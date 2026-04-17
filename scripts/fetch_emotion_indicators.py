from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

from data_fetch_utils import (
    DATA_DIR, save_json,
    tushare_index_kline, tushare_global_index_kline, tushare_fx_kline,
    tushare_full_market, tushare_rows, _fmt_date,
)

INDEX_CONFIG = {
    "ftseA50": ("index_global", "XIN9"),
    "nasdaq": ("index_global", "IXIC"),
    "dowJones": ("index_global", "DJI"),
    "sp500": ("index_global", "SPX"),
    "offshoreRmb": ("fx", "USDCNH.FXCM"),
}
INDEX_FUTURES_CONFIG = {
    "IF": {"label": "沪深300", "inner_code": "1000208870"},
    "IC": {"label": "中证500", "inner_code": "1000295095"},
    "IH": {"label": "上证50", "inner_code": "1000295097"},
    "IM": {"label": "中证1000", "inner_code": "1003154509"},
}
OUTPUT_PATH = DATA_DIR / "emotion_indicators.json"
INDEX_FUTURES_OUTPUT_PATH = DATA_DIR / "index_futures_long_short.json"
BULL_BEAR_OUTPUT_PATH = DATA_DIR / "bull_bear_signal.json"
MAX_REASONABLE_ASHARE_PE = 100.0
MAX_REASONABLE_ASHARE_PE_CHANGE_RATIO = 2.0
ASHARE_PE_PAGE_SIZE = 500
ASHARE_PE_MAX_PAGES = 12
FULL_MARKET_PAGE_SIZE = 100
FULL_MARKET_MAX_PAGES = 80
REQUEST_PAUSE_SECONDS = 0.15


def pause_briefly() -> None:
    time.sleep(REQUEST_PAUSE_SECONDS)


