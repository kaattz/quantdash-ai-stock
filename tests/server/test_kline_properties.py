"""K 线多源回退属性测试 — Property 10: K 线多源回退保证

当所有外部数据源不可用时，fetch_kline 应返回非空 mock 数据。
# Feature: backend-modular-migration, Property 10: K 线多源回退保证
# **Validates: Requirements 4.4, 4.7**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from server.modules.screener_kline_data import fetch_kline

# ---------------------------------------------------------------------------
# 策略：有效的 A 股代码（6 位数字字符串）
# ---------------------------------------------------------------------------
# 沪市主板 60xxxx、深市主板 00xxxx、创业板 30xxxx
_stock_symbol_st = st.one_of(
    st.from_regex(r"6\d{5}", fullmatch=True),
    st.from_regex(r"0\d{5}", fullmatch=True),
    st.from_regex(r"3\d{5}", fullmatch=True),
)

# 模拟数据源失败的方式：抛出 ConnectTimeout 或返回空列表
_failure_mode_st = st.sampled_from(["timeout", "empty"])

EXPECTED_KEYS = {"date", "open", "close", "high", "low", "volume"}

MODULE_PATH = "server.modules.screener_kline_data"


def _make_side_effect(mode: str):
    """根据失败模式返回对应的 mock side_effect 或 return_value。"""
    if mode == "timeout":
        return AsyncMock(side_effect=httpx.ConnectTimeout("mocked timeout"))
    else:
        return AsyncMock(return_value=[])


# ---------------------------------------------------------------------------
# Property 10: K 线多源回退保证
# Feature: backend-modular-migration, Property 10: K 线多源回退保证
# **Validates: Requirements 4.4, 4.7**
# ---------------------------------------------------------------------------
@pytest.mark.asyncio(loop_scope="function")
@settings(max_examples=10, deadline=None)
@given(symbol=_stock_symbol_st, mode=_failure_mode_st)
async def test_kline_fallback_returns_mock_data(symbol: str, mode: str):
    """当所有外部数据源不可用时，fetch_kline 应返回非空 mock 数据，
    且每条记录包含 date/open/close/high/low/volume 字段。"""
    mock_eastmoney = _make_side_effect(mode)
    mock_sina = _make_side_effect(mode)
    mock_tencent = _make_side_effect(mode)

    with (
        patch(f"{MODULE_PATH}.fetch_kline_from_eastmoney", mock_eastmoney),
        patch(f"{MODULE_PATH}.fetch_kline_from_sina", mock_sina),
        patch(f"{MODULE_PATH}.fetch_kline_from_tencent", mock_tencent),
    ):
        result = await fetch_kline(symbol)

    # 结果应为非空列表
    assert isinstance(result, list), f"fetch_kline 应返回列表，实际返回 {type(result)}"
    assert len(result) > 0, "所有数据源失败时，fetch_kline 应返回非空 mock 数据"

    # 每条记录应包含预期的键
    for i, item in enumerate(result):
        assert isinstance(item, dict), f"第 {i} 条记录应为字典，实际为 {type(item)}"
        missing = EXPECTED_KEYS - item.keys()
        assert not missing, f"第 {i} 条记录缺少字段: {missing}"
