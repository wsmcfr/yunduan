"""后端配置读取模块。"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中定义服务端运行所需的配置项。"""

    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    secret_encryption_key: str = Field(default="", alias="SECRET_ENCRYPTION_KEY")
    password_pepper: str = Field(default="", alias="PASSWORD_PEPPER")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    auth_cookie_name: str = Field(default="yunduan_session", alias="AUTH_COOKIE_NAME")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        alias="AUTH_COOKIE_SAMESITE",
    )
    auth_cookie_domain: str = Field(default="", alias="AUTH_COOKIE_DOMAIN")
    allow_public_registration: bool = Field(default=True, alias="ALLOW_PUBLIC_REGISTRATION")
    password_reset_token_expire_minutes: int = Field(
        default=30,
        alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
    )
    password_reset_request_cooldown_seconds: int = Field(
        default=60,
        alias="PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS",
    )
    # 公开访问地址默认留空，避免生产环境误发出指向 localhost 的重置邮件。
    public_app_url: str = Field(default="", alias="PUBLIC_APP_URL")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="云端检测系统", alias="SMTP_FROM_NAME")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, alias="SMTP_USE_SSL")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    cos_secret_id: str = Field(default="", alias="COS_SECRET_ID")
    cos_secret_key: str = Field(default="", alias="COS_SECRET_KEY")
    cos_region: str = Field(default="", alias="COS_REGION")
    cos_bucket: str = Field(default="", alias="COS_BUCKET")
    cos_public_base_url: str = Field(default="", alias="COS_PUBLIC_BASE_URL")
    cos_signed_url_expire_seconds: int = Field(default=3600, alias="COS_SIGNED_URL_EXPIRE_SECONDS")
    # 云端复核检测开关。关闭后服务仍会写入可读的 skipped 上下文，避免接口静默无结果。
    cloud_detection_enabled: bool = Field(default=True, alias="CLOUD_DETECTION_ENABLED")
    # 模型根目录只作为部署说明和后续相对路径扩展使用；实际加载以两个模型路径字段为准。
    cloud_detection_model_root: str = Field(default="D:\\model_picture", alias="CLOUD_DETECTION_MODEL_ROOT")
    # MobileNetV3-Small 分类模型路径，默认指向模型项目中已验证的静态混合 INT8 模型。
    cloud_detection_classifier_model_path: str = Field(
        default="D:\\model_picture\\checkpoints_classify\\defect_classifier_static_mixed_int8.onnx",
        alias="CLOUD_DETECTION_CLASSIFIER_MODEL_PATH",
    )
    # UNet-MobileNetV3 分割模型路径，默认指向模型项目中已验证的 decoder/head INT8 模型。
    cloud_detection_segment_model_path: str = Field(
        default="D:\\model_picture\\checkpoints_unet_test\\defect_unet_test_decoder_head_int8.onnx",
        alias="CLOUD_DETECTION_SEGMENT_MODEL_PATH",
    )
    # UNet 输出类别数量：背景 + scratch/rust/dent/crack/burr。
    cloud_detection_segment_num_classes: int = Field(default=6, alias="CLOUD_DETECTION_SEGMENT_NUM_CLASSES")
    # UNet 非背景像素达到该阈值时判为疑似不良。
    cloud_detection_defect_pixel_threshold: int = Field(default=80, alias="CLOUD_DETECTION_DEFECT_PIXEL_THRESHOLD")
    # 单张图片下载大小上限，防止误把超大对象送入同步推理路径。
    cloud_detection_max_image_bytes: int = Field(default=8 * 1024 * 1024, alias="CLOUD_DETECTION_MAX_IMAGE_BYTES")
    default_admin_username: str = Field(default="admin", alias="DEFAULT_ADMIN_USERNAME")
    # 默认管理员密码必须由部署环境显式提供，避免源码自带可预测口令。
    default_admin_password: str = Field(default="", alias="DEFAULT_ADMIN_PASSWORD")
    default_admin_display_name: str = Field(default="系统管理员", alias="DEFAULT_ADMIN_DISPLAY_NAME")
    default_admin_email: str = Field(default="admin@example.com", alias="DEFAULT_ADMIN_EMAIL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        """将逗号分隔的 CORS 配置转换为列表。"""

        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def auth_cookie_domain_value(self) -> str | None:
        """返回可以直接传给 Cookie API 的域名值。"""

        normalized_domain = self.auth_cookie_domain.strip()
        return normalized_domain or None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局单例配置对象。"""

    return Settings()
