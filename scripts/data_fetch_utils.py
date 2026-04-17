from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Sequence, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import build_opener, ProxyHandler, Request

from data_paths import A_SHARE_DIR, DATA_DIR, resolve_existing_path, resolve_write_path

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://quote.eastmoney.com/",
}

_opener = build_opener(ProxyHandler({}))
T = TypeVar("T")

# =========================================================================
# Tushare 配置
# =========================================================================

_TUSHARE_TOKEN = os.environ.get(
    "TUSHARE_API_KEY",
    os.environ.get("TUSHARE_KEY", "626731acf640dd90b86cca29b78d1b444fda11467a1e55b791d50404"),
)
_TUSHARE_URL = "https://api.tushare.pro"


def now_millis() -> int:
    return int(time.time() * 1000)


def _today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def _date_n_days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y%m%d")


# =========================================================================
# 基础 HTTP 工具（用于 push2ex / datacenter-web 等仍可用的域名）
# =========================================================================

def _fetch_raw(url: str, timeout: int = 15) -> bytes:
    req = Request(url, headers=DEFAULT_HEADERS)
    with _opener.open(req, timeout=timeout) as response:
        return response.read()


def fetch_json(url: str, timeout: int = 15) -> dict[str, Any]:
    return json.loads(_fetch_raw(url, timeout).decode("utf-8"))


def fetch_with_fallbacks(url: str, timeout: int = 15) -> dict[str, Any]:
    """对 push2ex / datacenter-web 等可用域名的请求，带 CORS 代理 fallback。"""
    pipelines = [
        url,
        f"https://corsproxy.io/?{quote(url, safe='')}",
        f"https://api.allorigins.win/raw?url={quote(url, safe='')}",
    ]
    last_error: Optional[Exception] = None
    for target in pipelines:
        try:
            return fetch_json(target, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, RemoteDisconnected,
                ConnectionResetError, OSError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.2)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


# =========================================================================
# Tushare API 核心
# =========================================================================

