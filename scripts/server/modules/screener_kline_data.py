"""K 线数据获取子模块：东方财富 / 新浪 / 腾讯三源回退 + mock 降级。

所有 async 函数使用 ``shared.runtime.CLIENT`` 发送 HTTP 请求，
日志通过 ``shared.runtime.LOGGER`` 输出。
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from server.shared.runtime import CLIENT, LOGGER

# ---------------------------------------------------------------------------
# 通用 HTTP 工具
# ---------------------------------------------------------------------------


async def fetch_json(url: str) -> Dict:
    """通用 JSON 抓取，附带浏览器 UA 和 Referer。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Referer": "https://eastmoney.com/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    resp = None
    try:
        resp = await CLIENT.get(url, headers=headers)
        LOGGER.debug(f"Fetching JSON from {url}, status code: {resp.status_code}")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        LOGGER.error(
            f"HTTP error when fetching {url}: {e.response.status_code} - {e.response.text}"
        )
        raise
    except httpx.RequestError as e:
        LOGGER.error(f"Request error when fetching {url}: {e}")
        raise
    except ValueError as e:
        if resp:
            LOGGER.error(
                f"JSON decode error when fetching {url}: {e}, response content: {resp.text}"
            )
        else:
            LOGGER.error(f"JSON decode error when fetching {url}: {e}")
        raise


# ---------------------------------------------------------------------------
# 内部辅助：股票代码转换
# ---------------------------------------------------------------------------


def _resolve_sina_symbol(symbol: str) -> str:
    return f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"


def _resolve_sina_scale(period: int) -> int:
    if period in (1, 5, 15, 30, 60):
        return period
    if period in (101, 102, 103):
        # Sina 用 240 表示日 K
        return 240
    return 240


def _resolve_tencent_symbol(symbol: str) -> str:
    return f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"


# ---------------------------------------------------------------------------
# 数据源：东方财富
# ---------------------------------------------------------------------------


