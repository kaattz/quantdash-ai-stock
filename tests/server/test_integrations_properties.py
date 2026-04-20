"""集成模块属性测试 — Property 8/9

Property 8: 飞书配置 Round-Trip — 保存后读取返回相同的 appId 和 aiBaseUrl
Property 9: 代理异常格式化非空 — 对任意 httpx 异常，_format_proxy_exception 返回非空字符串

# Feature: backend-modular-migration, Property 8/9
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import httpx
from hypothesis import given, settings
from hypothesis import strategies as st

from server.models import FeishuBotConfigPayload
from server.modules.integrations import (
    _format_proxy_exception,
    _load_feishu_bot_config,
    _save_feishu_bot_config,
)
import server.modules.integrations as _integrations


# ---------------------------------------------------------------------------
# 策略：随机 appId（字母数字，5-20 字符）
# ---------------------------------------------------------------------------
alphanum_st = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ),
    min_size=5,
    max_size=20,
)

# 策略：随机 aiBaseUrl
ai_base_url_st = alphanum_st.map(lambda s: f"http://test-{s}.example.com")


# ---------------------------------------------------------------------------
# Property 8: 飞书配置 Round-Trip
# Feature: backend-modular-migration, Property 8: 飞书配置 Round-Trip
# **Validates: Requirements 6.1, 6.2**
# ---------------------------------------------------------------------------
@settings(max_examples=10, deadline=None)
@given(app_id=alphanum_st, ai_base_url=ai_base_url_st)
def test_feishu_config_round_trip(app_id: str, ai_base_url: str):
    """保存后读取返回相同的 appId 和 aiBaseUrl。"""
    # 创建临时目录用于隔离 .env.local
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_env_path = Path(tmp_dir) / ".env.local"
        original_path = _integrations.ENV_LOCAL_PATH

        # 保存原始环境变量，测试后恢复
        env_keys = list(_integrations.FEISHU_ENV_KEY_MAP.values())
        saved_env = {k: os.environ.get(k) for k in env_keys}

        try:
            # 将 ENV_LOCAL_PATH 指向临时文件
            _integrations.ENV_LOCAL_PATH = tmp_env_path

            # 构造 payload
            payload = FeishuBotConfigPayload(
                appId=app_id,
                aiBaseUrl=ai_base_url,
            )

            # 保存配置
            _save_feishu_bot_config(payload)

            # 读取配置
            loaded = _load_feishu_bot_config()

            # 断言：appId 和 aiBaseUrl 一致
            assert loaded.appId == app_id, (
                f"appId 不一致: 期望 {app_id!r}，实际 {loaded.appId!r}"
            )
            assert loaded.aiBaseUrl == ai_base_url, (
                f"aiBaseUrl 不一致: 期望 {ai_base_url!r}，实际 {loaded.aiBaseUrl!r}"
            )
        finally:
            # 恢复 ENV_LOCAL_PATH
            _integrations.ENV_LOCAL_PATH = original_path
            # 恢复环境变量
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


# ---------------------------------------------------------------------------
# 策略：httpx 异常类型
# ---------------------------------------------------------------------------
httpx_exception_st = st.sampled_from([
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.ProxyError,
])

exception_message_st = st.text(min_size=0, max_size=50)


# ---------------------------------------------------------------------------
# Property 9: 代理异常格式化非空
# Feature: backend-modular-migration, Property 9: 代理异常格式化非空
# **Validates: Requirements 6.5**
# ---------------------------------------------------------------------------
@settings(max_examples=10)
@given(exc_cls=httpx_exception_st, msg=exception_message_st)
def test_format_proxy_exception_non_empty(exc_cls: type, msg: str):
    """对任意 httpx 异常，_format_proxy_exception 返回非空字符串。"""
    exc = exc_cls(msg)
    result = _format_proxy_exception(exc)

    assert isinstance(result, str), (
        f"结果应为 str，实际 {type(result)}"
    )
    assert len(result) > 0, (
        f"结果不应为空字符串，异常类型: {exc_cls.__name__}，消息: {msg!r}"
    )