def trimmed_mean(values: List[float], trim_ratio: float = 0.1) -> float:
    if not values:
        raise RuntimeError("No values available for trimmed mean")

    ordered = sorted(values)
    trim_count = int(len(ordered) * trim_ratio)
    if trim_count * 2 >= len(ordered):
        trim_count = max(0, (len(ordered) - 1) // 2)
    trimmed = ordered[trim_count: len(ordered) - trim_count] if trim_count else ordered
    if not trimmed:
        trimmed = ordered
    return sum(trimmed) / len(trimmed)


def fetch_index_series(api_type: str, ts_code: str, limit: int = 12) -> Dict[str, float]:
    try:
        if api_type == "index_global":
            rows = tushare_global_index_kline(ts_code, limit)
        elif api_type == "fx":
            rows = tushare_fx_kline(ts_code, limit)
        else:
            rows = tushare_index_kline(ts_code, limit)
    except Exception as exc:
        print(f"[emotion] fetch_index_series({ts_code}) failed: {exc}", file=sys.stderr)
        return {}

    result: Dict[str, float] = {}
    for r in rows:
        date_str = _fmt_date(r.get("trade_date", ""))
        close = float(r.get("close", 0) or 0)
        if close > 0:
            result[date_str] = close
    return result


def fetch_ashare_average_pe() -> float:
    values: List[float] = []
    market_data = tushare_full_market()
    for item in market_data:
        try:
            pe = float(item.get("pe_ttm", 0))
        except (TypeError, ValueError):
            continue
        if 0 < pe < 5000:
            values.append(pe)

    if not values:
        raise RuntimeError("No valid A-share PE values")

    return round(trimmed_mean(values), 2)


def normalize_ashare_average_pe(value: float, previous: object) -> float:
    previous_value = float(previous) if isinstance(previous, (int, float)) else None
    if value <= 0 or value > MAX_REASONABLE_ASHARE_PE:
        if previous_value and previous_value > 0:
            print(
                f"[emotion] valuation outlier {value:.2f}, fallback to previous {previous_value:.2f}",
                file=sys.stderr,
            )
            return round(previous_value, 2)
        print(
            f"[emotion] valuation outlier {value:.2f}, clamp to upper bound {MAX_REASONABLE_ASHARE_PE:.2f}",
            file=sys.stderr,
        )
        return round(MAX_REASONABLE_ASHARE_PE, 2)

    if previous_value and previous_value > 0:
        ratio = value / previous_value
        if ratio > MAX_REASONABLE_ASHARE_PE_CHANGE_RATIO or ratio < (1 / MAX_REASONABLE_ASHARE_PE_CHANGE_RATIO):
            print(
                f"[emotion] valuation jump {value:.2f} vs previous {previous_value:.2f}, fallback to previous",
                file=sys.stderr,
            )
            return round(previous_value, 2)

    return round(value, 2)


_MAIN_CONTRACT_CACHE: Dict[str, str] = {}


def fetch_index_futures_main_contract(code: str) -> str:
    """通过 tushare fut_basic 获取主力合约代码。"""
    if code in _MAIN_CONTRACT_CACHE:
        return _MAIN_CONTRACT_CACHE[code]

    # tushare fut_mapping 获取主力合约映射
    rows = tushare_rows("fut_mapping", {"ts_code": f"{code}.CFX"}, "ts_code,mapping_ts_code")
    if rows:
        main_code = rows[0].get("mapping_ts_code", "")
        if main_code:
            _MAIN_CONTRACT_CACHE[code] = main_code
            return main_code

    # fallback: 手动构造当月合约代码
    from datetime import datetime
    now = datetime.now()
    month_code = now.strftime("%y%m")
    main_code = f"{code}{month_code}.CFX"
    _MAIN_CONTRACT_CACHE[code] = main_code
    return main_code


def fetch_single_index_futures_long_short_series(code: str, limit: int = 21) -> dict:
    """通过 tushare fut_holding 获取期货多空持仓数据。"""
    config = INDEX_FUTURES_CONFIG[code]

    from data_fetch_utils import _date_n_days_ago, _today_str
    start_date = _date_n_days_ago(limit * 2)
    end_date = _today_str()

    # fut_holding 按品种代码查询，汇总所有会员的多空持仓
    rows = tushare_rows(
        "fut_holding",
        {"symbol": code, "start_date": start_date, "end_date": end_date},
        "trade_date,long_hld,short_hld,broker",
    )

    if not rows:
        # fallback: 尝试用交易所参数
        rows = tushare_rows(
            "fut_holding",
            {"exchange": "CFFEX", "start_date": start_date, "end_date": end_date},
            "trade_date,symbol,long_hld,short_hld,broker",
        )
        rows = [r for r in rows if r.get("symbol", "").startswith(code)]

    # 按日期汇总多空持仓
    daily_totals: Dict[str, Dict[str, int]] = {}
    for r in rows:
        trade_date = _fmt_date(r.get("trade_date", ""))
        if not trade_date:
            continue
        if trade_date not in daily_totals:
            daily_totals[trade_date] = {"long": 0, "short": 0}
        daily_totals[trade_date]["long"] += int(r.get("long_hld") or 0)
        daily_totals[trade_date]["short"] += int(r.get("short_hld") or 0)

    history: List[dict] = []
    for date_str in sorted(daily_totals.keys()):
        totals = daily_totals[date_str]
        if totals["short"] > 0:
            history.append({
                "date": date_str,
                "longPosition": totals["long"],
                "shortPosition": totals["short"],
            })

    history = history[-12:]
    if not history:
        print(f"[emotion] 警告: {code} 无期货持仓数据，返回空序列")
        return {
            "code": code,
            "label": config["label"],
            "mainContract": f"{code}(unknown)",
            "history": [],
        }

    main_contract = fetch_index_futures_main_contract(code)
    return {
        "code": code,
        "label": config["label"],
        "mainContract": main_contract,
        "history": history,
    }


def fetch_index_futures_long_short_ratio_series(limit: int = 21) -> Dict[str, float]:
    series = fetch_single_index_futures_long_short_series("IF", limit=limit)
    return {
        item["date"]: round(item["longPosition"] / item["shortPosition"], 4)
        for item in series["history"]
        if item["shortPosition"] > 0
    }


def build_index_futures_rows() -> List[dict]:
    return [fetch_single_index_futures_long_short_series(code) for code in INDEX_FUTURES_CONFIG]


def load_json_file(path: Path) -> object:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def load_market_volume_lookup() -> Dict[str, dict]:
    payload = load_json_file(DATA_DIR / "market_volume_trend.json")
    if not isinstance(payload, list):
        return {}

    lookup: Dict[str, dict] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        date = str(item.get("date") or "")
        if not date:
            continue
        full_date = str(item.get("fullDate") or "")
        normalized = full_date if full_date else f"2026-{date}" if len(date) == 5 else date
        lookup[normalized] = item
    return lookup


def fetch_full_market_rows() -> List[dict]:
    market_data = tushare_full_market()
    if not market_data:
        raise RuntimeError("No full-market rows returned from tushare")
    # 转换为东方财富兼容的 f3/f6/f12/f14 格式
    rows: List[dict] = []
    for item in market_data:
        rows.append({
            "f3": item.get("pct_chg", 0),
            "f6": item.get("amount", 0),
            "f12": item.get("code", ""),
            "f14": item.get("name", ""),
        })
    return rows


def fetch_limit_pool_meta(date: str, pool_type: str) -> List[dict]:
    """通过 tushare limit_list_d 获取涨停/跌停池元数据。"""
    api_date = date.replace("-", "")
    if pool_type == "zt":
        from data_fetch_utils import tushare_limit_up_pool
        pool = tushare_limit_up_pool(api_date)
    else:
        from data_fetch_utils import tushare_limit_down_pool
        pool = tushare_limit_down_pool(api_date)

    return [
        {
            "symbol": item.get("symbol", ""),
            "name": item.get("name", ""),
        }
        for item in pool
        if isinstance(item, dict)
    ]


def is_st_stock_name(name: str) -> bool:
    normalized = str(name).upper().replace(" ", "")
    return "ST" in normalized


def safe_float(value: object) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_snapshot_date(date: str) -> str:
    if len(date) == 10 and date.count("-") == 2:
        return date
    if len(date) == 5 and date.count("-") == 1:
        from datetime import datetime
        return f"{datetime.now().year}-{date}"
    return date


def build_bull_bear_signal_snapshot() -> dict:
    rows = fetch_full_market_rows()
    volume_lookup = load_market_volume_lookup()
    latest_volume_date = sorted(volume_lookup.keys())[-1] if volume_lookup else ""
    latest_date = normalize_snapshot_date(latest_volume_date) if latest_volume_date else ""
    if not latest_date:
        raise RuntimeError("No latest trading date for bull bear snapshot")

    limit_up_pool = fetch_limit_pool_meta(latest_date, "zt")
    limit_down_pool = fetch_limit_pool_meta(latest_date, "dt")
    limit_up_symbols = {item["symbol"] for item in limit_up_pool if item.get("symbol")}
    limit_down_symbols = {item["symbol"] for item in limit_down_pool if item.get("symbol")}

    rise_count = 0
    fall_count = 0
    flat_count = 0
    total_amount = 0.0
    up5_count = 0
    up1_count = 0
    flat_band_count = 0
    down1_count = 0
    down5_count = 0

    for row in rows:
        pct = safe_float(row.get("f3"))
        if pct is None:
            continue
        symbol = str(row.get("f12") or "")
        amount = safe_float(row.get("f6")) or 0.0
        if amount > 0:
            total_amount += amount

        if pct > 0:
            rise_count += 1
        elif pct < 0:
            fall_count += 1
        else:
            flat_count += 1

        if symbol in limit_up_symbols or symbol in limit_down_symbols:
            continue

        if pct >= 5:
            up5_count += 1
        elif pct >= 1:
            up1_count += 1
        elif pct > -1:
            flat_band_count += 1
        elif pct > -5:
            down1_count += 1
        else:
            down5_count += 1

    latest_volume = volume_lookup.get(latest_date, {}) if latest_date else {}
    amount_yi = int(round(float(latest_volume.get("amount") or total_amount / 100000000)))
    amount_change_rate = latest_volume.get("changeRate")
    if not isinstance(amount_change_rate, (int, float)):
        amount_change_rate = None

    limit_down_count = len(limit_down_pool)
    if limit_down_count == 0:
        limit_down_count = sum(
            1 for row in rows
            if (safe_float(row.get("f3")) or 0) <= -9.9
        )

    return {
        "date": latest_date,
        "riseCount": rise_count,
        "fallCount": fall_count,
        "flatCount": flat_count,
        "limitUpCount": len(limit_up_pool),
        "limitDownCount": limit_down_count,
        "naturalLimitUpCount": sum(1 for item in limit_up_pool if not is_st_stock_name(item.get("name", ""))),
        "naturalLimitDownCount": (
            sum(1 for item in limit_down_pool if not is_st_stock_name(item.get("name", "")))
            if limit_down_pool
            else sum(
                1
                for row in rows
                if (safe_float(row.get("f3")) or 0) <= -9.9 and not is_st_stock_name(str(row.get("f14") or ""))
            )
        ),
        "totalAmount": amount_yi,
        "amountChangeRate": amount_change_rate,
        "rangeBuckets": [
            {"label": "涨停", "count": len(limit_up_pool), "tone": "up"},
            {"label": "涨停~5%", "count": up5_count, "tone": "up"},
            {"label": "5~1%", "count": up1_count, "tone": "up"},
            {"label": "平盘", "count": flat_band_count, "tone": "flat"},
            {"label": "0~-1%", "count": down1_count, "tone": "down"},
            {"label": "-1~-5%", "count": down5_count, "tone": "down"},
            {"label": "跌停", "count": limit_down_count, "tone": "down"},
        ],
    }


def save_bull_bear_signal_snapshot(snapshot: dict) -> None:
    payload = load_json_file(BULL_BEAR_OUTPUT_PATH)
    history = payload if isinstance(payload, list) else []
    filtered = [
        item for item in history
        if isinstance(item, dict) and str(item.get("date") or "") != str(snapshot.get("date") or "")
    ]
    filtered.append(snapshot)
    filtered.sort(key=lambda item: str(item.get("date") or ""))
    save_json("bull_bear_signal.json", filtered)


def load_existing_rows() -> Dict[str, dict]:
    if not OUTPUT_PATH.exists():
        return {}
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, list):
        return {}
    return {
        str(item.get("date")): item
        for item in payload
        if isinstance(item, dict) and isinstance(item.get("date"), str)
    }


