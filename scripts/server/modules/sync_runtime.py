"""同步运行时模块：数据同步任务的启动和状态管理。

提供 ``ROUTER``，包含 3 个路由：
- GET  /health              — 健康检查
- GET  /sync/runtime-status — 查询同步任务运行状态
- POST /sync/startup-check  — 启动数据同步子进程
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException, Query

import server.shared.runtime as _runtime
from server.models import SyncTriggerResponse
from server.shared.runtime import LOGGER, ROOT_DIR, SYNC_RUNTIME_STATE

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

ROUTER = APIRouter(tags=["system"])


# ---------------------------------------------------------------------------
# 同步管理函数
# ---------------------------------------------------------------------------


def get_sync_runtime_state() -> Dict[str, Any]:
    """返回当前同步任务的运行状态快照。"""
    return dict(SYNC_RUNTIME_STATE)


async def _watch_sync_process(process: asyncio.subprocess.Process) -> None:
    """监视同步子进程，完成后更新运行时状态并清除进程引用。"""
    try:
        await process.wait()
        SYNC_RUNTIME_STATE["state"] = "idle"
        SYNC_RUNTIME_STATE["finishedAt"] = datetime.now(
            timezone(timedelta(hours=8))
        ).isoformat()
        SYNC_RUNTIME_STATE["exitCode"] = process.returncode
        SYNC_RUNTIME_STATE["error"] = (
            None
            if process.returncode == 0
            else f"process exited with code {process.returncode}"
        )
        SYNC_RUNTIME_STATE["pid"] = None
    except Exception as exc:  # pragma: no cover
        SYNC_RUNTIME_STATE["state"] = "idle"
        SYNC_RUNTIME_STATE["finishedAt"] = datetime.now(
            timezone(timedelta(hours=8))
        ).isoformat()
        SYNC_RUNTIME_STATE["exitCode"] = -1
        SYNC_RUNTIME_STATE["error"] = str(exc)
        SYNC_RUNTIME_STATE["pid"] = None
    finally:
        _runtime.SYNC_PROCESS = None


async def launch_startup_sync(mode: str = "startup") -> Dict[str, Any]:
    """启动数据同步子进程，返回当前运行状态。

    如果已有同步任务正在执行，抛出 HTTP 409。
    """
    if _runtime.SYNC_PROCESS and _runtime.SYNC_PROCESS.returncode is None:
        raise HTTPException(status_code=409, detail="已有同步任务正在执行")

    env = os.environ.copy()
    env["STARTUP_AUTO_SYNC"] = "1"
    env["STARTUP_SYNC_MODE"] = mode
    process = await asyncio.create_subprocess_exec(
        "node",
        str(ROOT_DIR / "scripts" / "ensureStartupData.js"),
        cwd=str(ROOT_DIR),
        env=env,
    )
    _runtime.SYNC_PROCESS = process
    SYNC_RUNTIME_STATE["state"] = "running"
    SYNC_RUNTIME_STATE["trigger"] = "startup-sync"
    SYNC_RUNTIME_STATE["mode"] = mode
    SYNC_RUNTIME_STATE["startedAt"] = datetime.now(
        timezone(timedelta(hours=8))
    ).isoformat()
    SYNC_RUNTIME_STATE["finishedAt"] = None
    SYNC_RUNTIME_STATE["exitCode"] = None
    SYNC_RUNTIME_STATE["error"] = None
    SYNC_RUNTIME_STATE["pid"] = process.pid
    asyncio.create_task(_watch_sync_process(process))
    return get_sync_runtime_state()


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@ROUTER.get("/health")
async def health():
    """健康检查端点。"""
    return {"status": "ok"}


@ROUTER.get("/sync/runtime-status")
async def sync_runtime_status():
    """查询同步任务运行状态。"""
    return get_sync_runtime_state()


@ROUTER.post("/sync/startup-check", response_model=SyncTriggerResponse)
async def trigger_startup_sync(
    mode: Literal["startup", "market", "offline"] = Query("startup"),
):
    """启动数据同步子进程。"""
    state = await launch_startup_sync(mode)
    return SyncTriggerResponse(
        status=state["state"],
        trigger=state["trigger"],
        mode=state["mode"],
        startedAt=state["startedAt"],
        pid=state["pid"],
    )
