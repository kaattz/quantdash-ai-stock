"""请求上下文中间件、统一异常处理和日志配置。"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from server.shared.runtime import LOGGER


# ---------------------------------------------------------------------------
# RequestContextMiddleware — 为每个请求分配 X-Request-ID
# ---------------------------------------------------------------------------
class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求生成唯一的 ``X-Request-ID`` 并附加到响应头。"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# register_exception_handlers — 统一处理 422、HTTP 异常和未捕获异常
# ---------------------------------------------------------------------------
def register_exception_handlers(app: FastAPI) -> None:
    """向 FastAPI 应用注册全局异常处理器。

    处理三类异常：
    1. 422 ``RequestValidationError`` — 请求参数校验失败
    2. ``HTTPException`` — 业务逻辑主动抛出的 HTTP 错误
    3. 未捕获的 ``Exception`` — 兜底 500 错误
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "body": getattr(exc, "body", None),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(getattr(request, "state", None), "request_id", None)
        LOGGER.error(
            "未捕获异常 [request_id=%s]: %s",
            request_id,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误"},
        )


# ---------------------------------------------------------------------------
# setup_logging — 日志格式配置
# ---------------------------------------------------------------------------
def setup_logging() -> None:
    """配置基础日志格式。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