async def fetch_kline_from_eastmoney(symbol: str, period: int = 101) -> List[Dict]:
    """东方财富 K 线接口，使用与 fetchMarketData.js 相同的 API 格式。"""
    try:
        # 根据股票代码判断市场类型
        if symbol.startswith("60") or symbol.startswith("5") or symbol.startswith("900"):
            secid = f"1.{symbol}"
        else:
            secid = f"0.{symbol}"

        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid,
            "fields1": "f1",
            "fields2": "f51,f52,f53,f54,f55,f57",
            "klt": period,
            "fqt": "1",  # 前复权
            "end": "20500101",
            "lmt": "260",
            "_": int(datetime.now().timestamp() * 1000),
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Referer": "http://quote.eastmoney.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

        resp = await CLIENT.get(url, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

        klines = payload.get("data", {}).get("klines") or []

        series: List[Dict[str, Any]] = []
        for entry in klines:
            parts = entry.split(",")
            if len(parts) >= 6:
                date_str, open_p, close_p, high_p, low_p, volume = parts[:6]
                try:
                    series.append(
                        {
                            "date": date_str,
                            "open": float(open_p),
                            "close": float(close_p),
                            "high": float(high_p),
                            "low": float(low_p),
                            "volume": float(volume),
                        }
                    )
                except ValueError:
                    continue
        return series
    except httpx.ConnectTimeout:
        LOGGER.error(f"Eastmoney API connect timeout for {symbol}")
        return []
    except httpx.HTTPError as e:
        LOGGER.error(f"Eastmoney API HTTP error for {symbol}: {e}")
        return []
    except Exception as e:
        LOGGER.error(f"Eastmoney API error for {symbol}: {type(e).__name__}: {e}")
        return []


# ---------------------------------------------------------------------------
# 数据源：新浪
# ---------------------------------------------------------------------------


async def fetch_kline_from_sina(symbol: str, period: int = 101) -> List[Dict]:
    """新浪 K 线接口。"""
    sina_symbol = _resolve_sina_symbol(symbol)
    scale = _resolve_sina_scale(period)
    params = {
        "symbol": sina_symbol,
        "scale": scale,
        "ma": "5,10,20,30,60",
        "datalen": 200,
    }
    url = "https://quotes.sina.cn/cn/api/openapi.php/StockService.getKLineData"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Referer": "https://finance.sina.com.cn/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    resp = await CLIENT.get(url, params=params, headers=headers)
    resp.raise_for_status()
    payload = resp.json()

    result_block: Any = payload.get("result")
    if isinstance(result_block, list):
        result_block = result_block[0] if result_block else {}
    if not isinstance(result_block, dict):
        return []

    data_block: Any = result_block.get("data", {})
    if isinstance(data_block, list):
        data_block = data_block[0] if data_block else {}
    if not isinstance(data_block, dict):
        return []

    kline = data_block.get("kline") or []
    series: List[Dict[str, Any]] = []
    for item in kline:
        day = item.get("day")
        if not day:
            continue
        try:
            series.append(
                {
                    "date": day,
                    "open": float(item.get("open", 0) or 0),
                    "close": float(item.get("close", 0) or 0),
                    "high": float(item.get("high", 0) or 0),
                    "low": float(item.get("low", 0) or 0),
                    "volume": float(item.get("volume", 0) or 0),
                }
            )
        except (TypeError, ValueError):
            continue
    return series


# ---------------------------------------------------------------------------
# 数据源：腾讯
# ---------------------------------------------------------------------------


async def fetch_kline_from_tencent(symbol: str, period: int = 101) -> List[Dict]:
    """腾讯 K 线接口。"""
    tencent_symbol = _resolve_tencent_symbol(symbol)
    limit = 240
    if period in (1, 5, 15, 30, 60):
        # 分钟线
        param = f"{tencent_symbol},m{period},{limit}"
        url = "https://ifzq.gtimg.cn/appstock/app/kline/mkline"
    else:
        # 日线
        param = f"{tencent_symbol},day,,{limit},qfq"
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Referer": "https://gu.qq.com/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    resp = await CLIENT.get(url, params={"param": param}, headers=headers)
    resp.raise_for_status()
    payload = resp.json()

    data = payload.get("data", {})
    if not isinstance(data, dict):
        return []

    target_raw: Any = data.get(tencent_symbol) or data.get(tencent_symbol.upper())
    target: Optional[Dict[str, Any]] = None
    if isinstance(target_raw, dict):
        target = target_raw
    elif isinstance(target_raw, list):
        for candidate in target_raw:
            if isinstance(candidate, dict):
                target = candidate
                break
    if not target:
        return []

    # 根据 period 类型确定 kline_key
    if period in (1, 5, 15, 30, 60):
        kline_key = "m"
    else:
        kline_key = "day"
    kline = (
        target.get(f"{kline_key}_hfq")
        or target.get(f"{kline_key}_fq")
        or target.get(kline_key)
        or []
    )

    series: List[Dict[str, Any]] = []
    for item in kline:
        if isinstance(item, list) and len(item) >= 6:
            date_str = item[0]
            open_p, close_p, high_p, low_p, volume = item[1:6]
        elif isinstance(item, dict):
            date_str = item.get("date")
            open_p = item.get("open")
            close_p = item.get("close")
            high_p = item.get("high")
            low_p = item.get("low")
            volume = item.get("volume")
        else:
            continue
        if not date_str:
            continue
        try:
            series.append(
                {
                    "date": date_str,
                    "open": float(open_p or 0),
                    "close": float(close_p or 0),
                    "high": float(high_p or 0),
                    "low": float(low_p or 0),
                    "volume": float(volume or 0),
                }
            )
        except (TypeError, ValueError):
            continue
    return series


# ---------------------------------------------------------------------------
# Mock 降级
# ---------------------------------------------------------------------------


def generate_mock_kline(symbol: str, days: int = 120) -> List[Dict]:
    """生成模拟的 K 线数据，当所有数据源均失败时作为降级方案。"""
    series: List[Dict] = []
    base_price = random.uniform(5, 50)
    current_price = base_price

    for i in range(days):
        date = (datetime.now() - timedelta(days=days - i - 1)).strftime("%Y-%m-%d")

        change_pct = random.uniform(-5, 5) / 100
        open_p = current_price
        close_p = current_price * (1 + change_pct)
        high_p = max(open_p, close_p) * (1 + random.uniform(0, 2) / 100)
        low_p = min(open_p, close_p) * (1 - random.uniform(0, 2) / 100)
        volume = random.uniform(5000000, 50000000)

        series.append(
            {
                "date": date,
                "open": round(open_p, 2),
                "close": round(close_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "volume": round(volume),
            }
        )
        current_price = close_p

    LOGGER.debug(f"Generated mock kline data for {symbol}, {days} days")
    return series


# ---------------------------------------------------------------------------
# 主入口：三源回退
# ---------------------------------------------------------------------------


async def fetch_kline(symbol: str, period: int = 101) -> List[Dict]:
    """获取 K 线数据，依次尝试东方财富 → 新浪 → 腾讯，每个源最多重试 3 次。

    全部失败时返回 mock 数据。
    """
    providers = [
        ("Eastmoney", fetch_kline_from_eastmoney),
        ("Sina", fetch_kline_from_sina),
        ("Tencent", fetch_kline_from_tencent),
    ]

    for name, provider in providers:
        for attempt in range(3):
            try:
                LOGGER.debug(
                    f"Attempting to fetch kline from {name} for {symbol} "
                    f"(attempt {attempt + 1})"
                )
                data = await provider(symbol, period)
                if data:
                    LOGGER.info(f"Successfully fetched kline from {name} for {symbol}")
                    return data
                LOGGER.warning(
                    f"{name} kline fetch returned empty for {symbol} "
                    f"(attempt {attempt + 1})"
                )
            except httpx.ConnectTimeout:
                LOGGER.warning(
                    f"{name} kline fetch timed out for {symbol} "
                    f"(attempt {attempt + 1})"
                )
                await asyncio.sleep(1)
            except Exception as e:
                LOGGER.warning(
                    f"{name} kline fetch failed for {symbol} "
                    f"(attempt {attempt + 1}): {type(e).__name__}: {e}"
                )

    LOGGER.error(
        f"All providers failed to fetch kline for {symbol}, generating mock data"
    )
    return generate_mock_kline(symbol)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def latest_trading_index(series: List[Dict]) -> int:
    """返回序列中最近一个交易日的索引（<= 今天）。"""
    if not series:
        return -1
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for idx in range(len(series) - 1, -1, -1):
        if series[idx]["date"] <= today:
            return idx
    return len(series) - 1


def pct_change(series: List[Dict], index: int) -> float:
    """计算 index 处相对前一日的涨跌幅（百分比）。"""
    if index <= 0 or index >= len(series):
        return 0.0
    prev = series[index - 1]["close"]
    if prev == 0:
        return 0.0
    return ((series[index]["close"] - prev) / prev) * 100


def limit_up_threshold(symbol: str, name: Optional[str] = None) -> float:
    """根据股票代码和名称判断涨停阈值倍数。"""
    upper_name = (name or "").upper()
    if "ST" in upper_name:
        return 1.045
    if symbol.startswith(("30", "68")):
        return 1.195
    if symbol.startswith(("8", "4")):
        return 1.30
    return 1.095


def count_recent(flags: List[bool], window: int, end_idx: int) -> int:
    """统计 flags 中 [end_idx - window + 1, end_idx] 范围内 True 的个数。"""
    start = max(end_idx - window + 1, 0)
    return sum(1 for i in range(start, end_idx + 1) if flags[i])


def trading_days_between(series: List[Dict], start: int, end: int) -> int:
    """计算 series 中 start 到 end 索引之间的交易日数量。"""
    if start >= end:
        return 0
    count = 0
    for i in range(start + 1, end + 1):
        day = datetime.strptime(series[i]["date"], "%Y-%m-%d").weekday()
        if day < 5:
            count += 1
    return count


def simple_moving_average(
    series: List[Dict], index: int, window: int, key: str
) -> Optional[float]:
    """计算简单移动平均线。"""
    if index < 0 or window <= 0 or index - window + 1 < 0:
        return None
    total = 0.0
    for offset in range(window):
        total += float(series[index - offset].get(key, 0.0))
    return total / window
