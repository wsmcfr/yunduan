"""上传和文件对象相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models.enums import FileKind, StorageProvider
from src.schemas.common import ORMBaseModel


class FileObjectCreateRequest(BaseModel):
    """登记文件对象元数据的请求体。"""

    file_kind: FileKind
    storage_provider: StorageProvider = StorageProvider.COS
    bucket_name: str = Field(min_length=1, max_length=128)
    region: str = Field(min_length=1, max_length=64)
    object_key: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=128)
    size_bytes: int | None = Field(default=None, ge=0)
    etag: str | None = Field(default=None, max_length=128)
    uploaded_at: datetime | None = None
    storage_last_modified: datetime | None = None


class FileObjectResponse(ORMBaseModel):
    """文件对象完整响应体。"""

    id: int
    detection_record_id: int
    file_kind: FileKind
    storage_provider: StorageProvider
    bucket_name: str
    region: str
    object_key: str
    content_type: str | None
    size_bytes: int | None
    etag: str | None
    preview_url: str | None = None
    uploaded_at: datetime | None
    storage_last_modified: datetime | None
    created_at: datetime


class CosUploadPrepareRequest(BaseModel):
    """生成 COS 上传计划的请求体。"""

    record_id: int | None = Field(default=None, ge=1)
    record_no: str | None = Field(default=None, max_length=64)
    file_kind: FileKind
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=128)


class CosUploadPrepareResponse(BaseModel):
    """COS 预签名上传或占位模式响应体。"""

    enabled: bool
    provider: StorageProvider
    bucket_name: str
    region: str
    object_key: str
    upload_url: str | None
    method: str
    headers: dict[str, str]
    expires_in_seconds: int | None
    message: str
