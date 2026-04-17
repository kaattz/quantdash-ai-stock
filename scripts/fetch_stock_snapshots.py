from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List

from data_fetch_utils import (
    save_json,
    read_json,
    tushare_rows,
    tushare_full_market,
    _fmt_date,
    _today_str,
    _date_n_days_ago,
)

FORCE_CONCEPT_REFRESH = os.getenv("FORCE_CONCEPT_REFRESH") == "1"


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val in (None, "", "-"):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


# =========================================================================
# 全市场股票快照（替代 push2.eastmoney.com/api/qt/clist/get）
# =========================================================================

def fetch_full_market_stocks() -> List[Dict[str, Any]]:
    """通过 tushare 获取全市场股票快照，返回与原 eastmoney 格式兼容的结构。"""
    print("[stocks-py] Fetching full market via tushare daily + daily_basic + stock_basic...")

    trade_date = _today_str()

    # 日线行情：价格、涨跌幅、成交量、成交额
    daily_rows = tushare_rows("daily", {"trade_date": trade_date},
                              "ts_code,close,pct_chg,vol,amount")
    if not daily_rows:
        trade_date = _date_n_days_ago(1)
        daily_rows = tushare_rows("daily", {"trade_date": trade_date},
                                  "ts_code,close,pct_chg,vol,amount")
    if not daily_rows:
        trade_date = _date_n_days_ago(2)
        daily_rows = tushare_rows("daily", {"trade_date": trade_date},
                                  "ts_code,close,pct_chg,vol,amount")

    daily_map: Dict[str, Dict] = {r["ts_code"]: r for r in daily_rows}

    # 基本面指标：PE、PB、总市值
    basic_rows = tushare_rows("daily_basic", {"trade_date": trade_date},
                              "ts_code,pe_ttm,pb,total_mv")
    basic_map: Dict[str, Dict] = {r["ts_code"]: r for r in basic_rows}

    # 股票基本信息：名称、行业
    info_rows = tushare_rows("stock_basic", {"list_status": "L"},
                             "ts_code,name,industry")
    info_map: Dict[str, Dict] = {r["ts_code"]: r for r in info_rows}

    stocks: List[Dict[str, Any]] = []
    for ts_code, daily in daily_map.items():
        code = ts_code.split(".")[0] if "." in ts_code else ts_code
        info = info_map.get(ts_code, {})
        basic = basic_map.get(ts_code, {})

        vol = _safe_float(daily.get("vol"))          # 手
        amount = _safe_float(daily.get("amount"))     # 千元
        total_mv = _safe_float(basic.get("total_mv")) # 万元
        industry = info.get("industry") or "A股"

        stocks.append({
            "symbol": code,
            "name": info.get("name", ""),
            "price": _safe_float(daily.get("close")),
            "pctChange": _safe_float(daily.get("pct_chg")),
            "volume": f"{(vol / 10000):.1f}万" if vol else "0",
            "turnover": f"{(amount / 100000):.2f}亿" if amount else "0",
            "industry": industry,
            "concepts": [industry],
            "pe": _safe_float(basic.get("pe_ttm")),
            "pb": _safe_float(basic.get("pb")),
            "marketCap": round(total_mv / 10000) if total_mv else 0,
        })

    return stocks


def fetch_chinext_stocks(full_market: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从全市场数据中筛选创业板股票（代码以 3 开头）。"""
    chinext = []
    for stock in full_market:
        if str(stock.get("symbol", "")).startswith("3"):
            chinext.append({
                **stock,
                "industry": stock.get("industry") or "创业板",
                "concepts": stock.get("concepts") or ["成长", "热门"],
            })
    return chinext


# =========================================================================
# 概念板块（替代 push2.eastmoney.com 概念板块接口，改用 tushare ths_index）
# =========================================================================

def fetch_concept_board_list() -> List[Dict[str, Any]]:
    """通过 tushare ths_index 获取同花顺概念板块列表。"""
    rows = tushare_rows("ths_index", {"exchange": "A", "type": "N"},
                        "ts_code,name")
    return [{"code": r["ts_code"], "name": r.get("name", "")} for r in rows if r.get("ts_code")]


def fetch_concept_board_members(board_code: str, board_name: str) -> List[str]:
    """通过 tushare ths_member 获取概念板块成员股票代码。"""
    rows = tushare_rows("ths_member", {"ts_code": board_code}, "code")
    symbols = []
    seen: set[str] = set()
    for r in rows:
        code = str(r.get("code", "")).strip()
        if code and code not in seen:
            seen.add(code)
            symbols.append(code)
    print(f"[stocks-py] concept {board_name} -> {len(symbols)} symbols")
    return symbols


def build_stock_concept_map() -> Dict[str, List[str]]:
    """获取概念板块映射。优先使用本地缓存（stock_concept_map.json），
    仅在缓存不存在或设置 FORCE_CONCEPT_REFRESH=1 时才从 tushare 逐个拉取。
    概念板块成员变化不频繁，通常每周更新一次即可。"""

    # 尝试从本地缓存读取
    if not FORCE_CONCEPT_REFRESH:
        cached = read_json("stock_concept_map.json")
        if isinstance(cached, dict) and len(cached) > 100:
            print(f"[stocks-py] 使用本地概念板块缓存（{len(cached)} 只股票），跳过 tushare 拉取。"
                  f"设置 FORCE_CONCEPT_REFRESH=1 可强制刷新。")
            return cached

    print("[stocks-py] 从 tushare 拉取概念板块成员（约 400+ 板块，需要几分钟）...")
    try:
        concept_boards = fetch_concept_board_list()
    except Exception as error:
        print(f"[stocks-py] Failed to fetch concept board list: {error}")
        return {}

    concept_map: Dict[str, List[str]] = {}
    for index, board in enumerate(concept_boards, start=1):
        board_code = str(board.get("code", "")).strip()
        board_name = str(board.get("name", "")).strip()
        if not board_code or not board_name:
            continue

        try:
            symbols = fetch_concept_board_members(board_code, board_name)
        except Exception as error:
            print(f"[stocks-py] Failed to fetch concept members for {board_name}({board_code}): {error}")
            continue

        for symbol in symbols:
            concept_map.setdefault(symbol, []).append(board_name)

        if index % 20 == 0 or index == len(concept_boards):
            print(f"[stocks-py] Processed concept boards {index}/{len(concept_boards)}")
        time.sleep(0.05)

    for symbol, concepts in concept_map.items():
        concept_map[symbol] = sorted(set(concepts))

    return concept_map


def enrich_stock_concepts(stocks: List[Dict[str, Any]], concept_map: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for stock in stocks:
        symbol = str(stock.get("symbol", "")).strip()
        concepts = concept_map.get(symbol) or stock.get("concepts") or [stock.get("industry") or "A股"]
        enriched.append({**stock, "concepts": concepts})
    return enriched


def main() -> int:
    print("[stocks-py] Fetching stock snapshots via tushare...")
    concept_map = build_stock_concept_map()
    if not concept_map:
        print("[stocks-py] Concept map unavailable, continuing with industry fallback concepts")

    full_market = fetch_full_market_stocks()
    chinext = fetch_chinext_stocks(full_market)

    full_market = enrich_stock_concepts(full_market, concept_map)
    chinext = enrich_stock_concepts(chinext, concept_map)

    save_json("stock_list_full.json", full_market)
    save_json("stock_list_chinext.json", chinext)
    save_json("stock_concept_map.json", concept_map)
    print(f"[stocks-py] wrote {len(full_market)} full-market rows and {len(chinext)} chinext rows")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"[stocks-py] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
