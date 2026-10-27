"""统一错误格式，不回显请求体或 SQL。"""

import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class BusinessError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str, details=None):
    return JSONResponse(status_code=status, content={
        "error": {"code": code, "message": message, "details": details or []}
    })


def install_error_handlers(app: FastAPI):
    @app.exception_handler(BusinessError)
    async def business_error(request: Request, exc: BusinessError):
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(map(str, err["loc"])), "message": err["msg"], "type": err["type"]}
            for err in exc.errors()
        ]
        return error_response(422, "VALIDATION_ERROR", "请求参数不合法，请检查字段。", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        response = error_response(exc.status_code, code, str(exc.detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc: sqlite3.Error):
        logger.error("SQLite request failed: %s", type(exc).__name__)
        if isinstance(exc, sqlite3.OperationalError):
            response = error_response(503, "DATABASE_UNAVAILABLE", "数据库暂时不可用，请稍后重试。")
            response.headers["Retry-After"] = "1"
            return response
        return error_response(500, "DATABASE_ERROR", "数据库操作失败。")
