"""市场数据获取子模块：股票列表 / 创业板 / 全市场。

使用 ``screener_kline_data.fetch_json`` 发送 HTTP 请求，
日志通过 ``shared.runtime.LOGGER`` 输出。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List

from server.models import StockPayload
from server.modules.screener_kline_data import fetch_json
from server.shared.runtime import LOGGER

# ---------------------------------------------------------------------------
# URL 构建
# ---------------------------------------------------------------------------


def build_stock_list_url(page: int, page_size: int) -> str:
    """构建东方财富股票列表 API 的请求 URL。"""
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    return (
        "https://push2.eastmoney.com/api/qt/clist/get"
        f"?pn={page}&pz={page_size}&po=1&np=1"
        "&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f3"
        "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        f"&fields=f12,f14,f2,f3,f5,f6,f9,f23,f20,f100&_={timestamp}"
    )


# ---------------------------------------------------------------------------
# 数据映射
# ---------------------------------------------------------------------------


def map_stock_payload(item: Dict) -> StockPayload:
    """将东方财富 API 返回的原始字典映射为 ``StockPayload``。"""

    def safe_float(value, default=0.0):  # noqa: ANN001
        if value == "-" or value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def safe_list(value) -> List[str]:  # noqa: ANN001
        if isinstance(value, list):
            return value
        return [value] if isinstance(value, str) and value else []

    volume = "-"
    turnover = "-"
    try:
        volume_value = safe_float(item.get("f5"))
        if volume_value:
            volume = f"{volume_value / 10000:.1f}万"
    except Exception:
        pass
    try:
        turnover_value = safe_float(item.get("f6"))
        if turnover_value:
            turnover = f"{turnover_value / 1e8:.2f}亿"
    except Exception:
        pass

    return StockPayload(
        symbol=str(item.get("f12")),
        name=item.get("f14", ""),
        price=safe_float(item.get("f2")),
        pctChange=safe_float(item.get("f3")),
        volume=volume,
        turnover=turnover,
        industry=item.get("f100", "") or "市场热点",
        concepts=safe_list(item.get("f100", "市场热点")),
        pe=safe_float(item.get("f9")),
        pb=safe_float(item.get("f23")),
        marketCap=safe_float(item.get("f20")) / 1e8 if safe_float(item.get("f20")) else 0.0,
    )


# ---------------------------------------------------------------------------
# 市场数据获取
# ---------------------------------------------------------------------------


async def fetch_stock_list(limit_pages: int = 1, page_size: int = 100) -> List[StockPayload]:
    """分页获取股票列表。"""
    stocks: List[StockPayload] = []
    for page in range(1, limit_pages + 1):
        url = build_stock_list_url(page, page_size)
        data = await fetch_json(url)
        diff = data.get("data", {}).get("diff") or []
        stocks.extend(map_stock_payload(item) for item in diff)
        if len(diff) < page_size:
            break
    return stocks


async def fetch_chinext_list() -> List[StockPayload]:
    """获取创业板股票列表。"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz=80&po=1&np=1"
        "&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f3"
        "&fs=m:0+t:80"
        "&fields=f12,f14,f2,f3,f5,f6,f9,f23,f20"
    )
    data = await fetch_json(url)
    diff = data.get("data", {}).get("diff") or []
    return [
        StockPayload(
            symbol=str(item.get("f12")),
            name=item.get("f14", ""),
            price=float(item.get("f2") or 0),
            pctChange=float(item.get("f3") or 0),
            volume=f"{(item.get('f5') or 0) / 10000:.1f}万",
            turnover=f"{(item.get('f6') or 0) / 1e8:.2f}亿",
            industry="创业板",
            concepts=["成长", "热门"],
            pe=float(item.get("f9") or 0),
            pb=float(item.get("f23") or 0),
            marketCap=float(item.get("f20") or 0) / 1e8,
        )
        for item in diff
    ]


async def fetch_full_market_list() -> List[StockPayload]:
    """获取全市场股票列表（最多 30 页，每页 400 条）。"""
    stocks: List[StockPayload] = []
    for page in range(1, 31):
        url = build_stock_list_url(page, 400)
        data = await fetch_json(url)
        diff = data.get("data", {}).get("diff") or []
        stocks.extend(map_stock_payload(item) for item in diff)
        if len(diff) < 400:
            break
        await asyncio.sleep(0.1)
    return stocks
