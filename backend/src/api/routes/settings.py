"""系统设置路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_admin_user, get_current_user, get_db
from src.db.models.user import User
from src.schemas.ai_gateway import (
    AIDiscoveredModelCandidate,
    AIDiscoveredModelListResponse,
    AIGatewayDiscoveryPreviewRequest,
    AIGatewayCreateRequest,
    AIGatewayDetailResponse,
    AIGatewayListResponse,
    AIGatewayUpdateRequest,
    AIModelProfileCreateRequest,
    AIModelProfileResponse,
    AIModelProfileUpdateRequest,
    AIRuntimeModelOption,
    AIRuntimeModelOptionListResponse,
)
from src.schemas.common import ApiMessageResponse
from src.services.ai_gateway_service import AIGatewayService

router = APIRouter()


@router.get("/ai-models/runtime-options", response_model=AIRuntimeModelOptionListResponse)
def list_runtime_ai_models(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AIRuntimeModelOptionListResponse:
    """返回业务运行时可选的模型列表。"""

    items = AIGatewayService(db).list_runtime_model_options()
    return AIRuntimeModelOptionListResponse(
        items=[
            AIRuntimeModelOption(
                id=item.id,
                display_name=item.display_name,
                upstream_vendor=item.upstream_vendor,
                protocol_type=item.protocol_type,
                user_agent=item.user_agent,
                model_identifier=item.model_identifier,
                supports_vision=item.supports_vision,
                supports_stream=item.supports_stream,
                gateway_id=item.gateway.id,
                gateway_name=item.gateway.name,
                gateway_vendor=item.gateway.vendor,
                base_url=item.base_url_override or item.gateway.base_url,
            )
            for item in items
        ]
    )


@router.get("/ai-gateways", response_model=AIGatewayListResponse)
def list_ai_gateways(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> AIGatewayListResponse:
    """返回管理员配置中心所需的全部网关与模型配置。"""

    items = AIGatewayService(db).list_gateways()
    return AIGatewayListResponse(
        items=[AIGatewayDetailResponse.model_validate(item) for item in items]
    )


@router.get("/ai-gateways/{gateway_id}/discovered-models", response_model=AIDiscoveredModelListResponse)
def discover_ai_gateway_models(
    gateway_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> AIDiscoveredModelListResponse:
    """根据指定网关的 URL 与密钥自动探测可用模型。"""

    items = AIGatewayService(db).discover_gateway_models(gateway_id)
    return AIDiscoveredModelListResponse(
        items=[AIDiscoveredModelCandidate.model_validate(item) for item in items]
    )


@router.post("/ai-gateways/discovery-preview", response_model=AIDiscoveredModelListResponse)
def preview_ai_gateway_models(
    payload: AIGatewayDiscoveryPreviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> AIDiscoveredModelListResponse:
    """根据弹窗中临时填写的 URL 与密钥即时探测模型。"""

    items = AIGatewayService(db).preview_gateway_models(payload)
    return AIDiscoveredModelListResponse(
        items=[AIDiscoveredModelCandidate.model_validate(item) for item in items]
    )


@router.post("/ai-gateways", response_model=AIGatewayDetailResponse)
def create_ai_gateway(
    payload: AIGatewayCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> AIGatewayDetailResponse:
    """创建新的 AI 网关。"""

    gateway = AIGatewayService(db).create_gateway(payload)
    return AIGatewayDetailResponse.model_validate(gateway)


@router.put("/ai-gateways/{gateway_id}", response_model=AIGatewayDetailResponse)
def update_ai_gateway(
    gateway_id: int,
    payload: AIGatewayUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> AIGatewayDetailResponse:
    """更新指定 AI 网关。"""

    gateway = AIGatewayService(db).update_gateway(gateway_id, payload)
    return AIGatewayDetailResponse.model_validate(gateway)


@router.delete("/ai-gateways/{gateway_id}", response_model=ApiMessageResponse)
def delete_ai_gateway(
    gateway_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> ApiMessageResponse:
    """删除指定 AI 网关。"""

    AIGatewayService(db).delete_gateway(gateway_id)
    return ApiMessageResponse(message="AI 网关已删除。")


@router.post("/ai-gateways/{gateway_id}/models", response_model=AIModelProfileResponse)
def create_ai_model(
    gateway_id: int,
    payload: AIModelProfileCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> AIModelProfileResponse:
    """在指定 AI 网关下创建模型配置。"""

    model = AIGatewayService(db).create_model(gateway_id, payload)
    return AIModelProfileResponse.model_validate(model)


@router.put("/ai-models/{model_id}", response_model=AIModelProfileResponse)
def update_ai_model(
    model_id: int,
    payload: AIModelProfileUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> AIModelProfileResponse:
    """更新指定 AI 模型配置。"""

    model = AIGatewayService(db).update_model(model_id, payload)
    return AIModelProfileResponse.model_validate(model)


@router.delete("/ai-models/{model_id}", response_model=ApiMessageResponse)
def delete_ai_model(
    model_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> ApiMessageResponse:
    """删除指定 AI 模型配置。"""

    AIGatewayService(db).delete_model(model_id)
    return ApiMessageResponse(message="AI 模型配置已删除。")
