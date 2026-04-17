from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_fetch_utils import (
    MARKET_DATA_DIR,
    read_json as read_local_json, save_json,
    tushare_index_kline, tushare_limit_up_pool, tushare_limit_down_pool, _fmt_date,
)


KLINE_DIR = MARKET_DATA_DIR / "klines"
KLINE_CACHE: Dict[str, List[dict[str, Any]]] = {}
LIMIT_UP_POOL_CACHE: Dict[str, List[dict[str, Any]]] = {}
BROKEN_POOL_CACHE: Dict[str, List[dict[str, Any]]] = {}


def load_json(file_name: str) -> Any:
    return read_local_json(file_name, None)


def is_chinext_symbol(symbol: str) -> bool:
    return str(symbol).startswith(("300", "301"))


def is_main_board_symbol(symbol: str) -> bool:
    return str(symbol).startswith(("600", "601", "603", "605", "000", "001", "002", "003"))


def build_board_height_entry_from_pool(date_str: str, today_pool: List[dict[str, Any]]) -> dict[str, Any]:
    main_board = [
        item for item in today_pool
        if is_main_board_symbol(str(item.get("symbol", "")))
    ]
    chinext_board = [
        item for item in today_pool
        if is_chinext_symbol(str(item.get("symbol", "")))
    ]

    def filter_by_count(pool: List[dict[str, Any]], count: int) -> List[dict[str, Any]]:
        return [item for item in pool if int(item.get("boardCount") or 0) == count]

    main_highest = max([int(item.get("boardCount") or 0) for item in main_board] or [0])
    main_second = max(
        [int(item.get("boardCount") or 0) for item in main_board if int(item.get("boardCount") or 0) < main_highest] or [0]
    )
    chinext_highest = max([int(item.get("boardCount") or 0) for item in chinext_board] or [0])

    main_highest_stocks = filter_by_count(main_board, main_highest) if main_highest > 0 else []
    main_second_stocks = filter_by_count(main_board, main_second) if main_second > 0 else []
    chinext_highest_stocks = filter_by_count(chinext_board, chinext_highest) if chinext_highest > 0 else []

    def names(stocks: List[dict[str, Any]]) -> List[str]:
        return [str(stock.get("name", "")) for stock in stocks if stock.get("name")]

    def symbols(stocks: List[dict[str, Any]]) -> List[str]:
        return [str(stock.get("symbol", "")) for stock in stocks if stock.get("symbol")]

    return {
        "date": date_str[5:],
        "fullDate": date_str,
        "mainBoardHighest": main_highest,
        "mainBoardHighestNames": names(main_highest_stocks),
        "mainBoardHighestSymbols": symbols(main_highest_stocks),
        "mainBoardSecondHighest": main_second,
        "mainBoardSecondHighestNames": names(main_second_stocks),
        "mainBoardSecondHighestSymbols": symbols(main_second_stocks),
        "chinextHighest": chinext_highest,
        "chinextHighestNames": names(chinext_highest_stocks),
        "chinextHighestSymbols": symbols(chinext_highest_stocks),
    }


def load_local_kline_file(symbol: str) -> Any:
    path = KLINE_DIR / f"{symbol}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def get_stock_kline(symbol: str, period: int = 101) -> List[dict[str, Any]]:
    """从本地 kline 文件读取 K 线数据（由 fetch_kline_library.py 批量同步）。"""
    cache_key = f"{symbol}_{period}"
    if cache_key in KLINE_CACHE:
        return KLINE_CACHE[cache_key]

    local_payload = load_local_kline_file(symbol)
    local_series = (
        local_payload.get("periods", {}).get(str(period))
        if isinstance(local_payload, dict)
        else None
    )
    if isinstance(local_series, list) and local_series:
        KLINE_CACHE[cache_key] = local_series
        return local_series

    KLINE_CACHE[cache_key] = []
    return []


def get_single_day_close_change(symbol: str, date_str: str) -> Optional[float]:
    klines = get_stock_kline(symbol, 101)
    if not klines:
        return None

    target_index = -1
    for index in range(len(klines) - 1, -1, -1):
        if str(klines[index].get("date", "")) <= date_str:
            target_index = index
            break

    if target_index <= 0:
        return None

    today = klines[target_index]
    prev = klines[target_index - 1]
    prev_close = float(prev.get("close", 0))
    if prev_close <= 0:
        return None

    return ((float(today.get("close", 0)) - prev_close) / prev_close) * 100


