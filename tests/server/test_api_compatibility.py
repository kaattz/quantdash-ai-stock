"""API 路径兼容性集成测试 — 验证所有 15 个 API 路径存在且可访问。

使用 FastAPI TestClient 验证迁移后的模块化架构保持 API 兼容性。
**Validates: Requirements 10.1, 10.2, 10.3, 10.4**
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import APP
from server.modules.auth import init_auth_db
import server.shared.runtime as _runtime
import server.shared.db as _db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _temp_db(tmp_path: Path):
    """为每个测试使用独立的临时数据库，避免污染。"""
    tmp_db = tmp_path / "test_compat.db"
    original_runtime = _runtime.AUTH_DB_PATH
    original_db = _db.AUTH_DB_PATH
    try:
        _runtime.AUTH_DB_PATH = tmp_db
        _db.AUTH_DB_PATH = tmp_db
        init_auth_db()
        yield
    finally:
        _runtime.AUTH_DB_PATH = original_runtime
        _db.AUTH_DB_PATH = original_db


@pytest.fixture()
def client():
    """创建 TestClient 实例。"""
    return TestClient(APP, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 需求 10.1: 所有 API 路径存在性验证
# 路径存在 = 不返回 404 或 405（可以返回 401、422、200 等）
# ---------------------------------------------------------------------------

class TestAPIPathsExist:
    """验证所有 15 个 API 路径存在且可访问（不返回 404/405）。"""

    def test_get_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_post_auth_register(self, client: TestClient):
        # 无 body → 422（校验错误），但路径存在
        resp = client.post("/auth/register")
        assert resp.status_code not in (404, 405)

    def test_post_auth_login(self, client: TestClient):
        resp = client.post("/auth/login")
        assert resp.status_code not in (404, 405)

    def test_get_auth_me(self, client: TestClient):
        # 无 token → 401
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_post_auth_logout(self, client: TestClient):
        resp = client.post("/auth/logout")
        assert resp.status_code == 401

    def test_post_auth_change_password(self, client: TestClient):
        resp = client.post("/auth/change-password")
        assert resp.status_code == 401

    def test_get_watchlist(self, client: TestClient):
        resp = client.get("/watchlist")
        assert resp.status_code == 401

    def test_put_watchlist(self, client: TestClient):
        resp = client.put("/watchlist")
        assert resp.status_code == 401

    def test_get_screener(self, client: TestClient):
        resp = client.get("/screener")
        assert resp.status_code == 401

    def test_get_sync_runtime_status(self, client: TestClient):
        resp = client.get("/sync/runtime-status")
        assert resp.status_code == 200

    def test_post_sync_startup_check(self, client: TestClient):
        resp = client.post("/sync/startup-check")
        assert resp.status_code not in (404, 405)

    def test_get_integrations_feishu_config(self, client: TestClient):
        resp = client.get("/integrations/feishu/config")
        assert resp.status_code not in (404, 405)

    def test_put_integrations_feishu_config(self, client: TestClient):
        # 无 body → 422
        resp = client.put("/integrations/feishu/config")
        assert resp.status_code not in (404, 405)

    def test_post_integrations_feishu_test(self, client: TestClient):
        # 无 body → 422
        resp = client.post("/integrations/feishu/test")
        assert resp.status_code not in (404, 405)

    def test_post_integrations_model_invoke(self, client: TestClient):
        # 无 body → 422
        resp = client.post("/integrations/model/invoke")
        assert resp.status_code not in (404, 405)


# ---------------------------------------------------------------------------
# 需求 10.4: CORS 配置验证
# ---------------------------------------------------------------------------

class TestCORSConfiguration:
    """验证 CORS 配置为 allow_origins=["*"]。"""

    def test_cors_allows_any_origin(self, client: TestClient):
        """发送 OPTIONS 预检请求，验证任意 Origin 都被允许。

        注意：当 allow_credentials=True 时，CORSMiddleware 会回显请求的 Origin
        而非返回 "*"（这是 CORS 规范要求的行为）。allow_origins=["*"] 表示接受
        任意来源，但响应头中会反映具体的请求来源。
        """
        test_origin = "http://localhost:3000"
        resp = client.options(
            "/health",
            headers={
                "Origin": test_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        actual = resp.headers.get("access-control-allow-origin")
        # 接受 "*" 或回显的具体 origin（credentials 模式下的标准行为）
        assert actual in ("*", test_origin), (
            f"CORS 应允许任意来源，实际返回: {actual}"
        )

    def test_cors_allows_all_methods(self, client: TestClient):
        """验证 CORS 允许所有 HTTP 方法。"""
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "PUT",
            },
        )
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        # CORSMiddleware 配置了 allow_methods=["*"]
        assert "PUT" in allow_methods or "*" in allow_methods

    def test_cors_allows_all_headers(self, client: TestClient):
        """验证 CORS 允许所有请求头。"""
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        allow_headers = resp.headers.get("access-control-allow-headers", "")
        assert "authorization" in allow_headers.lower() or "*" in allow_headers


# ---------------------------------------------------------------------------
# 需求 10.3: 端口配置验证
# ---------------------------------------------------------------------------

class TestPortConfiguration:
    """验证 app.py 中配置的端口为 7878。"""

    def test_uvicorn_port_is_7878(self):
        """通过检查 app.py 源码确认默认端口为 7878。"""
        import inspect
        import server.app as app_module

        source = inspect.getsource(app_module)
        assert "7878" in source, "app.py 应配置端口 7878"
