"""日志初始化模块。"""

from __future__ import annotations

import logging
from logging.config import dictConfig


def setup_logging() -> None:
    """初始化服务端日志配置。"""

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["console"],
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """获取模块日志对象。"""

    return logging.getLogger(name)
