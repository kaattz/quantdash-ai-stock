"""认证模块：用户注册/登录/登出/改密、会话管理、自选股数据操作。

提供 ``ROUTER`` 和 ``require_user`` 依赖函数供其他模块使用。
所有数据库操作通过 ``shared/db.py`` 的 ``get_db_connection`` 进行。
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException

from server.models import (
    AuthRequest,
    AuthResponse,
    ChangePasswordRequest,
    MeResponse,
    MonitorCondition,
    WatchlistEntry,
)
from server.shared.db import get_db_connection
from server.shared.runtime import LOGGER

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
ROUTER = APIRouter(tags=["auth"])

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
AUTH_TOKEN_TTL = timedelta(days=7)


# ---------------------------------------------------------------------------
# 数据库初始化
# ---------------------------------------------------------------------------
def init_auth_db() -> None:
    """创建 users / sessions / watchlists 表（如不存在）。"""
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


# ---------------------------------------------------------------------------
# 密码哈希
# ---------------------------------------------------------------------------
def _hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    """返回 ``(salt_hex, hash_hex)``。"""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return salt.hex(), hashed.hex()


def _verify_password(password: str, salt_hex: str, password_hash: str) -> bool:
    _, hash_attempt = _hash_password(password, salt_hex=salt_hex)
    return hash_attempt == password_hash


# ---------------------------------------------------------------------------
# 用户名规范化
# ---------------------------------------------------------------------------
def _normalize_username(username: str) -> str:
    return username.strip()


# ---------------------------------------------------------------------------
# 会话清理
# ---------------------------------------------------------------------------
def _cleanup_sessions(conn: sqlite3.Connection) -> None:
    """删除已过期的会话记录。"""
    conn.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (datetime.utcnow().isoformat(),),
    )


# ---------------------------------------------------------------------------
# 用户 CRUD
# ---------------------------------------------------------------------------
def create_user(username: str, password: str) -> Tuple[int, str]:
    normalized = _normalize_username(username)
    if not normalized or len(normalized) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要 3 个字符")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 个字符")

    salt, password_hash = _hash_password(password)
    with get_db_connection() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (normalized, password_hash, salt, datetime.utcnow().isoformat()),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=400, detail="用户名已存在") from exc
    return int(cur.lastrowid), normalized


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    normalized = _normalize_username(username)
    with get_db_connection(row_factory=True) as conn:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (normalized,))
        return cur.fetchone()


def get_user_row_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with get_db_connection(row_factory=True) as conn:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    row = get_user_by_username(username)
    if not row:
        return None
    if not _verify_password(password, row["salt"], row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"]}


def update_user_password(user_id: int, old_password: str, new_password: str) -> None:
    row = get_user_row_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not _verify_password(old_password, row["salt"], row["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要 6 个字符")
    if new_password == old_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    salt, password_hash = _hash_password(new_password)
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (password_hash, salt, user_id),
        )


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------
def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    now = datetime.utcnow()
    expires_at = now + AUTH_TOKEN_TTL
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, token, now.isoformat(), expires_at.isoformat()),
        )
    return token


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    with get_db_connection(row_factory=True) as conn:
        _cleanup_sessions(conn)
        cur = conn.execute(
            """
            SELECT users.id, users.username, sessions.token, sessions.expires_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ? AND sessions.expires_at > ?
            """,
            (token, datetime.utcnow().isoformat()),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row["id"], "username": row["username"], "token": row["token"]}


def revoke_session(token: str) -> None:
    with get_db_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---------------------------------------------------------------------------
# Watchlist 数据操作
# ---------------------------------------------------------------------------
def get_user_watchlist(user_id: int) -> List[Dict[str, Any]]:
    with get_db_connection(row_factory=True) as conn:
        cur = conn.execute("SELECT data FROM watchlists WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return []
        try:
            payload = json.loads(row["data"]) or []
            return payload if isinstance(payload, list) else []
        except json.JSONDecodeError:
            LOGGER.warning("Failed to decode watchlist for user %s", user_id)
            return []


def save_user_watchlist(user_id: int, items: List[Dict[str, Any]]) -> None:
    payload = json.dumps(items, ensure_ascii=False)
    now = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlists (user_id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (user_id, payload, now),
        )


def ensure_condition_defaults(condition: MonitorCondition) -> MonitorCondition:
    """为监控条件填充默认值。"""
    if not condition.id:
        condition.id = secrets.token_hex(8)
    if condition.type == "volume_ratio":
        if not condition.ratio or condition.ratio <= 0:
            condition.ratio = 2.0
        if not condition.lookbackDays or condition.lookbackDays < 3:
            condition.lookbackDays = 5
    if condition.type == "price_touch_ma":
        if condition.maWindow not in (5, 10, 20):
            condition.maWindow = 5
        if not condition.tolerancePct or condition.tolerancePct <= 0:
            condition.tolerancePct = 0.003
    return condition


def sanitize_watchlist_entry(entry: WatchlistEntry) -> Dict[str, Any]:
    """清理单个自选股条目，填充监控条件默认值并移除信号数据。"""
    sanitized_conditions: List[Dict[str, Any]] = []
    for condition in entry.monitorConditions:
        sanitized = ensure_condition_defaults(condition)
        sanitized_conditions.append(sanitized.model_dump())
    payload = entry.model_dump()
    payload.pop("monitorSignals", None)
    payload["monitorConditions"] = sanitized_conditions
    return payload


def sanitize_watchlist_payload(items: List[WatchlistEntry]) -> List[Dict[str, Any]]:
    """清理自选股列表。"""
    return [sanitize_watchlist_entry(item) for item in items]


# ---------------------------------------------------------------------------
# 认证依赖 & Token 提取
# ---------------------------------------------------------------------------
def extract_token(authorization: Optional[str]) -> str:
    """从 Authorization 头提取 Bearer token。"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少授权信息")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(status_code=401, detail="授权格式不正确")
    return value.strip()


async def require_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """FastAPI 依赖：验证 Bearer token 并返回当前用户信息。

    其他模块可通过 ``Depends(require_user)`` 保护路由。
    """
    token = extract_token(authorization)
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return user


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@ROUTER.post("/auth/register", response_model=AuthResponse)
async def register_endpoint(payload: AuthRequest):
    user_id, normalized = create_user(payload.username, payload.password)
    token = create_session(user_id)
    return AuthResponse(token=token, username=normalized)


@ROUTER.post("/auth/login", response_model=AuthResponse)
async def login_endpoint(payload: AuthRequest):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_session(user["id"])
    return AuthResponse(token=token, username=user["username"])


@ROUTER.get("/auth/me", response_model=MeResponse)
async def me_endpoint(current_user: Dict[str, Any] = Depends(require_user)):
    return MeResponse(username=current_user["username"])


@ROUTER.post("/auth/logout")
async def logout_endpoint(current_user: Dict[str, Any] = Depends(require_user)):
    revoke_session(current_user["token"])
    return {"status": "ok"}


@ROUTER.post("/auth/change-password")
async def change_password_endpoint(
    payload: ChangePasswordRequest,
    current_user: Dict[str, Any] = Depends(require_user),
):
    update_user_password(current_user["id"], payload.oldPassword, payload.newPassword)
    return {"status": "ok"}
