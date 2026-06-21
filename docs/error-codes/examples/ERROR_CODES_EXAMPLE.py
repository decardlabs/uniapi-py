# app/errors.py - 改进的错误代码定义
# 这是建议的实现方案

from enum import Enum


class ErrorCode(str, Enum):
    """API 错误代码常量
    
    每个错误都有唯一的代码，便于:
    - 客户端编程式处理
    - 日志搜索和分析
    - 文档查询
    - 多语言支持
    """
    
    # ==================== 认证错误 (401) ====================
    NOT_LOGGED_IN = "NOT_LOGGED_IN"
    """用户未登录（缺少有效会话）"""
    
    NO_TOKEN_PROVIDED = "NO_TOKEN_PROVIDED"
    """中继端点缺少 Bearer token"""
    
    INVALID_TOKEN = "INVALID_TOKEN"
    """Token 不存在或格式错误"""
    
    TOKEN_DISABLED = "TOKEN_DISABLED"
    """Token 已被禁用（status != 1）"""
    
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    """Token 时间戳已过期"""
    
    TOKEN_QUOTA_EXHAUSTED = "TOKEN_QUOTA_EXHAUSTED"
    """Token 的额度用尽（remain_quota <= 0）"""
    
    USER_DISABLED = "USER_DISABLED"
    """Token 对应的用户被禁用"""
    
    # ==================== 权限错误 (403) ====================
    ACCESS_DENIED = "ACCESS_DENIED"
    """一般权限拒绝"""
    
    ADMIN_ACCESS_REQUIRED = "ADMIN_ACCESS_REQUIRED"
    """需要管理员权限（role >= 10）"""
    
    ROOT_ACCESS_REQUIRED = "ROOT_ACCESS_REQUIRED"
    """需要 root 权限（role >= 100）"""
    
    TOKEN_MODEL_NOT_ALLOWED = "TOKEN_MODEL_NOT_ALLOWED"
    """Token 无权使用该模型"""
    
    USER_GROUP_NOT_ALLOWED = "USER_GROUP_NOT_ALLOWED"
    """用户组无权访问该通道"""
    
    FUSION_NOT_AUTHORIZED = "FUSION_NOT_AUTHORIZED"
    """Token 无权使用 Fusion 引擎"""
    
    # ==================== 业务错误 (400) ====================
    INVALID_REQUEST = "INVALID_REQUEST"
    """请求参数或格式错误"""
    
    MODEL_NOT_SPECIFIED = "MODEL_NOT_SPECIFIED"
    """Token 有权限限制但未指定模型"""
    
    MODEL_NOT_SUPPORTED = "MODEL_NOT_SUPPORTED"
    """指定的模型无提供商支持"""
    
    NO_AVAILABLE_CHANNELS = "NO_AVAILABLE_CHANNELS"
    """该模型没有可用的通道"""
    
    INSUFFICIENT_QUOTA = "INSUFFICIENT_QUOTA"
    """Token 或用户额度不足"""
    
    # ==================== 其他错误 ====================
    NOT_FOUND = "NOT_FOUND"
    """资源不存在（404）"""
    
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    """请求速率超过限制（429）"""
    
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    """预算不足或支付必需（402）"""
    
    INTERNAL_ERROR = "INTERNAL_ERROR"
    """服务器内部错误（500）"""


# 错误代码 → HTTP 状态码映射表
# 便于快速查询和异常处理器使用
ERROR_CODE_TO_STATUS = {
    # 401 Unauthorized
    ErrorCode.NOT_LOGGED_IN: 401,
    ErrorCode.NO_TOKEN_PROVIDED: 401,
    ErrorCode.INVALID_TOKEN: 401,
    ErrorCode.TOKEN_DISABLED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.TOKEN_QUOTA_EXHAUSTED: 401,
    ErrorCode.USER_DISABLED: 401,
    
    # 403 Forbidden
    ErrorCode.ACCESS_DENIED: 403,
    ErrorCode.ADMIN_ACCESS_REQUIRED: 403,
    ErrorCode.ROOT_ACCESS_REQUIRED: 403,
    ErrorCode.TOKEN_MODEL_NOT_ALLOWED: 403,
    ErrorCode.USER_GROUP_NOT_ALLOWED: 403,
    ErrorCode.FUSION_NOT_AUTHORIZED: 403,
    
    # 400 Bad Request
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.MODEL_NOT_SPECIFIED: 400,
    ErrorCode.MODEL_NOT_SUPPORTED: 400,
    ErrorCode.NO_AVAILABLE_CHANNELS: 400,
    ErrorCode.INSUFFICIENT_QUOTA: 400,
    
    # 其他
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.PAYMENT_REQUIRED: 402,
    ErrorCode.INTERNAL_ERROR: 500,
}


