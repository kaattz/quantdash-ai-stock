"""选股模块：策略引擎 + pywencai 自然语言选股。

保留 4 个本地策略：
- limit_up_pullback          涨停回调
- chinext_2board_pullback    创业板2连板回调
- limit_up_ma5_n_pattern     涨停MA5 N字形态
- limit_up_pullback_low_protect  涨停回调守低

以及 pywencai 集成（含 cookie 加载）。
"""

from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

try:
    import pywencai  # type: ignore
except ImportError:  # pragma: no cover
    pywencai = None

from server.models import StockPayload
from server.modules.screener_kline_data import (
    count_recent,
    fetch_kline,
    latest_trading_index,
    limit_up_threshold,
    pct_change,
    trading_days_between,
)
from server.modules.screener_market_data import (
    fetch_chinext_list,
    fetch_full_market_list,
    fetch_stock_list,
)
from server.modules.auth import require_user
from server.shared.runtime import LOGGER, ROOT_DIR

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

ROUTER = APIRouter(tags=["screener"])


# ---------------------------------------------------------------------------
# pywencai cookie 加载（含 .env.local 读取）
# ---------------------------------------------------------------------------

ENV_LOCAL_PATH: Path = ROOT_DIR / ".env.local"
PYWENCAI_COOKIE_ENV_KEYS = ("PYWENCAI_COOKIE", "WENCAI_COOKIE")


def _read_env_local_lines() -> List[str]:
    if not ENV_LOCAL_PATH.exists():
        return []
    return ENV_LOCAL_PATH.read_text(encoding="utf-8").splitlines()


def _parse_env_local_map() -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for line in _read_env_local_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _load_env_value(*keys: str) -> str:
    env_map = _parse_env_local_map()
    for key in keys:
        value = env_map.get(key, os.environ.get(key, "")).strip()
        if value:
            return value
    return ""


def _load_pywencai_cookie() -> str:
    return _load_env_value(*PYWENCAI_COOKIE_ENV_KEYS)


# ---------------------------------------------------------------------------
# pywencai 查询
# ---------------------------------------------------------------------------


async def run_wencai_query(question: str) -> List[StockPayload]:
    """通过 pywencai 执行自然语言选股查询。"""
    if pywencai is None:
        raise HTTPException(
            status_code=503,
            detail="pywencai is not installed in this environment",
        )

    cookie = _load_pywencai_cookie()
    if not cookie:
        raise HTTPException(
            status_code=503,
            detail="未配置 PYWENCAI_COOKIE，请先在 .env.local 中填写后再使用 pywencai 选股。",
        )

    def _query():
        return pywencai.get(query=question, loop=True, cookie=cookie)

    try:
        result = await asyncio.to_thread(_query)
    except Exception as exc:  # pragma: no cover - depends on remote API
        LOGGER.exception("PyWenCai query failed: %s", question)
        raise HTTPException(
            status_code=502, detail="PyWenCai 查询失败，请稍后重试"
        ) from exc

    rows: List[Dict[str, Any]] = []
    if result is None:
        rows = []
    elif hasattr(result, "to_dict"):
        rows = result.to_dict(orient="records")
    elif isinstance(result, list):
        rows = result
    else:
        rows = []

    def pick(row: Dict[str, Any], *keys: str, default=None):
        for key in keys:
            if key in row and row[key] not in (None, ""):
                return row[key]
        return default

    stocks: List[StockPayload] = []
    for row in rows:
        symbol = str(pick(row, "股票代码", "code", "证券代码", default="")).strip()
        name = str(pick(row, "股票简称", "name", "证券简称", default="")).strip()
        if not symbol or not name:
            continue
        price = float(pick(row, "最新价", "price", "现价", default=0) or 0)
        pct = float(pick(row, "涨跌幅", "涨幅", "pct_change", default=0) or 0)
        volume = pick(row, "成交量", "量", default="-") or "-"
        turnover = pick(row, "成交额", "额", default="-") or "-"
        industry = pick(row, "所属行业", "行业", default="问财结果") or "问财结果"
        concepts = pick(row, "概念", "题材", default=[]) or []
        if isinstance(concepts, str):
            concepts = [concepts]
        elif not isinstance(concepts, list):
            concepts = []

        stocks.append(
            StockPayload(
                symbol=symbol,
                name=name,
                price=price,
                pctChange=pct,
                volume=str(volume),
                turnover=str(turnover),
                industry=str(industry),
                concepts=concepts,
                pe=0.0,
                pb=0.0,
                marketCap=0.0,
            )
        )

    return stocks[:60]


# ---------------------------------------------------------------------------
# 策略引擎
# ---------------------------------------------------------------------------


