"""后端统一错误定义。"""

from __future__ import annotations


class AppError(Exception):
    """服务层统一业务错误。"""

    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None) -> None:
        """初始化业务错误对象。"""

        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class NotFoundError(AppError):
    """资源不存在错误。"""

    def __init__(self, code: str, message: str) -> None:
        """构造 404 类型错误。"""

        super().__init__(status_code=404, code=code, message=message)


class ConflictError(AppError):
    """资源冲突错误。"""

    def __init__(self, code: str, message: str) -> None:
        """构造 409 类型错误。"""

        super().__init__(status_code=409, code=code, message=message)


class BadRequestError(AppError):
    """客户端请求参数非法错误。"""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        """构造 400 类型错误。"""

        super().__init__(status_code=400, code=code, message=message, details=details)


class UnauthorizedError(AppError):
    """未授权错误。"""

    def __init__(self, code: str, message: str) -> None:
        """构造 401 类型错误。"""

        super().__init__(status_code=401, code=code, message=message)


class IntegrationError(AppError):
    """外部集成调用失败错误。"""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        """构造 502 类型错误。"""

        super().__init__(status_code=502, code=code, message=message, details=details)
