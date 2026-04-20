"""认证模块属性测试 — Property 1: 认证 Round-Trip

使用 hypothesis 对注册→登录→/auth/me 的完整流程进行属性验证。
# Feature: backend-modular-migration, Property 1: 认证 Round-Trip
# **Validates: Requirements 3.1, 3.2, 3.4**
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from server.modules.auth import ROUTER, init_auth_db
import server.shared.runtime as _runtime
import server.shared.db as _db


# ---------------------------------------------------------------------------
# 策略：有效用户名（字母数字，3-20 字符）和密码（6-30 字符）
# ---------------------------------------------------------------------------
valid_username_st = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ),
    min_size=3,
    max_size=20,
)

valid_password_st = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%"
    ),
    min_size=6,
    max_size=30,
)


def _patch_db_path(tmp_db: Path):
    """同时修补 runtime 和 db 模块中的 AUTH_DB_PATH（db.py 通过 from import 持有独立引用）。"""
    _runtime.AUTH_DB_PATH = tmp_db
    _db.AUTH_DB_PATH = tmp_db


# ---------------------------------------------------------------------------
# Property 1: 认证 Round-Trip
# Feature: backend-modular-migration, Property 1: 认证 Round-Trip
# **Validates: Requirements 3.1, 3.2, 3.4**
# ---------------------------------------------------------------------------
@settings(max_examples=10, deadline=None)
@given(username=valid_username_st, password=valid_password_st)
def test_auth_round_trip(username: str, password: str):
    """注册后登录再调用 /auth/me，返回的 username 应一致。"""
    # 每次迭代使用全新的临时数据库，确保隔离
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    tmp_db = Path(tmp_path)

    original_runtime = _runtime.AUTH_DB_PATH
    original_db = _db.AUTH_DB_PATH
    try:
        _patch_db_path(tmp_db)
        init_auth_db()

        app = FastAPI()
        app.include_router(ROUTER)
        client = TestClient(app)

        # 1. 注册
        reg_resp = client.post(
            "/auth/register",
            json={"username": username, "password": password},
        )
        assert reg_resp.status_code == 200, f"注册失败: {reg_resp.text}"
        reg_data = reg_resp.json()
        assert "token" in reg_data
        assert reg_data["username"] == username

        # 2. 登录
        login_resp = client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        assert login_resp.status_code == 200, f"登录失败: {login_resp.text}"
        login_data = login_resp.json()
        token = login_data["token"]
        assert login_data["username"] == username

        # 3. 调用 /auth/me
        me_resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200, f"/auth/me 失败: {me_resp.text}"
        me_data = me_resp.json()
        assert me_data["username"] == username
    finally:
        _runtime.AUTH_DB_PATH = original_runtime
        _db.AUTH_DB_PATH = original_db
        tmp_db.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Property 2: 错误凭据拒绝
# Feature: backend-modular-migration, Property 2: 错误凭据拒绝
# **Validates: Requirements 3.3**
# ---------------------------------------------------------------------------
@settings(max_examples=10, deadline=None)
@given(
    username=valid_username_st,
    password=valid_password_st,
    wrong_password=valid_password_st,
)
def test_wrong_credentials_rejected(
    username: str, password: str, wrong_password: str
):
    """使用错误密码登录应返回 HTTP 401。"""
    from hypothesis import assume

    assume(wrong_password != password)

    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    tmp_db = Path(tmp_path)

    original_runtime = _runtime.AUTH_DB_PATH
    original_db = _db.AUTH_DB_PATH
    try:
        _patch_db_path(tmp_db)
        init_auth_db()

        app = FastAPI()
        app.include_router(ROUTER)
        client = TestClient(app)

        # 1. 注册
        reg_resp = client.post(
            "/auth/register",
            json={"username": username, "password": password},
        )
        assert reg_resp.status_code == 200, f"注册失败: {reg_resp.text}"

        # 2. 使用错误密码登录
        login_resp = client.post(
            "/auth/login",
            json={"username": username, "password": wrong_password},
        )
        assert login_resp.status_code == 401, (
            f"错误密码应返回 401，实际返回 {login_resp.status_code}: {login_resp.text}"
        )
    finally:
        _runtime.AUTH_DB_PATH = original_runtime
        _db.AUTH_DB_PATH = original_db
        tmp_db.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Property 3: 登出撤销 Token
# Feature: backend-modular-migration, Property 3: 登出撤销 Token
# **Validates: Requirements 3.5**
# ---------------------------------------------------------------------------
@settings(max_examples=10, deadline=None)
@given(username=valid_username_st, password=valid_password_st)
def test_logout_revokes_token(username: str, password: str):
    """登出后使用同一 token 调用 /auth/me 应返回 HTTP 401。"""
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    tmp_db = Path(tmp_path)

    original_runtime = _runtime.AUTH_DB_PATH
    original_db = _db.AUTH_DB_PATH
    try:
        _patch_db_path(tmp_db)
        init_auth_db()

        app = FastAPI()
        app.include_router(ROUTER)
        client = TestClient(app)

        # 1. 注册
        reg_resp = client.post(
            "/auth/register",
            json={"username": username, "password": password},
        )
        assert reg_resp.status_code == 200, f"注册失败: {reg_resp.text}"

        # 2. 登录获取 token
        login_resp = client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        assert login_resp.status_code == 200, f"登录失败: {login_resp.text}"
        token = login_resp.json()["token"]

        # 3. 登出
        logout_resp = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_resp.status_code == 200, f"登出失败: {logout_resp.text}"

        # 4. 使用已撤销的 token 调用 /auth/me，应返回 401
        me_resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 401, (
            f"登出后 /auth/me 应返回 401，实际返回 {me_resp.status_code}: {me_resp.text}"
        )
    finally:
        _runtime.AUTH_DB_PATH = original_runtime
        _db.AUTH_DB_PATH = original_db
        tmp_db.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Property 4: 改密 Round-Trip
# Feature: backend-modular-migration, Property 4: 改密 Round-Trip
# **Validates: Requirements 3.6**
# ---------------------------------------------------------------------------
@settings(max_examples=10, deadline=None)
@given(
    username=valid_username_st,
    old_password=valid_password_st,
    new_password=valid_password_st,
)
def test_change_password_round_trip(
    username: str, old_password: str, new_password: str
):
    """改密后新密码登录成功，旧密码登录返回 401。"""
    from hypothesis import assume

    assume(old_password != new_password)

    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    tmp_db = Path(tmp_path)

    original_runtime = _runtime.AUTH_DB_PATH
    original_db = _db.AUTH_DB_PATH
    try:
        _patch_db_path(tmp_db)
        init_auth_db()

        app = FastAPI()
        app.include_router(ROUTER)
        client = TestClient(app)

        # 1. 注册
        reg_resp = client.post(
            "/auth/register",
            json={"username": username, "password": old_password},
        )
        assert reg_resp.status_code == 200, f"注册失败: {reg_resp.text}"

        # 2. 登录获取 token
        login_resp = client.post(
            "/auth/login",
            json={"username": username, "password": old_password},
        )
        assert login_resp.status_code == 200, f"登录失败: {login_resp.text}"
        token = login_resp.json()["token"]

        # 3. 改密
        change_resp = client.post(
            "/auth/change-password",
            json={"oldPassword": old_password, "newPassword": new_password},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert change_resp.status_code == 200, f"改密失败: {change_resp.text}"

        # 4. 使用新密码登录 → 应成功
        new_login_resp = client.post(
            "/auth/login",
            json={"username": username, "password": new_password},
        )
        assert new_login_resp.status_code == 200, (
            f"改密后新密码登录应成功，实际返回 {new_login_resp.status_code}: {new_login_resp.text}"
        )

        # 5. 使用旧密码登录 → 应返回 401
        old_login_resp = client.post(
            "/auth/login",
            json={"username": username, "password": old_password},
        )
        assert old_login_resp.status_code == 401, (
            f"改密后旧密码登录应返回 401，实际返回 {old_login_resp.status_code}: {old_login_resp.text}"
        )
    finally:
        _runtime.AUTH_DB_PATH = original_runtime
        _db.AUTH_DB_PATH = original_db
        tmp_db.unlink(missing_ok=True)