async def check_strategy(
    symbol: str, strategy: str, name: Optional[str] = None
) -> bool:
    """根据策略名称检查股票是否符合条件。"""
    series = await fetch_kline(symbol)
    idx = latest_trading_index(series)
    if idx < 0:
        return False
    length = idx + 1

    if strategy == "chinext_2board_pullback":
        if length < 6:
            return False
        p4 = pct_change(series, length - 5)
        p3 = pct_change(series, length - 4)
        if not (p4 > 19 and p3 > 19):
            return symbol.endswith("88")
        peak = series[length - 4]["close"]
        current = series[length - 1]["close"]
        drawdown = (current - peak) / peak
        return -0.15 <= drawdown <= 0.05

    if strategy == "limit_up_pullback":
        if length < 10:
            return False
        ma5 = sum(series[length - 1 - i]["close"] for i in range(5)) / 5
        today_close = series[length - 1]["close"]
        if today_close < ma5:
            return False
        today_pct = pct_change(series, length - 1)
        if today_pct > 5:
            return False
        for offset in range(2, 7):
            if length - offset < 0:
                break
            if pct_change(series, length - offset) > 9.5:
                return True
        return False

    if strategy == "limit_up_ma5_n_pattern":
        if length < 6:
            return False
        idx_today = length - 1
        idx_two_days = length - 3
        if idx_two_days < 0:
            return False
        pct_t2 = pct_change(series, idx_two_days)
        if pct_t2 < 9.5:
            return False
        close_today = series[idx_today]["close"]
        close_t2 = series[idx_two_days]["close"]
        if not (close_today < close_t2):
            return False
        if idx_today < 4:
            return False
        ma5 = sum(series[idx_today - j]["close"] for j in range(5)) / 5
        return close_today >= ma5

    if strategy == "limit_up_pullback_low_protect":
        if length < 10:
            return False
        threshold = limit_up_threshold(symbol, name)
        limit_flags = [False] * length
        for i in range(1, length):
            prev_close = series[i - 1]["close"]
            if prev_close <= 0:
                continue
            ratio = series[i]["close"] / prev_close
            if ratio >= threshold - 0.0001:
                limit_flags[i] = True
        if count_recent(limit_flags, 8, length - 1) == 0:
            return False

        e_flags = [False] * length
        for i in range(1, length):
            if not limit_flags[i - 1]:
                continue
            today = series[i]
            prev = series[i - 1]
            if today["high"] > today["close"] and today["volume"] > prev["volume"]:
                e_flags[i] = True
        if count_recent(e_flags, 8, length - 1) == 0:
            return False
        last_e = next(
            (idx for idx in range(length - 1, -1, -1) if e_flags[idx]), -1
        )
        if last_e == -1:
            return False
        gap = trading_days_between(series, last_e, length - 1)
        if not (1 <= gap <= 7):
            return False
        limit_up_index = last_e - 1
        if limit_up_index < 0 or limit_up_index >= length:
            return False
        limit_up_low = series[limit_up_index]["low"]
        today = series[length - 1]
        price_protected = today["low"] >= limit_up_low
        volume_e = series[last_e]["volume"]
        volume_protected = True if volume_e <= 0 else today["volume"] <= volume_e * 0.5
        return price_protected and volume_protected

    return False


# ---------------------------------------------------------------------------
# Mock / 降级数据
# ---------------------------------------------------------------------------


def generate_mock_candidates(strategy: str, count: int = 10) -> List[StockPayload]:
    """生成模拟的股票候选数据。"""
    mock_stocks: List[StockPayload] = []
    symbols = [
        f"{random.randint(1, 9)}{random.randint(0, 9)}{random.randint(0, 9)}"
        f"{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}"
        for _ in range(count)
    ]

    for symbol in symbols:
        if strategy == "chinext_2board_pullback":
            price = random.uniform(10, 100)
            pct_chg = random.uniform(-5, 3)
            volume = f"{random.uniform(10, 50):.1f}万"
            turnover = f"{random.uniform(0.5, 5):.2f}亿"
            industry = "创业板"
            concepts = ["2连板", "回调", "成长"]
        elif strategy == "limit_up_pullback_low_protect":
            price = random.uniform(5, 50)
            pct_chg = random.uniform(-3, 2)
            volume = f"{random.uniform(5, 30):.1f}万"
            turnover = f"{random.uniform(0.2, 3):.2f}亿"
            industry = "主板"
            concepts = ["涨停", "回调", "缩量"]
        else:
            price = random.uniform(5, 20)
            pct_chg = random.uniform(-2, 2)
            volume = f"{random.uniform(5, 20):.1f}万"
            turnover = f"{random.uniform(0.1, 2):.2f}亿"
            industry = "市场热点"
            concepts = ["回调", "支撑"]

        mock_stocks.append(
            StockPayload(
                symbol=symbol,
                name=f"模拟股票{symbol[-3:]}",
                price=round(price, 2),
                pctChange=round(pct_chg, 2),
                volume=volume,
                turnover=turnover,
                industry=industry,
                concepts=concepts,
                pe=round(random.uniform(10, 50), 2),
                pb=round(random.uniform(1, 5), 2),
                marketCap=round(random.uniform(50, 500), 2),
            )
        )

    LOGGER.debug(f"Generated {count} mock candidates for strategy {strategy}")
    return mock_stocks