def get_single_day_performance(symbol: str, date_str: str) -> Optional[dict[str, Any]]:
    klines = get_stock_kline(symbol, 101)
    if not klines:
        return None

    target_index = -1
    for index in range(len(klines) - 1, -1, -1):
        if str(klines[index].get("date", "")) <= date_str:
            target_index = index
            break

    if target_index <= 0:
        return None

    today = klines[target_index]
    prev = klines[target_index - 1]
    prev_close = float(prev.get("close", 0))
    if prev_close <= 0:
        return None

    open_pct = ((float(today.get("open", 0)) - prev_close) / prev_close) * 100
    close_pct = ((float(today.get("close", 0)) - prev_close) / prev_close) * 100
    is_one_word = (
        abs(float(today.get("open", 0)) - float(today.get("close", 0))) < 0.001
        and abs(float(today.get("open", 0)) - float(today.get("high", 0))) < 0.001
        and abs(float(today.get("open", 0)) - float(today.get("low", 0))) < 0.001
    )

    return {
        "openPct": round(open_pct, 2),
        "closePct": round(close_pct, 2),
        "isOneWord": is_one_word,
    }


def fetch_limit_up_pool(date_str: str) -> List[dict[str, Any]]:
    """通过 tushare limit_list_d 获取涨停池。"""
    if date_str in LIMIT_UP_POOL_CACHE:
        return LIMIT_UP_POOL_CACHE[date_str]

    api_date = date_str.replace("-", "")
    pool = tushare_limit_up_pool(api_date)
    result = [
        {
            "symbol": item.get("symbol", ""),
            "name": item.get("name", ""),
            "boardCount": int(item.get("boardCount") or 1),
            "limitUpTime": item.get("limitUpTime", ""),
            "industry": item.get("industry", ""),
            "pctChange": item.get("pctChange", 0),
        }
        for item in pool
    ]
    LIMIT_UP_POOL_CACHE[date_str] = result
    return result


def fetch_broken_pool(date_str: str) -> List[dict[str, Any]]:
    """通过 tushare limit_list_d (limit_type='Z') 获取炸板池。
    如果 tushare 不支持 Z 类型，则从涨停池中筛选跌幅较大的作为近似。"""
    if date_str in BROKEN_POOL_CACHE:
        return BROKEN_POOL_CACHE[date_str]

    api_date = date_str.replace("-", "")
    from data_fetch_utils import tushare_rows
    rows = tushare_rows(
        "limit_list_d",
        {"trade_date": api_date, "limit_type": "Z"},
        "ts_code,name,close,pct_chg",
    )

    if rows:
        result = [
            {
                "symbol": (r.get("ts_code", "").split(".")[0] if "." in r.get("ts_code", "") else r.get("ts_code", "")),
                "name": r.get("name", ""),
                "pctChange": float(r.get("pct_chg") or 0),
            }
            for r in rows
        ]
    else:
        # fallback: 返回空列表
        result = []

    BROKEN_POOL_CACHE[date_str] = result
    return result


def fetch_market_index_amount_series(secid: str) -> Dict[str, float]:
    parts = secid.split(".")
    if len(parts) != 2:
        return {}
    market, code = parts
    suffix = ".SH" if market == "1" else ".SZ"
    ts_code = f"{code}{suffix}"
    try:
        rows = tushare_index_kline(ts_code, limit=12)
        result: Dict[str, float] = {}
        for r in rows:
            date_str = _fmt_date(r.get("trade_date", ""))
            result[date_str] = float(r.get("vol", 0) or 0)
        return result
    except Exception:
        return {}


def get_recent_trading_dates(count: int) -> List[str]:
    sentiment = load_json("sentiment.json")
    if isinstance(sentiment, list) and sentiment:
        dates = sorted(
            str(item.get("date"))
            for item in sentiment
            if isinstance(item, dict) and isinstance(item.get("date"), str)
        )
        return dates[max(len(dates) - count - 2, 0):]

    rows = tushare_index_kline("000001.SH", limit=40)
    dates = sorted(_fmt_date(r.get("trade_date", "")) for r in rows)
    return dates[max(len(dates) - count - 2, 0):]