def build_rows() -> List[dict]:
    existing = load_existing_rows()
    series_map = {name: fetch_index_series(api_type, ts_code) for name, (api_type, ts_code) in INDEX_CONFIG.items()}
    index_futures_long_short_series = fetch_index_futures_long_short_ratio_series()

    # 只用有数据的指数来计算共享日期
    available_series = {k: v for k, v in series_map.items() if v}
    if not available_series:
        raise RuntimeError("No index data available for emotion indicators")

    date_sets = [set(s.keys()) for s in available_series.values()]
    date_sets.append(set(index_futures_long_short_series.keys()))
    shared_dates = sorted(set.intersection(*date_sets))[-10:]

    rows: List[dict] = []
    latest_shared_date = shared_dates[-1] if shared_dates else None
    previous_latest_row = existing.get(shared_dates[-2], {}) if len(shared_dates) >= 2 else {}
    latest_pe = normalize_ashare_average_pe(
        fetch_ashare_average_pe(),
        previous_latest_row.get("ashareAvgValuation"),
    ) if latest_shared_date else None

    for index, date in enumerate(shared_dates):
        previous = existing.get(date, {})
        valuation = previous.get("ashareAvgValuation")
        if index == len(shared_dates) - 1 or not isinstance(valuation, (int, float)) or valuation <= 0:
            valuation = latest_pe

        rows.append(
            {
                "date": date,
                "ftseA50": round(series_map["ftseA50"].get(date, 0), 2),
                "nasdaq": round(series_map["nasdaq"].get(date, 0), 2),
                "dowJones": round(series_map["dowJones"].get(date, 0), 2),
                "sp500": round(series_map["sp500"].get(date, 0), 2),
                "offshoreRmb": round(series_map["offshoreRmb"].get(date, 0), 4),
                "ashareAvgValuation": round(float(valuation), 2),
                "indexFuturesLongShortRatio": round(index_futures_long_short_series[date], 4),
            }
        )

    if not rows:
        raise RuntimeError("No shared dates returned for emotion indicators")

    return rows


