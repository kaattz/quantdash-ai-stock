"""全市场 K 线批量同步（tushare 按日期批量拉取）。

优化策略：
  旧方案：逐只股票调 tushare API → 5000+ 股票 × 3 周期 = 15000+ 次 API 调用
  新方案：按日期调 daily/weekly/monthly → 约 30+8+6 = 44 次 API 调用

用法：
    python scripts/fetch_kline_library.py

环境变量：
    SKIP_KLINE_DOWNLOAD=1    跳过下载
    KLINE_FORCE_FULL=1       强制全量更新（忽略本地缓存）
    KLINE_RECENT_DAYS=30     日K拉取天数（默认30）
    KLINE_RECENT_WEEKS=8     周K拉取周数（默认8）
    KLINE_RECENT_MONTHS=6    月K拉取月数（默认6）
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set

from data_fetch_utils import (
    MARKET_DATA_DIR,
    save_json,
    tushare_rows,
    _fmt_date,
    _today_str,
    _date_n_days_ago,
)
from data_paths import resolve_existing_path

KLINE_DIR = MARKET_DATA_DIR / "klines"
SKIP_KLINE_DOWNLOAD = os.getenv("SKIP_KLINE_DOWNLOAD") == "1"
KLINE_FORCE_FULL = os.getenv("KLINE_FORCE_FULL") == "1"
KLINE_RECENT_DAYS = max(5, int(os.getenv("KLINE_RECENT_DAYS", "30") or "30"))
KLINE_RECENT_WEEKS = max(2, int(os.getenv("KLINE_RECENT_WEEKS", "30") or "30"))
KLINE_RECENT_MONTHS = max(2, int(os.getenv("KLINE_RECENT_MONTHS", "30") or "30"))


# period code → tushare api name
PERIOD_API_MAP: Dict[int, str] = {101: "daily", 102: "weekly", 103: "monthly"}
PERIOD_LIMITS: Dict[int, int] = {101: KLINE_RECENT_DAYS, 102: KLINE_RECENT_WEEKS, 103: KLINE_RECENT_MONTHS}
# 周K/月K 需要更大的日期回溯范围
PERIOD_LOOKBACK_DAYS: Dict[int, int] = {101: KLINE_RECENT_DAYS * 2, 102: KLINE_RECENT_WEEKS * 10, 103: KLINE_RECENT_MONTHS * 40}


def format_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def get_trading_dates(days_back: int) -> List[str]:
    """获取最近 N 个交易日列表（YYYYMMDD 格式）。"""
    start = _date_n_days_ago(days_back)
    end = _today_str()
    rows = tushare_rows("trade_cal", {"start_date": start, "end_date": end, "is_open": "1"}, "cal_date")
    dates = sorted([r["cal_date"] for r in rows if r.get("cal_date")])
    return dates


def fetch_market_kline_by_date(api_name: str, trade_date: str) -> List[Dict[str, Any]]:
    """按日期拉全市场某天的 K 线数据，返回 [{ts_code, trade_date, open, close, high, low, vol}, ...]。"""
    rows = tushare_rows(api_name, {"trade_date": trade_date}, "ts_code,trade_date,open,close,high,low,vol")
    return rows


def ts_code_to_symbol(ts_code: str) -> str:
    return ts_code.split(".")[0] if "." in ts_code else ts_code


def load_local_kline_file(symbol: str) -> Dict[str, Any] | None:
    file_path = KLINE_DIR / f"{symbol}.json"
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_stock_names() -> Dict[str, str]:
    """从 stock_list_full.json 加载股票名称映射。"""
    file_path = resolve_existing_path("stock_list_full.json")
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, list):
        return {}
    return {str(item.get("symbol", "")): item.get("name", "") for item in payload if item.get("symbol")}


def build_kline_library() -> int:
    if SKIP_KLINE_DOWNLOAD:
        print("[kline-py] Skipping K-line download because SKIP_KLINE_DOWNLOAD=1")
        return 0

    KLINE_DIR.mkdir(parents=True, exist_ok=True)
    today = format_date(datetime.now())
    name_map = load_stock_names()

    # ── 按日期批量拉取全市场数据，按股票代码分桶 ──
    # symbol → period_str → [{date, open, close, high, low, volume}, ...]
    all_data: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}  # symbol → period → date → row

    for period, api_name in PERIOD_API_MAP.items():
        period_str = str(period)
        lookback = PERIOD_LOOKBACK_DAYS[period]
        limit = PERIOD_LIMITS[period]

        # 获取交易日列表
        print(f"[kline-py] 获取 {api_name} 交易日列表（回溯 {lookback} 天）...")
        trading_dates = get_trading_dates(lookback)
        # 只取最近 limit 个交易日
        trading_dates = trading_dates[-limit:]
        print(f"[kline-py] {api_name}: 将拉取 {len(trading_dates)} 个交易日的数据")

        for idx, trade_date in enumerate(trading_dates):
            try:
                rows = fetch_market_kline_by_date(api_name, trade_date)
            except Exception as e:
                print(f"[kline-py] {api_name} {trade_date} 失败: {e}")
                rows = []

            for r in rows:
                ts_code = r.get("ts_code", "")
                symbol = ts_code_to_symbol(ts_code)
                if not symbol:
                    continue

                if symbol not in all_data:
                    all_data[symbol] = {}
                if period_str not in all_data[symbol]:
                    all_data[symbol][period_str] = {}

                date_str = _fmt_date(r.get("trade_date", ""))
                all_data[symbol][period_str][date_str] = {
                    "date": date_str,
                    "open": float(r.get("open") or 0),
                    "close": float(r.get("close") or 0),
                    "high": float(r.get("high") or 0),
                    "low": float(r.get("low") or 0),
                    "volume": float(r.get("vol") or 0),
                }

            if (idx + 1) % 10 == 0 or idx == len(trading_dates) - 1:
                print(f"[kline-py] {api_name}: {idx + 1}/{len(trading_dates)} 交易日已拉取")

            time.sleep(0.12)  # tushare 限流

    # ── 合并到本地文件并写入 ──
    symbols = sorted(all_data.keys())
    print(f"[kline-py] 共获取 {len(symbols)} 只股票数据，开始写入本地文件...")

    manifest: List[Dict[str, Any]] = []
    for idx, symbol in enumerate(symbols):
        # 加载已有本地数据
        existing = load_local_kline_file(symbol) if not KLINE_FORCE_FULL else None
        existing_periods = existing.get("periods", {}) if isinstance(existing, dict) else {}

        periods_payload: Dict[str, List[Dict[str, Any]]] = {}
        for period_str in ["101", "102", "103"]:
            # 合并已有数据和新数据
            merged: Dict[str, Dict[str, Any]] = {}

            # 先加载已有数据
            old_series = existing_periods.get(period_str, [])
            if isinstance(old_series, list):
                for item in old_series:
                    if isinstance(item, dict) and item.get("date"):
                        merged[item["date"]] = item

            # 覆盖新数据
            new_data = all_data[symbol].get(period_str, {})
            merged.update(new_data)

            if merged:
                periods_payload[period_str] = [merged[d] for d in sorted(merged.keys())]

        if not periods_payload:
            continue

        payload = {
            "symbol": symbol,
            "name": name_map.get(symbol, existing.get("name", "") if existing else ""),
            "market": 1 if symbol.startswith("6") else 0,
            "updated": today,
            "periods": periods_payload,
        }

        file_path = KLINE_DIR / f"{symbol}.json"
        file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        manifest.append({
            "symbol": symbol,
            "name": payload["name"],
            "updated": today,
            "periods": sorted(periods_payload.keys()),
        })

        if (idx + 1) % 500 == 0 or idx == len(symbols) - 1:
            print(f"[kline-py] 写入进度: {idx + 1}/{len(symbols)}")

    save_json("kline-manifest.json", manifest)
    print(f"[kline-py] 完成！共写入 {len(manifest)} 只股票的 K 线数据。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(build_kline_library())
    except Exception as exc:
        print(f"[kline-py] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
