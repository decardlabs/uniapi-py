# app/exceptions_improved.py - 改进的异常处理
# 这是建议的实现方案

from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi import Request
from app.errors import ErrorCode, ERROR_CODE_TO_STATUS, get_suggestion_for_error


class AppException(Exception):
    """改进的基础异常类
    
    特点：
    - 支持错误代码常量
    - 包含详细信息和建议
    - 自动映射 HTTP 状态码
    - 统一的异常处理器
    
    用法示例：
        raise AppException(
            error_code=ErrorCode.TOKEN_MODEL_NOT_ALLOWED,
            message="Token not allowed to use model 'deepseek-v4-pro'",
            details={
                "requested_model": "deepseek-v4-pro",
                "allowed_models": ["glm-5.2"],
            },
            suggestion="Call GET /v1/models to list available models",
        )
    """
    
    def __init__(
        self,
        error_code: str | ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        """初始化异常
        
        Args:
            error_code: 错误代码 (ErrorCode 枚举或字符串)
            message: 错误消息（人类可读）
            details: 上下文信息字典
            suggestion: 解决建议（可选，未提供时自动查询）
        """
        # 标准化错误代码
        if isinstance(error_code, ErrorCode):
            self.error_code = error_code.value
        else:
            self.error_code = str(error_code)
        
        self.message = message
        self.details = details or {}
        
        # 如果未提供建议，自动查询
        if suggestion is None:
            suggestion = get_suggestion_for_error(self.error_code)
        self.suggestion = suggestion
        
        # 从映射表查询状态码
        try:
            self.status_code = ERROR_CODE_TO_STATUS.get(
                ErrorCode(self.error_code),
                400
            )
        except ValueError:
            self.status_code = 400
        
        super().__init__(message)


class UnauthorizedException(AppException):
    """401 Unauthorized - 身份认证失败
    
    用法示例：
        raise UnauthorizedException(
            error_code=ErrorCode.INVALID_TOKEN,
            message="Token is invalid or expired",
        )
    """
    
    def __init__(
        self,
        error_code: str | ErrorCode = ErrorCode.INVALID_TOKEN,
        message: str = "Unauthorized",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )
        assert self.status_code == 401, f"Expected 401, got {self.status_code}"


class ForbiddenException(AppException):
    """403 Forbidden - 权限不足
    
    用法示例：
        raise ForbiddenException(
            error_code=ErrorCode.TOKEN_MODEL_NOT_ALLOWED,
            message="Token not allowed to use this model",
            details={"allowed_models": ["glm-5.2"]},
        )
    """
    
    def __init__(
        self,
        error_code: str | ErrorCode = ErrorCode.ACCESS_DENIED,
        message: str = "Forbidden",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )
        assert self.status_code == 403, f"Expected 403, got {self.status_code}"


class NotFoundException(AppException):
    """404 Not Found - 资源不存在
    
    用法示例：
        raise NotFoundException(
            error_code=ErrorCode.NOT_FOUND,
            message="User not found",
            details={"user_id": 123},
        )
    """
    
    def __init__(
        self,
        error_code: str | ErrorCode = ErrorCode.NOT_FOUND,
        message: str = "Not Found",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(error_code, message, details)
        assert self.status_code == 404, f"Expected 404, got {self.status_code}"


class BadRequestException(AppException):
    """400 Bad Request - 请求参数错误
    
    用法示例：
        raise BadRequestException(
            error_code=ErrorCode.INVALID_REQUEST,
            message="Password too short",
            details={"field": "password", "min_length": 8},
        )
    """
    
    def __init__(
        self,
        error_code: str | ErrorCode = ErrorCode.INVALID_REQUEST,
        message: str = "Bad Request",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(error_code, message, details, suggestion)
        assert self.status_code == 400, f"Expected 400, got {self.status_code}"


class QuotaExceededException(AppException):
    """额度用尽异常
    
    用法示例：
        raise QuotaExceededException(
            message="Token quota exhausted",
            details={
                "used_quota": 1000,
                "total_quota": 1000,
            },
        )
    """
    
    def __init__(
        self,
        message: str = "Quota exceeded",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        # 注意：这个特殊异常使用 401 状态码（本应是 402）
        # 未来应改为 402 Payment Required
        error_code = ErrorCode.TOKEN_QUOTA_EXHAUSTED
        
        super().__init__(
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )


class NotImplementedException(AppException):
    """501 Not Implemented"""
    
    def __init__(
        self,
        message: str = "Not implemented",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            error_code="NOT_IMPLEMENTED",
            message=message,
            details=details,
        )
        self.status_code = 501


# ========================= 异常处理器 =========================

async def app_exception_handler(
    request: Request, exc: AppException
) -> JSONResponse:
    """统一的异常处理器
    
    将 AppException 转换为 JSON 响应，包含完整的错误信息：
    - error_code: 机器可读的错误代码
    - message: 人类可读的错误消息
    - details: 上下文信息
    - suggestion: 解决建议
    - request_id: 追踪 ID
    - timestamp: 错误发生时间
    
    响应示例：
        {
            "success": false,
            "error": {
                "code": "TOKEN_MODEL_NOT_ALLOWED",
                "message": "Token not allowed to use model 'deepseek-v4-pro'",
                "details": {
                    "requested_model": "deepseek-v4-pro",
                    "allowed_models": ["glm-5.2"]
                },
                "suggestion": "Call GET /v1/models to list available models",
                "request_id": "req_abc123def456",
                "timestamp": "2026-06-21T10:30:00.123456Z"
            }
        }
    """
    
    # 构建错误响应
    error_content = {
        "code": exc.error_code,
        "message": exc.message,
        "details": exc.details,
        "request_id": getattr(request.state, "request_id", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # 仅在有建议时包含建议字段
    if exc.suggestion:
        error_content["suggestion"] = exc.suggestion
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": error_content,
        },
    )


# ========================= 使用示例 =========================

"""
在 FastAPI 应用中使用：

from fastapi import FastAPI
from app.exceptions import app_exception_handler, AppException

app = FastAPI()

# 注册异常处理器
app.add_exception_handler(AppException, app_exception_handler)

# 在路由中使用异常
@app.post("/api/chat")
async def chat(request: ChatRequest):
    if request.model not in allowed_models:
        raise ForbiddenException(
            error_code=ErrorCode.TOKEN_MODEL_NOT_ALLOWED,
            message=f"Token not allowed to use model '{request.model}'",
            details={
                "requested_model": request.model,
                "allowed_models": list(allowed_models),
            },
        )
    
    # 处理请求...
    
    return response


# 在依赖项中使用
from fastapi import Depends

def check_admin_role(user: User = Depends(get_user)):
    if user.role < 10:
        raise ForbiddenException(
            error_code=ErrorCode.ADMIN_ACCESS_REQUIRED,
            message="Admin access required",
        )
    return user

# 在服务中使用
async def get_token(token_key: str):
    token = await db.get(Token, key=token_key)
    if not token:
        raise UnauthorizedException(
            error_code=ErrorCode.INVALID_TOKEN,
            message="Token not found",
        )
    return token
"""