# 错误代码 → 建议的建议文本映射
ERROR_CODE_TO_SUGGESTION = {
    ErrorCode.NOT_LOGGED_IN: 
        "Please log in to access this resource.",
    
    ErrorCode.NO_TOKEN_PROVIDED:
        "Add 'Authorization: Bearer {token}' header to your request.",
    
    ErrorCode.INVALID_TOKEN:
        "Check that your token is correct and properly formatted.",
    
    ErrorCode.TOKEN_DISABLED:
        "Your token has been disabled. Contact administrators for assistance.",
    
    ErrorCode.TOKEN_EXPIRED:
        "Your token has expired. Please apply for a new token.",
    
    ErrorCode.TOKEN_QUOTA_EXHAUSTED:
        "Your token's quota has been exhausted. Purchase additional quota or wait for renewal.",
    
    ErrorCode.USER_DISABLED:
        "The user associated with this token has been disabled. Contact administrators.",
    
    ErrorCode.ADMIN_ACCESS_REQUIRED:
        "Your user role must be 10 or higher. Contact administrators for access.",
    
    ErrorCode.ROOT_ACCESS_REQUIRED:
        "Only root users (role >= 100) can access this. Contact system administrators.",
    
    ErrorCode.TOKEN_MODEL_NOT_ALLOWED:
        "Call GET /v1/models to list available models for your token.",
    
    ErrorCode.USER_GROUP_NOT_ALLOWED:
        "Your user group does not have access to this resource. Contact administrators.",
    
    ErrorCode.FUSION_NOT_AUTHORIZED:
        "You don't have authorization for Fusion engine. Check your token permissions.",
    
    ErrorCode.MODEL_NOT_SPECIFIED:
        "Specify a model or call GET /v1/models to list available models.",
    
    ErrorCode.MODEL_NOT_SUPPORTED:
        "This model is not supported by any configured provider. Check supported models list.",
    
    ErrorCode.NO_AVAILABLE_CHANNELS:
        "No available channels for this model. Try again later or use another model.",
    
    ErrorCode.INSUFFICIENT_QUOTA:
        "Your quota is insufficient for this request. Reduce request size or purchase more quota.",
    
    ErrorCode.RATE_LIMIT_EXCEEDED:
        "You are making requests too frequently. Please wait before trying again.",
    
    ErrorCode.PAYMENT_REQUIRED:
        "Your budget or quota requires payment/renewal. Contact support.",
}


# 错误代码 → 文档 URL 映射
ERROR_CODE_TO_HELP_URL = {
    ErrorCode.NOT_LOGGED_IN:
        "https://docs.example.com/auth/login",
    
    ErrorCode.NO_TOKEN_PROVIDED:
        "https://docs.example.com/auth/tokens",
    
    ErrorCode.TOKEN_MODEL_NOT_ALLOWED:
        "https://docs.example.com/api/models",
    
    ErrorCode.ADMIN_ACCESS_REQUIRED:
        "https://docs.example.com/admin/roles",
    
    ErrorCode.INSUFFICIENT_QUOTA:
        "https://docs.example.com/billing/quota",
}


def get_suggestion_for_error(error_code: str | ErrorCode) -> str | None:
    """获取错误的建议文本"""
    if isinstance(error_code, str):
        try:
            error_code = ErrorCode(error_code)
        except ValueError:
            return None
    return ERROR_CODE_TO_SUGGESTION.get(error_code)


def get_help_url_for_error(error_code: str | ErrorCode) -> str | None:
    """获取错误的帮助 URL"""
    if isinstance(error_code, str):
        try:
            error_code = ErrorCode(error_code)
        except ValueError:
            return None
    return ERROR_CODE_TO_HELP_URL.get(error_code)
