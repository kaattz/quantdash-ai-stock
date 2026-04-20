"""数据库连接管理，提供统一的上下文管理器替代各处直接 ``sqlite3.connect``。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from server.shared.runtime import AUTH_DB_PATH


@contextmanager
def get_db_connection(*, row_factory: bool = False) -> Iterator[sqlite3.Connection]:
    """获取 SQLite 数据库连接的上下文管理器。

    Parameters
    ----------
    row_factory:
        为 ``True`` 时将 ``conn.row_factory`` 设为 ``sqlite3.Row``，
        使查询结果可通过列名访问。

    Yields
    ------
    sqlite3.Connection
        配置好 PRAGMA 的数据库连接。正常退出时自动 commit，
        异常时自动 rollback，最终始终 close。
    """
    conn = sqlite3.connect(AUTH_DB_PATH)
    try:
        # 启用外键约束、WAL 日志模式和忙等待超时
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        if row_factory:
            conn.row_factory = sqlite3.Row

        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
