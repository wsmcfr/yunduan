"""AI 网关与模型配置服务实现。"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.errors import BadRequestError, ConflictError, NotFoundError
from src.core.secret_cipher import SecretCipher
from src.db.models.ai_gateway import AIGateway
from src.db.models.ai_model_profile import AIModelProfile
from src.db.models.enums import AIGatewayVendor, AIProtocolType
from src.integrations.ai_model_discovery_client import AIModelDiscoveryClient
from src.repositories.ai_gateway_repository import AIGatewayRepository
from src.repositories.ai_model_profile_repository import AIModelProfileRepository
from src.schemas.ai_gateway import (
    AIGatewayDiscoveryPreviewRequest,
    AIGatewayCreateRequest,
    AIGatewayUpdateRequest,
    AIModelProfileCreateRequest,
    AIModelProfileUpdateRequest,
)


class AIGatewayService:
    """封装 AI 网关与模型配置中心的业务流程。"""

    def __init__(
        self,
        db: Session,
        cipher: SecretCipher | None = None,
        discovery_client: AIModelDiscoveryClient | None = None,
    ) -> None:
        """初始化 AI 配置中心依赖。"""

        self.db = db
        self.gateway_repository = AIGatewayRepository(db)
        self.model_repository = AIModelProfileRepository(db)
        self.cipher = cipher or SecretCipher()
        self.discovery_client = discovery_client or AIModelDiscoveryClient()
        # 每次调用前都会写入当前公司范围，避免服务内的重复查询忘记带租户条件。
        self._company_id = 0

    def _set_company_scope(self, *, company_id: int) -> None:
        """记录当前调用所属的公司范围。"""

        self._company_id = company_id

    def _normalize_api_key(self, api_key: str | None) -> str:
        """把 API Key 规整成适合持久化的形式。"""

        normalized_api_key = (api_key or "").strip()
        if not normalized_api_key:
            raise BadRequestError(code="api_key_required", message="请填写有效的 API Key。")

        return normalized_api_key

    def _ensure_gateway_name_unique(self, *, name: str, exclude_id: int | None = None) -> None:
        """校验 AI 网关名称唯一。"""

        existed = self.gateway_repository.get_by_name(name, company_id=self._company_id)
        if existed is not None and existed.id != exclude_id:
            raise ConflictError(code="ai_gateway_name_exists", message="AI 网关名称已存在。")

    def _build_api_key_fields(self, api_key: str) -> tuple[str, str]:
        """把明文 API Key 转成数据库可持久化的密文字段。"""

        normalized_api_key = self._normalize_api_key(api_key)
        encrypted_value = self.cipher.encrypt(normalized_api_key)
        return encrypted_value, normalized_api_key[-4:]

    def _raise_gateway_name_integrity_error(self, exc: IntegrityError) -> None:
        """把数据库唯一约束冲突转换成更清晰的业务错误。"""

        raw_message = str(getattr(exc, "orig", exc))
        if "ix_ai_gateways_name" in raw_message:
            raise ConflictError(
                code="ai_gateway_global_name_conflict",
                message="数据库仍残留旧的全局唯一索引，不同公司暂时不能使用同名 AI 网关。请先执行最新数据库迁移后再重试。",
            ) from exc

        raise ConflictError(
            code="ai_gateway_name_exists",
            message="当前公司下已存在同名 AI 网关，请修改名称后再试。",
        ) from exc

    def list_gateways(self, *, company_id: int) -> list[AIGateway]:
        """返回配置中心所需的全部网关与模型配置。"""

        self._set_company_scope(company_id=company_id)
        gateways = self.gateway_repository.list_all(company_id=company_id)
        for gateway in gateways:
            gateway.models = sorted(
                gateway.models,
                key=lambda item: (item.updated_at, item.id),
                reverse=True,
            )
        return gateways

    def list_runtime_model_options(self, *, company_id: int) -> list[AIModelProfile]:
        """返回业务运行时可用的模型配置。"""

        self._set_company_scope(company_id=company_id)
        enabled_models = self.model_repository.list_runtime_enabled(company_id=company_id)
        return [
            item
            for item in enabled_models
            if item.gateway.is_enabled and item.gateway.has_api_key and item.is_enabled
        ]

    def get_model_for_runtime(self, *, company_id: int, model_id: int) -> AIModelProfile:
        """获取业务运行时实际可用的模型配置。"""

        self._set_company_scope(company_id=company_id)
        model = self.model_repository.get_by_id(
            model_id,
            company_id=company_id,
            include_gateway=True,
        )
        if model is None:
            raise NotFoundError(code="ai_model_not_found", message="AI 模型配置不存在。")
        if not model.is_enabled:
            raise BadRequestError(code="ai_model_disabled", message="所选 AI 模型已停用。")
        if not model.gateway.is_enabled:
            raise BadRequestError(code="ai_gateway_disabled", message="所属 AI 网关已停用。")
        if not model.gateway.has_api_key:
            raise BadRequestError(code="ai_gateway_missing_key", message="所属 AI 网关缺少 API Key。")

        return model

    def _normalize_runtime_base_url(
        self,
        *,
        base_url: str,
        protocol_type: AIProtocolType,
        gateway_vendor: AIGatewayVendor,
    ) -> str:
        """把历史配置里的基地址规整成真正可请求的运行时地址。"""

        normalized_base_url = base_url.strip().rstrip("/")
        if not normalized_base_url:
            return normalized_base_url

        parsed_url = urlparse(normalized_base_url)
        normalized_path = parsed_url.path.rstrip("/")

        if protocol_type == AIProtocolType.ANTHROPIC_MESSAGES and normalized_path.endswith("/v1"):
            next_path = normalized_path[:-3]
            return urlunparse(parsed_url._replace(path=next_path))

        if (
            gateway_vendor == AIGatewayVendor.OPENCLAUDECODE
            and protocol_type in {AIProtocolType.OPENAI_COMPATIBLE, AIProtocolType.OPENAI_RESPONSES}
            and not normalized_path.endswith("/v1")
        ):
            next_path = f"{normalized_path}/v1" if normalized_path else "/v1"
            return urlunparse(parsed_url._replace(path=next_path))

        return normalized_base_url

    def build_runtime_model_context(
        self,
        *,
        company_id: int,
        model_id: int,
    ) -> dict[str, str | int | bool | None]:
        """把模型配置转换成运行时可直接消费的上下文摘要。"""

        model = self.get_model_for_runtime(company_id=company_id, model_id=model_id)
        runtime_base_url = self._normalize_runtime_base_url(
            base_url=model.base_url_override or model.gateway.base_url,
            protocol_type=model.protocol_type,
            gateway_vendor=model.gateway.vendor,
        )
        return {
            "model_profile_id": model.id,
            "display_name": model.display_name,
            "model_identifier": model.model_identifier,
            "upstream_vendor": model.upstream_vendor.value,
            "protocol_type": model.protocol_type.value,
            "auth_mode": model.auth_mode.value,
            "base_url": runtime_base_url,
            "user_agent": model.user_agent,
            "supports_vision": model.supports_vision,
            "supports_stream": model.supports_stream,
            "gateway_id": model.gateway.id,
            "gateway_name": model.gateway.name,
            "gateway_vendor": model.gateway.vendor.value,
            # 明文密钥只允许在服务端运行期短暂存在，不能透出到前端。
            "api_key": self.cipher.decrypt(model.gateway.api_key_encrypted),
        }

    def discover_gateway_models(self, *, company_id: int, gateway_id: int) -> list[dict]:
        """根据已保存的网关 URL 和密钥自动探测可选模型。"""

        self._set_company_scope(company_id=company_id)
        gateway = self.gateway_repository.get_by_id(gateway_id, company_id=company_id)
        if gateway is None:
            raise NotFoundError(code="ai_gateway_not_found", message="AI 网关不存在。")
        if not gateway.has_api_key:
            raise BadRequestError(code="ai_gateway_missing_key", message="请先为当前网关配置 API Key。")

        decrypted_api_key = self.cipher.decrypt(gateway.api_key_encrypted)
        return self.discovery_client.discover_models(
            gateway_vendor=gateway.vendor,
            base_url=gateway.base_url,
            api_key=decrypted_api_key,
        )

    def preview_gateway_models(self, payload: AIGatewayDiscoveryPreviewRequest) -> list[dict]:
        """根据弹窗内临时填写的 URL 和密钥即时探测模型。"""

        return self.discovery_client.discover_models(
            gateway_vendor=payload.vendor,
            base_url=payload.base_url,
            api_key=payload.api_key,
        )

    def create_gateway(self, *, company_id: int, payload: AIGatewayCreateRequest) -> AIGateway:
        """创建新的 AI 网关。"""

        self._set_company_scope(company_id=company_id)
        gateway_name = payload.name.strip()
        self._ensure_gateway_name_unique(name=gateway_name)
        encrypted_api_key, api_key_last4 = self._build_api_key_fields(payload.api_key)

        gateway = AIGateway(
            company_id=company_id,
            name=gateway_name,
            vendor=payload.vendor,
            official_url=(payload.official_url or "").strip() or None,
            base_url=payload.base_url.strip(),
            note=(payload.note or "").strip() or None,
            is_enabled=payload.is_enabled,
            is_custom=payload.is_custom,
            api_key_encrypted=encrypted_api_key,
            api_key_last4=api_key_last4,
        )
        try:
            self.gateway_repository.create(gateway)
            self.db.commit()
        except IntegrityError as exc:
            # flush / commit 命中唯一约束后会把当前事务打脏，
            # 必须先回滚再把错误映射成前端可读的业务提示。
            self.db.rollback()
            self._raise_gateway_name_integrity_error(exc)

        return self.gateway_repository.get_by_id(
            gateway.id,
            company_id=company_id,
            include_models=True,
        ) or gateway

    def update_gateway(
        self,
        *,
        company_id: int,
        gateway_id: int,
        payload: AIGatewayUpdateRequest,
    ) -> AIGateway:
        """更新指定 AI 网关。"""

        self._set_company_scope(company_id=company_id)
        gateway = self.gateway_repository.get_by_id(
            gateway_id,
            company_id=company_id,
            include_models=True,
        )
        if gateway is None:
            raise NotFoundError(code="ai_gateway_not_found", message="AI 网关不存在。")

        if payload.name is not None:
            normalized_name = payload.name.strip()
            self._ensure_gateway_name_unique(name=normalized_name, exclude_id=gateway_id)
            gateway.name = normalized_name
        if payload.vendor is not None:
            gateway.vendor = payload.vendor
        if "official_url" in payload.model_fields_set:
            gateway.official_url = (payload.official_url or "").strip() or None
        if payload.base_url is not None:
            gateway.base_url = payload.base_url.strip()
        if "note" in payload.model_fields_set:
            gateway.note = (payload.note or "").strip() or None
        if payload.is_enabled is not None:
            gateway.is_enabled = payload.is_enabled
        if payload.is_custom is not None:
            gateway.is_custom = payload.is_custom

        if "api_key" in payload.model_fields_set and payload.api_key is not None:
            normalized_api_key = payload.api_key.strip()
            if normalized_api_key:
                encrypted_api_key, api_key_last4 = self._build_api_key_fields(normalized_api_key)
                gateway.api_key_encrypted = encrypted_api_key
                gateway.api_key_last4 = api_key_last4

        try:
            self.gateway_repository.save(gateway)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self._raise_gateway_name_integrity_error(exc)

        return self.gateway_repository.get_by_id(
            gateway_id,
            company_id=company_id,
            include_models=True,
        ) or gateway

    def delete_gateway(self, *, company_id: int, gateway_id: int) -> None:
        """删除指定 AI 网关。"""

        self._set_company_scope(company_id=company_id)
        gateway = self.gateway_repository.get_by_id(gateway_id, company_id=company_id)
        if gateway is None:
            raise NotFoundError(code="ai_gateway_not_found", message="AI 网关不存在。")

        self.gateway_repository.delete(gateway)
        self.db.commit()

    def create_model(
        self,
        *,
        company_id: int,
        gateway_id: int,
        payload: AIModelProfileCreateRequest,
    ) -> AIModelProfile:
        """在指定网关下创建模型配置。"""

        self._set_company_scope(company_id=company_id)
        gateway = self.gateway_repository.get_by_id(gateway_id, company_id=company_id)
        if gateway is None:
            raise NotFoundError(code="ai_gateway_not_found", message="AI 网关不存在。")

        model = AIModelProfile(
            gateway_id=gateway_id,
            display_name=payload.display_name.strip(),
            upstream_vendor=payload.upstream_vendor,
            protocol_type=payload.protocol_type,
            auth_mode=payload.auth_mode,
            base_url_override=(payload.base_url_override or "").strip() or None,
            user_agent=(payload.user_agent or "").strip() or None,
            model_identifier=payload.model_identifier.strip(),
            supports_vision=payload.supports_vision,
            supports_stream=payload.supports_stream,
            is_enabled=payload.is_enabled,
            note=(payload.note or "").strip() or None,
        )
        self.model_repository.create(model)
        self.db.commit()
        return self.model_repository.get_by_id(
            model.id,
            company_id=company_id,
            include_gateway=True,
        ) or model

    def update_model(
        self,
        *,
        company_id: int,
        model_id: int,
        payload: AIModelProfileUpdateRequest,
    ) -> AIModelProfile:
        """更新指定模型配置。"""

        self._set_company_scope(company_id=company_id)
        model = self.model_repository.get_by_id(
            model_id,
            company_id=company_id,
            include_gateway=True,
        )
        if model is None:
            raise NotFoundError(code="ai_model_not_found", message="AI 模型配置不存在。")

        if payload.display_name is not None:
            model.display_name = payload.display_name.strip()
        if payload.upstream_vendor is not None:
            model.upstream_vendor = payload.upstream_vendor
        if payload.protocol_type is not None:
            model.protocol_type = payload.protocol_type
        if payload.auth_mode is not None:
            model.auth_mode = payload.auth_mode
        if "base_url_override" in payload.model_fields_set:
            model.base_url_override = (payload.base_url_override or "").strip() or None
        if "user_agent" in payload.model_fields_set:
            model.user_agent = (payload.user_agent or "").strip() or None
        if payload.model_identifier is not None:
            model.model_identifier = payload.model_identifier.strip()
        if payload.supports_vision is not None:
            model.supports_vision = payload.supports_vision
        if payload.supports_stream is not None:
            model.supports_stream = payload.supports_stream
        if payload.is_enabled is not None:
            model.is_enabled = payload.is_enabled
        if "note" in payload.model_fields_set:
            model.note = (payload.note or "").strip() or None

        self.model_repository.save(model)
        self.db.commit()
        return self.model_repository.get_by_id(
            model_id,
            company_id=company_id,
            include_gateway=True,
        ) or model

    def delete_model(self, *, company_id: int, model_id: int) -> None:
        """删除指定模型配置。"""

        self._set_company_scope(company_id=company_id)
        model = self.model_repository.get_by_id(model_id, company_id=company_id)
        if model is None:
            raise NotFoundError(code="ai_model_not_found", message="AI 模型配置不存在。")

        self.model_repository.delete(model)
        self.db.commit()