def main() -> int:
    wrote_any = False

    # 情绪指标（国际指数 + PE + 期货多空比）
    try:
        rows = build_rows()
        save_json("emotion_indicators.json", rows)
        print(f"[emotion] wrote {len(rows)} rows to {OUTPUT_PATH}")
        wrote_any = True
    except Exception as exc:
        print(f"[emotion] build_rows failed, skipping: {exc}", file=sys.stderr)

    # 期货多空比
    try:
        futures_rows = build_index_futures_rows()
        save_json("index_futures_long_short.json", futures_rows)
        print(f"[emotion] wrote {len(futures_rows)} rows to {INDEX_FUTURES_OUTPUT_PATH}")
        wrote_any = True
    except Exception as exc:
        print(f"[emotion] build_index_futures_rows failed, skipping: {exc}", file=sys.stderr)

    # 牛熊信号快照（依赖 push2 全市场数据）
    try:
        bull_bear_snapshot = build_bull_bear_signal_snapshot()
        save_bull_bear_signal_snapshot(bull_bear_snapshot)
        print(f"[emotion] updated bull bear snapshot for {bull_bear_snapshot.get('date')} at {BULL_BEAR_OUTPUT_PATH}")
        wrote_any = True
    except Exception as exc:
        print(f"[emotion] build_bull_bear_signal_snapshot failed, skipping: {exc}", file=sys.stderr)

    if not wrote_any:
        print("[emotion] all sections failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"[emotion] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
