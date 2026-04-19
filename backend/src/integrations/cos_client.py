"""腾讯云 COS 集成客户端。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.core.config import get_settings
from src.core.logging import get_logger
from src.db.models.enums import FileKind, StorageProvider

logger = get_logger(__name__)


class CosClient:
    """负责生成 COS 上传计划或预签名 URL。"""

    def __init__(self) -> None:
        """读取当前服务端 COS 配置。"""

        self.settings = get_settings()

    def _build_object_key(self, record_no: str, file_kind: FileKind, file_name: str) -> str:
        """根据业务编号和文件类型生成稳定的对象路径。"""

        safe_name = Path(file_name).name or "unnamed.bin"
        return f"detections/{record_no}/{file_kind.value}/{uuid4().hex}_{safe_name}"

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
        if not all(
            [
                self.settings.cos_secret_id,
                self.settings.cos_secret_key,
                bucket_name,
                region,
            ]
        ):
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
            from qcloud_cos import CosConfig, CosS3Client

            config = CosConfig(
                Region=region,
                SecretId=self.settings.cos_secret_id,
                SecretKey=self.settings.cos_secret_key,
                Token=None,
                Scheme="https",
            )
            client = CosS3Client(config)
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