def tushare_call(api_name: str, params: dict, fields: str = "") -> dict[str, Any]:
    """调用 tushare pro API，返回原始响应。"""
    body: dict[str, Any] = {"api_name": api_name, "token": _TUSHARE_TOKEN, "params": params}
    if fields:
        body["fields"] = fields
    data = json.dumps(body).encode("utf-8")
    req = Request(_TUSHARE_URL, data=data, headers={"Content-Type": "application/json"})
    with _opener.open(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def tushare_rows(api_name: str, params: dict, fields: str = "") -> list[dict[str, Any]]:
    """调用 tushare 并返回 [{field: value}, ...] 格式。"""
    resp = tushare_call(api_name, params, fields)
    data = resp.get("data") or {}
    field_names = data.get("fields") or []
    items = data.get("items") or []
    return [dict(zip(field_names, row)) for row in items]


# =========================================================================
# Tushare 数据获取：K 线
# =========================================================================

def _fmt_date(td: str) -> str:
    """'20260415' -> '2026-04-15'"""
    return f"{td[:4]}-{td[4:6]}-{td[6:8]}" if len(td) == 8 else td


def tushare_kline(ts_code: str, limit: int = 200, api: str = "daily",
                  fields: str = "trade_date,open,close,high,low,vol") -> list[dict[str, Any]]:
    """获取 K 线数据，返回按日期正序的 dict 列表。
    api: daily / index_daily / index_global / fx_daily / ths_daily
    """
    end_date = _today_str()
    start_date = _date_n_days_ago(limit * 2)
    rows = tushare_rows(api, {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}, fields)
    rows.sort(key=lambda r: r.get("trade_date", ""))
    return rows[-limit:]


def tushare_stock_kline(symbol: str, limit: int = 200) -> list[dict[str, Any]]:
    """获取个股日 K 线。symbol: 6 位代码如 '000692' 或 '600519'。"""
    suffix = ".SH" if symbol.startswith("6") else ".SZ"
    ts_code = f"{symbol}{suffix}"
    # 先试个股，失败试指数
    rows = tushare_kline(ts_code, limit, api="daily")
    if not rows:
        rows = tushare_kline(ts_code, limit, api="index_daily")
    return rows


def tushare_index_kline(ts_code: str, limit: int = 200) -> list[dict[str, Any]]:
    """获取国内指数日 K 线。ts_code: 如 '000001.SH'。"""
    return tushare_kline(ts_code, limit, api="index_daily")


def tushare_global_index_kline(ts_code: str, limit: int = 200) -> list[dict[str, Any]]:
    """获取国际指数日 K 线。ts_code: 如 'XIN9', 'DJI', 'SPX', 'IXIC'。"""
    return tushare_kline(ts_code, limit, api="index_global")


def tushare_fx_kline(ts_code: str, limit: int = 200) -> list[dict[str, Any]]:
    """获取外汇日 K 线。ts_code: 如 'USDCNH.FXCM'。"""
    rows = tushare_kline(ts_code, limit, api="fx_daily",
                         fields="trade_date,bid_open,bid_close,bid_high,bid_low,tick_qty")
    for r in rows:
        r["open"] = r.pop("bid_open", 0) or 0
        r["close"] = r.pop("bid_close", 0) or 0
        r["high"] = r.pop("bid_high", 0) or 0
        r["low"] = r.pop("bid_low", 0) or 0
        r["vol"] = r.pop("tick_qty", 0) or 0
    return rows


def tushare_sector_kline(ts_code: str, limit: int = 10) -> list[dict[str, Any]]:
    """获取同花顺板块日 K 线。ts_code: 如 '883999.TI'。"""
    return tushare_kline(ts_code, limit, api="ths_daily",
                         fields="trade_date,open,close,high,low,pct_change,vol")


# =========================================================================
# Tushare 数据获取：板块列表 / 股票列表
# =========================================================================

def tushare_sector_list(trade_date: str = "", top_n: int = 30) -> list[dict[str, Any]]:
    """获取同花顺板块涨跌排行，返回 [{ts_code, name, pct_change}, ...]。"""
    if not trade_date:
        trade_date = _today_str()
    rows = tushare_rows("ths_daily", {"trade_date": trade_date}, "ts_code,name,pct_change")
    if not rows:
        trade_date = _date_n_days_ago(1)
        rows = tushare_rows("ths_daily", {"trade_date": trade_date}, "ts_code,name,pct_change")
    rows.sort(key=lambda r: -(r.get("pct_change") or 0))
    return rows[:top_n]


def tushare_full_market(trade_date: str = "") -> list[dict[str, Any]]:
    """获取全市场股票行情，返回 [{ts_code, pct_chg, amount, pe_ttm, name}, ...]。"""
    if not trade_date:
        trade_date = _today_str()

    rows = tushare_rows("daily", {"trade_date": trade_date}, "ts_code,pct_chg,amount")
    if not rows:
        trade_date = _date_n_days_ago(1)
        rows = tushare_rows("daily", {"trade_date": trade_date}, "ts_code,pct_chg,amount")
    if not rows:
        return []

    # PE 数据
    pe_rows = tushare_rows("daily_basic", {"trade_date": trade_date}, "ts_code,pe_ttm")
    pe_map = {r["ts_code"]: r.get("pe_ttm", 0) for r in pe_rows}

    # 股票名称
    name_rows = tushare_rows("stock_basic", {"list_status": "L"}, "ts_code,name")
    name_map = {r["ts_code"]: r.get("name", "") for r in name_rows}

    result = []
    for r in rows:
        ts_code = r.get("ts_code", "")
        code = ts_code.split(".")[0] if "." in ts_code else ts_code
        result.append({
            "ts_code": ts_code,
            "code": code,
            "name": name_map.get(ts_code, ""),
            "pct_chg": r.get("pct_chg", 0) or 0,
            "amount": (r.get("amount", 0) or 0) * 1000,  # tushare 单位千元 → 元
            "pe_ttm": pe_map.get(ts_code, 0) or 0,
        })
    return result


# =========================================================================
# Tushare 数据获取：涨跌停池
# =========================================================================

_LIMIT_POOL_CACHE: dict[str, list[dict[str, Any]]] = {}


def tushare_limit_up_pool(trade_date: str = "") -> list[dict[str, Any]]:
    """获取某日涨停股票池（tushare limit_list_d，limit_type='U'）。
    返回 [{symbol, name, industry, boardCount, pctChange, limitUpTime}, ...]
    """
    if not trade_date:
        trade_date = _today_str()

    cache_key = f"up_{trade_date}"
    if cache_key in _LIMIT_POOL_CACHE:
        return _LIMIT_POOL_CACHE[cache_key]

    rows = tushare_rows(
        "limit_list_d",
        {"trade_date": trade_date, "limit_type": "U"},
        "ts_code,name,industry,close,pct_chg,limit_times,first_time",
    )
    if not rows:
        # 尝试前一天
        trade_date = _date_n_days_ago(1)
        rows = tushare_rows(
            "limit_list_d",
            {"trade_date": trade_date, "limit_type": "U"},
            "ts_code,name,industry,close,pct_chg,limit_times,first_time",
        )

    result = []
    for r in rows:
        ts_code = r.get("ts_code", "")
        symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
        result.append({
            "symbol": symbol,
            "name": r.get("name", ""),
            "industry": r.get("industry", ""),
            "boardCount": int(r.get("limit_times") or 1),
            "pctChange": float(r.get("pct_chg") or 0),
            "limitUpTime": r.get("first_time") or "",
            "c": symbol,
            "n": r.get("name", ""),
            "lbc": int(r.get("limit_times") or 1),
            "hybk": r.get("industry", ""),
        })

    _LIMIT_POOL_CACHE[cache_key] = result
    return result


def tushare_limit_down_pool(trade_date: str = "") -> list[dict[str, Any]]:
    """获取某日跌停股票池（tushare limit_list_d，limit_type='D'）。"""
    if not trade_date:
        trade_date = _today_str()

    cache_key = f"down_{trade_date}"
    if cache_key in _LIMIT_POOL_CACHE:
        return _LIMIT_POOL_CACHE[cache_key]

    rows = tushare_rows(
        "limit_list_d",
        {"trade_date": trade_date, "limit_type": "D"},
        "ts_code,name,industry,close,pct_chg,first_time",
    )
    if not rows:
        trade_date = _date_n_days_ago(1)
        rows = tushare_rows(
            "limit_list_d",
            {"trade_date": trade_date, "limit_type": "D"},
            "ts_code,name,industry,close,pct_chg,first_time",
        )

    result = []
    for r in rows:
        ts_code = r.get("ts_code", "")
        symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
        result.append({
            "symbol": symbol,
            "name": r.get("name", ""),
            "industry": r.get("industry", ""),
            "pctChange": float(r.get("pct_chg") or 0),
            "c": symbol,
            "n": r.get("name", ""),
        })

    _LIMIT_POOL_CACHE[cache_key] = result
    return result


# =========================================================================
# 文件 I/O
# =========================================================================

def save_json(file_name: str, payload: Any) -> Path:
    output_path = resolve_write_path(file_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def read_json(file_name: str, default: Any = None) -> Any:
    file_path = resolve_existing_path(file_name)
    if not file_path.exists():
        return default
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


MARKET_DATA_DIR = A_SHARE_DIR
SYSTEM_DATA_DIR = DATA_DIR / "system"


def chunked(items: Sequence[T], chunk_size: int) -> List[Sequence[T]]:
    return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]


def retry_collect(items: Iterable[T], worker: Callable[[T], Any]) -> list[Any]:
    results: list[Any] = []
    for item in items:
        results.append(worker(item))
    return results