def build_structure_entries_from_sentiment(items: List[dict[str, Any]]) -> List[dict[str, Any]]:
    entries: List[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: str(row.get("date", ""))):
        raw_zt = item.get("rawZt") or {}
        counts = raw_zt.get("counts") or {}
        total_limit_up_count = int(item.get("limitUpCount") or 0)
        if not counts or total_limit_up_count <= 0:
            continue

        first_board_count = int(counts.get("1") or counts.get(1) or 0)
        second_board_count = int(counts.get("2") or counts.get(2) or 0)
        third_board_count = int(counts.get("3") or counts.get(3) or 0)
        high_board_count = sum(
            int(count)
            for board, count in counts.items()
            if int(board) >= 4
        )
        relay_count = max(total_limit_up_count - first_board_count, 0)
        date_str = str(item.get("date", ""))
        entries.append(
            {
                "date": date_str[5:] if len(date_str) >= 5 else date_str,
                "firstBoardCount": first_board_count,
                "secondBoardCount": second_board_count,
                "thirdBoardCount": third_board_count,
                "highBoardCount": high_board_count,
                "totalLimitUpCount": total_limit_up_count,
                "firstBoardRatio": round((first_board_count / total_limit_up_count) * 100, 1)
                if total_limit_up_count > 0
                else 0,
                "relayCount": relay_count,
                "highBoardRatio": round((high_board_count / total_limit_up_count) * 100, 1)
                if total_limit_up_count > 0
                else 0,
            }
        )
    return entries


def get_leader_status_label(params: dict[str, Any]) -> str:
    is_one_word = bool(params.get("isOneWord"))
    continued = bool(params.get("continued"))
    next_close_pct = params.get("nextClosePct")
    leader_count = int(params.get("leaderCount") or 0)
    leader_board_count = int(params.get("leaderBoardCount") or 0)
    if next_close_pct is None:
        if leader_count >= 2 and leader_board_count >= 4:
            return "高标抱团"
        if is_one_word:
            return "一字观察"
        return "待次日确认"
    if is_one_word and continued:
        return "一字加速"
    if continued and float(next_close_pct) >= 0:
        return "强势晋级"
    if float(next_close_pct) >= 3:
        return "断板承接"
    if float(next_close_pct) >= 0:
        return "高位分歧"
    if float(next_close_pct) > -5:
        return "分歧转弱"
    return "退潮承压"


