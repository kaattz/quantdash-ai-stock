"""从 tushare stock_company 接口获取上市公司基本信息（主营业务、公司介绍等），
写入 data/markets/a_share/stock_company.json 供前端 ProfilePanel 使用。

用法：
    python scripts/fetch_stock_company.py

输出文件格式：
    {
      "updated": "2026-04-17",
      "data": {
        "600519": {
          "name": "贵州茅台",
          "chairman": "张德芹",
          "main_business": "...",
          "introduction": "...",
          "reg_capital": 12.56,
          "setup_date": "1999-11-20",
          "province": "贵州",
          "city": "遵义",
          "website": "www.moutaichina.com"
        },
        ...
      }
    }
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from data_fetch_utils import save_json, tushare_rows, read_json
from data_paths import A_SHARE_DIR

OUTPUT_FILE = "stock_company.json"
# tushare stock_company 每次最多返回约 5000 条，按交易所分批拉取
EXCHANGES = ["SSE", "SZSE"]


def fetch_company_info() -> Dict[str, Dict[str, Any]]:
    """从 tushare stock_company 接口获取全部上市公司信息。"""
    fields = (
        "ts_code,chairman,manager,secretary,reg_capital,"
        "setup_date,province,city,introduction,website,"
        "main_business,business_scope,employees"
    )

    result: Dict[str, Dict[str, Any]] = {}

    for exchange in EXCHANGES:
        print(f"[stock-company] 获取 {exchange} 上市公司信息...")
        try:
            rows = tushare_rows("stock_company", {"exchange": exchange}, fields)
        except Exception as e:
            print(f"[stock-company] 获取 {exchange} 失败: {e}")
            rows = []

        for row in rows:
            ts_code = row.get("ts_code", "")
            symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
            if not symbol:
                continue

            result[symbol] = {
                "chairman": row.get("chairman") or "",
                "manager": row.get("manager") or "",
                "secretary": row.get("secretary") or "",
                "reg_capital": row.get("reg_capital"),
                "setup_date": row.get("setup_date") or "",
                "province": row.get("province") or "",
                "city": row.get("city") or "",
                "introduction": row.get("introduction") or "",
                "website": row.get("website") or "",
                "main_business": row.get("main_business") or "",
                "business_scope": row.get("business_scope") or "",
                "employees": row.get("employees"),
            }

        print(f"[stock-company] {exchange}: 获取到 {len(rows)} 家公司信息")
        time.sleep(0.5)  # tushare 限流

    return result


def build_stock_company_data() -> int:
    """主入口：拉取公司信息并写入本地 JSON。"""
    # 检查是否今天已经同步过
    existing = read_json(OUTPUT_FILE)
    today = datetime.now().strftime("%Y-%m-%d")
    if (
        isinstance(existing, dict)
        and existing.get("updated") == today
        and isinstance(existing.get("data"), dict)
        and len(existing["data"]) > 100
    ):
        print(f"[stock-company] 数据已是最新 ({today})，跳过同步。")
        return 0

    print("[stock-company] 开始从 tushare 获取上市公司信息...")
    data = fetch_company_info()

    if not data:
        print("[stock-company] 未获取到任何公司信息，跳过写入。")
        return 1

    payload = {
        "updated": today,
        "count": len(data),
        "data": data,
    }

    save_json(OUTPUT_FILE, payload)
    print(f"[stock-company] 完成，共 {len(data)} 家公司信息已写入 {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(build_stock_company_data())
    except Exception as exc:
        print(f"[stock-company] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
