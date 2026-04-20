"""全局共享状态，所有模块通过 ``from server.shared.runtime import ...`` 访问。"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from data_paths import DATA_DIR, SYSTEM_DIR

# ---------------------------------------------------------------------------
# HTTP 客户端
# ---------------------------------------------------------------------------
MODEL_PROXY_TIMEOUT_SECONDS = float(
    os.environ.get("MODEL_PROXY_TIMEOUT_SECONDS", "120")
)
MODEL_PROXY_CONNECT_TIMEOUT_SECONDS = float(
    os.environ.get("MODEL_PROXY_CONNECT_TIMEOUT_SECONDS", "15")
)
HTTP_TIMEOUT = httpx.Timeout(
    MODEL_PROXY_TIMEOUT_SECONDS,
    connect=MODEL_PROXY_CONNECT_TIMEOUT_SECONDS,
)
CLIENT: httpx.AsyncClient = httpx.AsyncClient(timeout=HTTP_TIMEOUT)

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
LOGGER: logging.Logger = logging.getLogger("quantdash.screener")

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR.mkdir(parents=True, exist_ok=True)
SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
AUTH_DB_PATH: Path = SYSTEM_DIR / "auth.db"

# ---------------------------------------------------------------------------
# 同步运行时状态
# ---------------------------------------------------------------------------
SYNC_PROCESS: Optional[asyncio.subprocess.Process] = None
SYNC_RUNTIME_STATE: Dict[str, Any] = {
    "state": "idle",
    "trigger": None,
    "mode": None,
    "startedAt": None,
    "finishedAt": None,
    "exitCode": None,
    "error": None,
    "pid": None,
}


# ---------------------------------------------------------------------------
# 应用生命周期管理
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # noqa: ANN001
    """FastAPI lifespan：启动时初始化资源，关闭时清理 HTTP 客户端。"""
    try:
        yield
    finally:
        await CLIENT.aclose()
