"""自选股模块属性测试 — Property 5/6/7

Property 5: 自选股 Round-Trip — PUT 后 GET 返回相同数量条目，symbol 和 name 一致
Property 6: 监控条件默认值填充 — ensure_condition_defaults 处理后各字段满足约束
Property 7: 监控信号计算有效性 — 返回的 MonitorSignal 字段与输入条件一致

# Feature: backend-modular-migration, Property 5/6/7
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from server.models import MonitorCondition, MonitorSignal, WatchlistEntry
from server.modules.auth import ROUTER as AUTH_ROUTER, init_auth_db
from server.modules.watchlist import ROUTER as WATCHLIST_ROUTER, evaluate_monitor_condition
from server.modules.auth import ensure_condition_defaults
import server.shared.runtime as _runtime
import server.shared.db as _db


# ---------------------------------------------------------------------------
# DB 隔离辅助（与 test_auth_properties.py 一致）
# ---------------------------------------------------------------------------
def _patch_db_path(tmp_db: Path):
    """同时修补 runtime 和 db 模块中的 AUTH_DB_PATH。"""
    _runtime.AUTH_DB_PATH = tmp_db
    _db.AUTH_DB_PATH = tmp_db


# ---------------------------------------------------------------------------
# 策略：有效用户名和密码
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


# ---------------------------------------------------------------------------
# 策略：有效的 WatchlistEntry 列表
# ---------------------------------------------------------------------------
valid_symbol_st = st.from_regex(r"[0-9]{6}", fullmatch=True)
valid_name_st = st.text(
    alphabet=st.sampled_from("测试股票ABCDEFG甲乙丙丁"),
    min_size=2,
    max_size=8,
)

watchlist_entry_st = st.fixed_dictionaries({
    "symbol": valid_symbol_st,
    "name": valid_name_st,
    "price": st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    "pctChange": st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    "volume": st.just("100000"),
    "turnover": st.just("50000000"),
    "industry": st.just("科技"),
    "concepts": st.just(["概念A"]),
})

watchlist_entries_st = st.lists(watchlist_entry_st, min_size=1, max_size=5)


# ---------------------------------------------------------------------------
# Property 5: 自选股 Round-Trip
# Feature: backend-modular-migration, Property 5: 自选股 Round-Trip
# **Validates: Requirements 5.1, 5.3**
# ---------------------------------------------------------------------------
@settings(max_examples=10, deadline=None)
@given(
    username=valid_username_st,
    password=valid_password_st,
    entries=watchlist_entries_st,
)
def test_watchlist_round_trip(username: str, password: str, entries: List[Dict]):
    """PUT 后 GET 返回相同数量条目，symbol 和 name 一致。"""
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    tmp_db = Path(tmp_path)

    original_runtime = _runtime.AUTH_DB_PATH
    original_db = _db.AUTH_DB_PATH
    try:
        _patch_db_path(tmp_db)
        init_auth_db()

        app = FastAPI()
        app.include_router(AUTH_ROUTER)
        app.include_router(WATCHLIST_ROUTER)
        client = TestClient(app)

        # 1. 注册用户
        reg_resp = client.post(
            "/auth/register",
            json={"username": username, "password": password},
        )
        assert reg_resp.status_code == 200, f"注册失败: {reg_resp.text}"
        token = reg_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. PUT /watchlist
        put_resp = client.put("/watchlist", json=entries, headers=headers)
        assert put_resp.status_code == 200, f"PUT /watchlist 失败: {put_resp.text}"

        # 3. GET /watchlist（不含信号）
        get_resp = client.get("/watchlist", headers=headers)
        assert get_resp.status_code == 200, f"GET /watchlist 失败: {get_resp.text}"
        result = get_resp.json()

        # 断言：数量一致
        assert len(result) == len(entries), (
            f"条目数量不一致: 期望 {len(entries)}，实际 {len(result)}"
        )

        # 断言：每个条目的 symbol 和 name 一致
        for i, (expected, actual) in enumerate(zip(entries, result)):
            assert actual["symbol"] == expected["symbol"], (
                f"第 {i} 条 symbol 不一致: 期望 {expected['symbol']}，实际 {actual['symbol']}"
            )
            assert actual["name"] == expected["name"], (
                f"第 {i} 条 name 不一致: 期望 {expected['name']}，实际 {actual['name']}"
            )
    finally:
        _runtime.AUTH_DB_PATH = original_runtime
        _db.AUTH_DB_PATH = original_db
        tmp_db.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 策略：MonitorCondition（可能缺少字段或无效值）
# ---------------------------------------------------------------------------
monitor_condition_type_st = st.sampled_from(["volume_ratio", "price_touch_ma"])

# 生成可能缺失/无效的 MonitorCondition 用于测试默认值填充
monitor_condition_st = st.builds(
    MonitorCondition,
    id=st.one_of(st.none(), st.just(""), st.text(min_size=1, max_size=16)),
    type=monitor_condition_type_st,
    enabled=st.just(True),
    ratio=st.one_of(st.none(), st.floats(min_value=-5.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
    lookbackDays=st.one_of(st.none(), st.integers(min_value=0, max_value=30)),
    maWindow=st.one_of(st.none(), st.sampled_from([1, 3, 5, 7, 10, 15, 20, 25])),
    tolerancePct=st.one_of(st.none(), st.floats(min_value=-0.01, max_value=0.1, allow_nan=False, allow_infinity=False)),
)


# ---------------------------------------------------------------------------
# Property 6: 监控条件默认值填充
# Feature: backend-modular-migration, Property 6: 监控条件默认值填充
# **Validates: Requirements 5.3**
# ---------------------------------------------------------------------------
@settings(max_examples=10)
@given(condition=monitor_condition_st)
def test_ensure_condition_defaults(condition: MonitorCondition):
    """ensure_condition_defaults 处理后各字段满足约束。"""
    result = ensure_condition_defaults(condition)

    # id 非空
    assert result.id, "id 应非空"

    if result.type == "volume_ratio":
        assert result.ratio is not None and result.ratio > 0, (
            f"volume_ratio 的 ratio 应 > 0，实际 {result.ratio}"
        )
        assert result.lookbackDays is not None and result.lookbackDays >= 3, (
            f"volume_ratio 的 lookbackDays 应 >= 3，实际 {result.lookbackDays}"
        )

    if result.type == "price_touch_ma":
        assert result.maWindow in (5, 10, 20), (
            f"price_touch_ma 的 maWindow 应在 {{5, 10, 20}} 中，实际 {result.maWindow}"
        )
        assert result.tolerancePct is not None and result.tolerancePct > 0, (
            f"price_touch_ma 的 tolerancePct 应 > 0，实际 {result.tolerancePct}"
        )


# ---------------------------------------------------------------------------
# 策略：K 线序列和有效索引
# ---------------------------------------------------------------------------
kline_entry_st = st.fixed_dictionaries({
    "date": st.from_regex(r"2024-0[1-9]-[012][0-9]", fullmatch=True),
    "open": st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    "close": st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    "high": st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    "low": st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    "volume": st.floats(min_value=1000.0, max_value=100000000.0, allow_nan=False, allow_infinity=False),
})

kline_series_st = st.lists(kline_entry_st, min_size=5, max_size=30)

# 启用的 MonitorCondition（确保有效）
enabled_condition_st = st.builds(
    MonitorCondition,
    id=st.text(
        alphabet=st.sampled_from("abcdef0123456789"),
        min_size=8,
        max_size=16,
    ),
    type=monitor_condition_type_st,
    enabled=st.just(True),
    ratio=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
    lookbackDays=st.integers(min_value=3, max_value=10),
    maWindow=st.sampled_from([5, 10, 20]),
    tolerancePct=st.floats(min_value=0.001, max_value=0.05, allow_nan=False, allow_infinity=False),
)


# ---------------------------------------------------------------------------
# Property 7: 监控信号计算有效性
# Feature: backend-modular-migration, Property 7: 监控信号计算有效性
# **Validates: Requirements 5.4**
# ---------------------------------------------------------------------------
@settings(max_examples=10)
@given(
    series=kline_series_st,
    condition=enabled_condition_st,
)
def test_monitor_signal_validity(series: List[Dict], condition: MonitorCondition):
    """返回的 MonitorSignal 字段与输入条件一致。"""
    # 使用有效索引（序列中间或末尾）
    index = len(series) - 1

    result = evaluate_monitor_condition(series, index, condition, quote=None)

    # 结果应为 MonitorSignal
    assert isinstance(result, MonitorSignal), (
        f"结果应为 MonitorSignal，实际 {type(result)}"
    )

    # conditionType 与输入条件的 type 一致
    assert result.conditionType == condition.type, (
        f"conditionType 不一致: 期望 {condition.type}，实际 {result.conditionType}"
    )

    # checkedAt 非空
    assert result.checkedAt, "checkedAt 应非空"

    # message 非空
    assert result.message, "message 应非空"