def main() -> int:
    print("[cycle-py] Building offline cycle snapshots...")
    sentiment = load_json("sentiment.json") or []
    structure = (
        build_structure_entries_from_sentiment(sentiment)[-12:]
        if isinstance(sentiment, list)
        else []
    )
    save_json("limit_up_structure.json", structure)

    trading_dates = get_recent_trading_dates(12)
    repair: List[dict[str, Any]] = []
    leader: List[dict[str, Any]] = []
    board_height: List[dict[str, Any]] = []
    high_risk: List[dict[str, Any]] = []

    for index, current_date in enumerate(trading_dates):
        next_date = trading_dates[index + 1] if index < len(trading_dates) - 1 else None
        today_pool = fetch_limit_up_pool(current_date)
        broken_pool = fetch_broken_pool(current_date)

        if today_pool:
            board_height.append(build_board_height_entry_from_pool(current_date, today_pool))

        if next_date:
            broken_repair_count = 0
            big_face_count = 0
            big_face_repair_count = 0
            for stock in broken_pool:
                next_change = get_single_day_close_change(stock["symbol"], next_date)
                repaired = next_change is not None and next_change > 0
                if repaired:
                    broken_repair_count += 1
                if float(stock.get("pctChange", 0)) <= -5:
                    big_face_count += 1
                    if repaired:
                        big_face_repair_count += 1
            repair.append(
                {
                    "date": current_date[5:],
                    "brokenCount": len(broken_pool),
                    "brokenRepairCount": broken_repair_count,
                    "brokenRepairRate": round((broken_repair_count / len(broken_pool)) * 100, 1)
                    if broken_pool
                    else 0,
                    "bigFaceCount": big_face_count,
                    "bigFaceRepairCount": big_face_repair_count,
                    "bigFaceRepairRate": round((big_face_repair_count / big_face_count) * 100, 1)
                    if big_face_count > 0
                    else 0,
                }
            )

        if today_pool:
            leader_board_count = max(int(item.get("boardCount") or 0) for item in today_pool)
            leaders = [item for item in today_pool if int(item.get("boardCount") or 0) == leader_board_count]
            leaders_sorted = sorted(
                leaders,
                key=lambda item: str(item.get("limitUpTime") or "99:99:99"),
            )
            leader_stock = leaders_sorted[0]
            second_highest_board = max(
                [int(item.get("boardCount") or 0) for item in today_pool if int(item.get("boardCount") or 0) < leader_board_count]
                or [0]
            )
            three_plus_count = len([item for item in today_pool if int(item.get("boardCount") or 0) >= 3])

            continued_count = 0
            next_open_pct = None
            next_close_pct = None
            if next_date:
                next_pool = fetch_limit_up_pool(next_date)
                next_board_map = {
                    item["symbol"]: int(item.get("boardCount") or 0)
                    for item in next_pool
                }
                continued_count = len(
                    [item for item in leaders if next_board_map.get(item["symbol"], 0) > leader_board_count]
                )
                next_performance = get_single_day_performance(leader_stock["symbol"], next_date)
                if next_performance:
                    next_open_pct = next_performance.get("openPct")
                    next_close_pct = next_performance.get("closePct")

            leader_performance = get_single_day_performance(leader_stock["symbol"], current_date)
            is_one_word = bool(leader_performance.get("isOneWord")) if leader_performance else False

            leader.append(
                {
                    "date": current_date[5:],
                    "leaderSymbol": leader_stock["symbol"],
                    "leaderName": leader_stock["name"],
                    "leaderBoardCount": leader_board_count,
                    "leaderCount": len(leaders),
                    "secondHighestBoard": second_highest_board,
                    "threePlusCount": three_plus_count,
                    "continuedCount": continued_count,
                    "nextOpenPct": next_open_pct,
                    "nextClosePct": next_close_pct,
                    "isOneWord": is_one_word,
                    "statusLabel": get_leader_status_label(
                        {
                            "isOneWord": is_one_word,
                            "continued": continued_count > 0,
                            "nextClosePct": next_close_pct,
                            "leaderCount": len(leaders),
                            "leaderBoardCount": leader_board_count,
                        }
                    ),
                }
            )

        if next_date:
            high_board_pool = [item for item in today_pool if int(item.get("boardCount") or 0) >= 4]
            a_kill_count = 0
            weak_count = 0
            for stock in high_board_pool:
                next_change = get_single_day_close_change(stock["symbol"], next_date)
                if next_change is None:
                    continue
                if next_change <= -8:
                    a_kill_count += 1
                if next_change < 0:
                    weak_count += 1

            broken_rate = round((len(broken_pool) / len(today_pool)) * 100, 1) if today_pool else 0
            risk_level = (
                "high"
                if a_kill_count >= 2 or broken_rate >= 35
                else "medium"
                if a_kill_count >= 1 or broken_rate >= 20 or weak_count >= 2
                else "low"
            )
            high_risk.append(
                {
                    "date": current_date[5:],
                    "highBoardCount": len(high_board_pool),
                    "aKillCount": a_kill_count,
                    "weakCount": weak_count,
                    "brokenCount": len(broken_pool),
                    "brokenRate": broken_rate,
                    "riskLevel": risk_level,
                }
            )

        time.sleep(0.04)

    save_json("repair_rate.json", repair[-12:])
    save_json("leader_state.json", leader[-12:])
    save_json("board_height_history.json", board_height[-30:])
    save_json("high_risk.json", high_risk[-6:])

    sh_series = fetch_market_index_amount_series("1.000001")
    sz_series = fetch_market_index_amount_series("0.399001")
    all_dates = sorted(set(sh_series.keys()) | set(sz_series.keys()))[-8:]
    volume = []
    for index, date in enumerate(all_dates):
        amount = sh_series.get(date, 0) + sz_series.get(date, 0)
        prev_amount = (
            sh_series.get(all_dates[index - 1], 0) + sz_series.get(all_dates[index - 1], 0)
            if index > 0
            else 0
        )
        change_rate = (
            round(((amount - prev_amount) / prev_amount) * 100, 2)
            if index > 0 and prev_amount > 0
            else None
        )
        if amount > 0:
            volume.append(
                {
                    "date": date[5:],
                    "amount": round(amount / 100000000),
                    "changeRate": change_rate,
                }
            )
    save_json("market_volume_trend.json", volume)

    latest_sentiment = sentiment[-1] if isinstance(sentiment, list) and sentiment else None
    previous_sentiment = sentiment[-2] if isinstance(sentiment, list) and len(sentiment) > 1 else None
    latest_structure = structure[-1] if structure else None
    latest_repair = repair[-1] if repair else None
    latest_leader = leader[-1] if leader else None
    latest_volume = volume[-1] if volume else None
    previous_volume = volume[-2] if len(volume) > 1 else None
    latest_risk = high_risk[-1] if high_risk else None

    if latest_volume and previous_volume and latest_volume.get("changeRate") is not None and previous_volume.get("changeRate") is not None:
        if latest_volume["changeRate"] > 0 and previous_volume["changeRate"] > 0:
            volume_state = "持续放量"
        elif latest_volume["changeRate"] < 0 and previous_volume["changeRate"] < 0:
            volume_state = "缩量再缩量"
        elif latest_volume["changeRate"] > 0 and latest_sentiment and previous_sentiment and float(latest_sentiment.get("value", 0)) <= float(previous_sentiment.get("value", 0)):
            volume_state = "放量滞涨"
        else:
            volume_state = "存量震荡"
    else:
        volume_state = "存量震荡"

    stage = "分歧"
    reasons: List[str] = []
    if latest_risk and (
        latest_risk.get("riskLevel") == "high"
        or float((latest_leader or {}).get("nextClosePct") or 0) <= -5
        or float((latest_repair or {}).get("brokenRepairRate") or 0) < 20
    ):
        stage = "退潮"
        reasons.append("高位负反馈明显，龙头或高标承压")
    elif latest_sentiment and int(latest_sentiment.get("height") or 0) <= 2 and int(latest_sentiment.get("limitUpCount") or 0) < 20:
        stage = "冰点"
        reasons.append("连板高度与涨停家数均处于低位")
    elif latest_repair and latest_leader and float(latest_repair.get("brokenRepairRate") or 0) >= 35 and float(latest_leader.get("nextClosePct") or -99) >= 0 and volume_state != "缩量再缩量":
        stage = "修复"
        reasons.append("修复率回升，龙头次日反馈转正")
    elif latest_sentiment and latest_structure and latest_leader and float(latest_sentiment.get("value") or 0) >= 5 and int(latest_structure.get("highBoardCount") or 0) >= 3 and int(latest_leader.get("leaderBoardCount") or 0) >= 5 and volume_state != "缩量再缩量":
        stage = "主升"
        reasons.append("高标梯队和赚钱效应同步扩散")
    elif latest_structure and (
        float(latest_structure.get("firstBoardRatio") or 0) >= 60
        or int((latest_leader or {}).get("leaderBoardCount") or 0) <= 4
    ):
        stage = "试错"
        reasons.append("首板占比较高，资金仍在低位试错")

    if volume_state == "缩量再缩量":
        reasons.append("量能连续回落，情绪支撑趋弱")
    elif volume_state == "持续放量":
        reasons.append("量能持续抬升，增量资金仍在参与")
    elif volume_state == "放量滞涨":
        reasons.append("量能放大但情绪指标未同步走强")

    if latest_risk and int(latest_risk.get("aKillCount") or 0) > 0:
        reasons.append(f"高位A杀样本 {latest_risk.get('aKillCount')} 家")
    elif latest_repair and float(latest_repair.get("brokenRepairRate") or 0) >= 35:
        reasons.append("炸板修复率改善，亏钱效应减弱")

    confidence_base = (
        72
        if stage == "主升"
        else 68
        if stage == "修复"
        else 75
        if stage == "退潮"
        else 70
        if stage == "冰点"
        else 62
    ) + (
        6
        if (latest_risk or {}).get("riskLevel") == "low"
        else 8
        if (latest_risk or {}).get("riskLevel") == "high"
        else 3
    ) + (6 if volume_state in {"持续放量", "缩量再缩量"} else 0)

    save_json(
        "cycle_overview.json",
        {
            "stage": stage,
            "confidence": min(95, confidence_base),
            "riskLevel": "高风险"
            if (latest_risk or {}).get("riskLevel") == "high"
            else "中风险"
            if (latest_risk or {}).get("riskLevel") == "medium"
            else "低风险",
            "volumeState": volume_state,
            "latestVolumeAmount": latest_volume.get("amount") if latest_volume else None,
            "volumeChangeRate": latest_volume.get("changeRate") if latest_volume else None,
            "reasons": reasons[:3],
        },
    )

    print("[cycle-py] wrote cycle snapshot files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"[cycle-py] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
