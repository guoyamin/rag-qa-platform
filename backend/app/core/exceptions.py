"""
智能问答平台 - 自定义异常

设计原则（遵循 CODING_STANDARD 5.2）：
- Service 层只抛 BaseAppException 子类，不直接抛 HTTPException
- 每个异常携带 http_status（协议层状态码）与 code（业务错误码）
- API 层的异常处理器据此返回正确的 HTTP 状态码
"""

from fastapi import status


class BaseAppException(Exception):
    """应用基础异常"""

    http_status: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str = "系统错误", code: str = "SYSTEM_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class AuthenticationError(BaseAppException):
    """认证异常（401）"""

    http_status = status.HTTP_401_UNAUTHORIZED

    def __init__(self, message: str = "认证失败"):
        super().__init__(message=message, code="AUTHENTICATION_ERROR")


class AuthorizationError(BaseAppException):
    """授权异常（403）"""

    http_status = status.HTTP_403_FORBIDDEN

    def __init__(self, message: str = "权限不足"):
        super().__init__(message=message, code="AUTHORIZATION_ERROR")


class NotFoundError(BaseAppException):
    """资源不存在异常（404）"""

    http_status = status.HTTP_404_NOT_FOUND

    def __init__(self, message: str = "资源不存在"):
        super().__init__(message=message, code="NOT_FOUND")


class ValidationError(BaseAppException):
    """参数校验异常（400）"""

    http_status = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str = "参数校验失败"):
        super().__init__(message=message, code="VALIDATION_ERROR")


class LLMError(BaseAppException):
    """LLM调用异常（503）"""

    http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    def __init__(self, message: str = "AI服务调用失败"):
        super().__init__(message=message, code="LLM_ERROR")


class RAGError(BaseAppException):
    """RAG流程异常（503）"""

    http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    def __init__(self, message: str = "知识检索失败"):
        super().__init__(message=message, code="RAG_ERROR")


class RateLimitExceeded(BaseAppException):
    """请求限流异常（429）"""

    http_status = status.HTTP_429_TOO_MANY_REQUESTS

    def __init__(self, message: str = "请求过于频繁"):
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED")


class ServiceUnavailableError(BaseAppException):
    """服务不可用异常（503）"""

    http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    def __init__(self, message: str = "服务暂时不可用"):
        super().__init__(message=message, code="SERVICE_UNAVAILABLE")
