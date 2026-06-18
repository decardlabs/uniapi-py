from __future__ import annotations

from typing import Any, Optional

from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(
        self,
        status_code: int = 400,
        message: str = "Bad request",
        data: Any = None,
    ):
        self.status_code = status_code
        self.message = message
        self.data = data


class NotFoundException(AppException):
    def __init__(self, message: str = "Not found"):
        super().__init__(status_code=404, message=message)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(status_code=401, message=message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(status_code=403, message=message)


class QuotaExceededException(AppException):
    def __init__(self, message: str = "Quota exceeded"):
        super().__init__(status_code=400, message=message)


class NotImplementedException(AppException):
    def __init__(self, message: str = "Not implemented"):
        super().__init__(status_code=501, message=message)


async def app_exception_handler(request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "data": exc.data,
        },
    )
