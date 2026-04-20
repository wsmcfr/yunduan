"""腾讯云 COS 集成客户端。"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

from src.core.errors import IntegrationError
from src.core.config import get_settings
from src.core.logging import get_logger
from src.db.models.enums import FileKind, StorageProvider

logger = get_logger(__name__)


class CosClient:
    """负责生成 COS 上传计划或预签名 URL。"""

    def __init__(self) -> None:
        """读取当前服务端 COS 配置。"""

        self.settings = get_settings()

    def is_configured(self) -> bool:
        """判断当前服务端是否具备生成 COS 签名请求的最小配置。"""

        return all(
            [
                self.settings.cos_secret_id,
                self.settings.cos_secret_key,
                self.settings.cos_region,
                self.settings.cos_bucket,
            ]
        )

    def _build_object_key(self, record_no: str, file_kind: FileKind, file_name: str) -> str:
        """根据业务编号和文件类型生成稳定的对象路径。"""

        safe_name = Path(file_name).name or "unnamed.bin"
        return f"detections/{record_no}/{file_kind.value}/{uuid4().hex}_{safe_name}"

    def _get_sdk_client(self, *, region: str):
        """按指定地域创建 COS SDK 客户端。"""

        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(
            Region=region,
            SecretId=self.settings.cos_secret_id,
            SecretKey=self.settings.cos_secret_key,
            Token=None,
            Scheme="https",
        )
        return CosS3Client(config)

    def build_public_url(self, *, bucket_name: str, region: str, object_key: str) -> str | None:
        """拼装文件对象的公开访问地址或自定义域名地址。"""

        if object_key.startswith(("http://", "https://")):
            return object_key

        if not bucket_name or not region or not object_key:
            return None

        quoted_object_key = quote(object_key, safe="/")
        public_base_url = str(self.settings.cos_public_base_url or "").strip().rstrip("/")
        if public_base_url:
            return f"{public_base_url}/{quoted_object_key}"
        return f"https://{bucket_name}.cos.{region}.myqcloud.com/{quoted_object_key}"

    def build_object_access_url(
        self,
        *,
        bucket_name: str,
        region: str,
        object_key: str,
        expires_seconds: int | None = None,
    ) -> str | None:
        """为给定文件对象生成访问 URL。

        优先使用带时效的下载签名 URL；签名不可用时退回到公开地址。
        这样前端预览、AI 看图、PDF 嵌图都能复用同一条对象访问链路。
        """

        if object_key.startswith(("http://", "https://")):
            return object_key

        if not bucket_name or not region or not object_key:
            return None

        resolved_expire_seconds = expires_seconds or self.settings.cos_signed_url_expire_seconds
        if not self.is_configured():
            return self.build_public_url(
                bucket_name=bucket_name,
                region=region,
                object_key=object_key,
            )

        try:
            client = self._get_sdk_client(region=region)
            return client.get_presigned_url(
                Method="GET",
                Bucket=bucket_name,
                Key=object_key,
                Expired=resolved_expire_seconds,
            )
        except Exception as exc:
            logger.warning(
                "cos.build_access_url_failed event=cos.build_access_url_failed bucket=%s region=%s object_key=%s error=%s",
                bucket_name,
                region,
                object_key,
                str(exc),
            )
            return self.build_public_url(
                bucket_name=bucket_name,
                region=region,
                object_key=object_key,
            )

    def read_file_bytes(
        self,
        *,
        bucket_name: str,
        region: str,
        object_key: str,
        timeout_seconds: int = 60,
        max_bytes: int | None = None,
    ) -> dict[str, str | bytes]:
        """读取指定 COS 文件对象的字节内容。

        这里统一通过“签名下载 URL + HTTP GET”读取对象，避免业务层直接感知 SDK 细节。
        """

        access_url = self.build_object_access_url(
            bucket_name=bucket_name,
            region=region,
            object_key=object_key,
        )
        if access_url is None:
            raise IntegrationError(
                code="cos_object_unavailable",
                message="当前文件对象缺少可用的 COS 访问信息。",
                details={
                    "bucket_name": bucket_name,
                    "region": region,
                    "object_key": object_key,
                },
            )

        request = Request(
            access_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
                response_bytes = response.read((max_bytes + 1) if max_bytes is not None else None)
        except HTTPError as exc:
            raise IntegrationError(
                code="cos_download_failed",
                message=f"COS 文件下载失败，HTTP {exc.code}。",
                details={
                    "bucket_name": bucket_name,
                    "region": region,
                    "object_key": object_key,
                    "status_code": exc.code,
                },
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise IntegrationError(
                code="cos_download_failed",
                message="COS 文件下载失败，请检查对象访问权限、地域和网络。",
                details={
                    "bucket_name": bucket_name,
                    "region": region,
                    "object_key": object_key,
                    "reason": str(exc),
                },
            ) from exc

        if max_bytes is not None and len(response_bytes) > max_bytes:
            raise IntegrationError(
                code="cos_object_too_large",
                message="COS 文件大小超过当前处理上限。",
                details={
                    "bucket_name": bucket_name,
                    "region": region,
                    "object_key": object_key,
                    "max_bytes": max_bytes,
                    "actual_size": len(response_bytes),
                },
            )

        return {
            "access_url": access_url,
            "content_type": content_type or mimetypes.guess_type(access_url)[0] or "application/octet-stream",
            "data": response_bytes,
        }

    def prepare_upload(
        self,
        *,
        record_no: str,
        file_kind: FileKind,
        file_name: str,
        content_type: str,
    ) -> dict:
        """生成 COS 上传所需的预签名参数或占位结果。"""

        object_key = self._build_object_key(record_no, file_kind, file_name)
        bucket_name = self.settings.cos_bucket
        region = self.settings.cos_region

        # 当 COS 配置不完整时，仍然返回占位对象路径，便于前后端先联调接口。
        if not self.is_configured():
            return {
                "enabled": False,
                "provider": StorageProvider.COS,
                "bucket_name": bucket_name,
                "region": region,
                "object_key": object_key,
                "upload_url": None,
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "expires_in_seconds": None,
                "message": "COS 未配置完成，当前返回占位上传计划。",
            }

        try:
            client = self._get_sdk_client(region=region)
            headers = {"Content-Type": content_type}
            upload_url = client.get_presigned_url(
                Method="PUT",
                Bucket=bucket_name,
                Key=object_key,
                Expired=3600,
                Headers=headers,
            )
            return {
                "enabled": True,
                "provider": StorageProvider.COS,
                "bucket_name": bucket_name,
                "region": region,
                "object_key": object_key,
                "upload_url": upload_url,
                "method": "PUT",
                "headers": headers,
                "expires_in_seconds": 3600,
                "message": "COS 预签名地址生成成功。",
            }
        except Exception as exc:
            logger.warning(
                "cos.prepare_failed event=cos.prepare_failed bucket=%s region=%s object_key=%s error=%s",
                bucket_name,
                region,
                object_key,
                str(exc),
            )
            return {
                "enabled": False,
                "provider": StorageProvider.COS,
                "bucket_name": bucket_name,
                "region": region,
                "object_key": object_key,
                "upload_url": None,
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "expires_in_seconds": None,
                "message": "COS 预签名生成失败，当前已退化为占位模式。",
            }