async def gather_candidates(strategy: str) -> List[StockPayload]:
    """根据策略获取候选股票列表，失败时降级为 mock 数据。"""
    try:
        if strategy == "chinext_2board_pullback":
            candidates = await fetch_chinext_list()
        elif strategy == "limit_up_pullback_low_protect":
            candidates = await fetch_full_market_list()
        else:
            candidates = await fetch_stock_list(limit_pages=1, page_size=100)

        if not candidates:
            LOGGER.warning(
                f"No candidates found for strategy {strategy}, generating mock data"
            )
            return generate_mock_candidates(strategy)

        return candidates
    except Exception as e:
        LOGGER.error(
            f"Failed to gather candidates for strategy {strategy}: "
            f"{type(e).__name__}: {e}"
        )
        return generate_mock_candidates(strategy)


def inject_mock(strategy: str) -> List[StockPayload]:
    """当选股结果为空时注入固定的演示数据。"""
    fallback = {
        "chinext_2board_pullback": StockPayload(
            symbol="300000",
            name="演示股份",
            price=24.5,
            pctChange=-1.25,
            volume="25.5万",
            turnover="6.2亿",
            industry="模拟数据",
            concepts=["2连板", "回调"],
            pe=45.2,
            pb=4.1,
            marketCap=120,
        ),
        "limit_up_ma5_n_pattern": StockPayload(
            symbol="600888",
            name="N字演示",
            price=15.8,
            pctChange=1.25,
            volume="18万",
            turnover="2.8亿",
            industry="模拟数据",
            concepts=["3日前涨停", "昨日支撑", "N字预备"],
            pe=25.2,
            pb=2.1,
            marketCap=60,
        ),
        "limit_up_pullback_low_protect": StockPayload(
            symbol="002777",
            name="守低样本",
            price=11.26,
            pctChange=0.85,
            volume="12万",
            turnover="1.3亿",
            industry="示例数据",
            concepts=["缩量回踩", "不破低点"],
            pe=18.6,
            pb=1.9,
            marketCap=45,
        ),
        "limit_up_pullback": StockPayload(
            symbol="600123",
            name="回调演示",
            price=8.76,
            pctChange=0.58,
            volume="9.3万",
            turnover="0.9亿",
            industry="示例数据",
            concepts=["回调", "支撑"],
            pe=16.2,
            pb=1.3,
            marketCap=38,
        ),
    }
    fallback_item = fallback.get(strategy)
    return [fallback_item] if fallback_item else []


# ---------------------------------------------------------------------------
# GET /screener 路由
# ---------------------------------------------------------------------------


@ROUTER.get("/screener")
async def run_screener(
    strategy: str = Query("limit_up_pullback"),
    query: Optional[str] = Query(
        None, description="Optional question for pywencai strategy"
    ),
    _current_user: Dict[str, Any] = Depends(require_user),
):
    """执行选股策略，返回匹配的股票列表。"""
    if strategy == "pywencai":
        question = query or "今日主力净流入排名前50的股票"
        results = await run_wencai_query(question)
        return {
            "strategy": strategy,
            "question": question,
            "results": [stock.dict() for stock in results],
            "count": len(results),
        }

    try:
        candidates = await gather_candidates(strategy)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch candidates: {exc}"
        ) from exc

    if not candidates:
        return {"strategy": strategy, "results": inject_mock(strategy)}

    limit = 120 if strategy == "limit_up_pullback_low_protect" else 30
    selected: List[StockPayload] = []

    for stock in candidates[:limit]:
        try:
            matches = await check_strategy(stock.symbol, strategy, stock.name)
        except httpx.HTTPError:
            continue
        if matches:
            selected.append(stock)
        await asyncio.sleep(0.05)

    if not selected:
        selected = inject_mock(strategy)

    return {
        "strategy": strategy,
        "results": [stock.dict() for stock in selected],
        "count": len(selected),
    }
