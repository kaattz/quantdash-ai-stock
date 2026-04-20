"""QuantDash Screener Service 入口。

组装所有模块路由、中间件和异常处理，提供统一的 FastAPI 应用实例。
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.shared.runtime import lifespan
from server.shared.api import RequestContextMiddleware, register_exception_handlers, setup_logging
from server.modules.auth import ROUTER as AUTH_ROUTER, init_auth_db
from server.modules.screener import ROUTER as SCREENER_ROUTER
from server.modules.watchlist import ROUTER as WATCHLIST_ROUTER
from server.modules.integrations import ROUTER as INTEGRATIONS_ROUTER
from server.modules.sync_runtime import ROUTER as SYNC_ROUTER
from server.modules.skill_library import ROUTER as SKILL_LIBRARY_ROUTER

# ---------------------------------------------------------------------------
# 日志初始化
# ---------------------------------------------------------------------------
setup_logging()

# ---------------------------------------------------------------------------
# FastAPI 应用实例
# ---------------------------------------------------------------------------
APP = FastAPI(title="QuantDash Screener Service", lifespan=lifespan)

# ---------------------------------------------------------------------------
# 中间件
# ---------------------------------------------------------------------------
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
APP.add_middleware(RequestContextMiddleware)

# ---------------------------------------------------------------------------
# 统一异常处理
# ---------------------------------------------------------------------------
register_exception_handlers(APP)

# ---------------------------------------------------------------------------
# 注册模块路由
# ---------------------------------------------------------------------------
APP.include_router(SYNC_ROUTER)
APP.include_router(INTEGRATIONS_ROUTER)
APP.include_router(SKILL_LIBRARY_ROUTER)
APP.include_router(AUTH_ROUTER)
APP.include_router(WATCHLIST_ROUTER)
APP.include_router(SCREENER_ROUTER)

# ---------------------------------------------------------------------------
# 数据库初始化
# ---------------------------------------------------------------------------
init_auth_db()

# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(APP, host="0.0.0.0", port=7878)
