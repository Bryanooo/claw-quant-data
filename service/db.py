"""
=============================================================================
数据库连接管理
=============================================================================

统一管理 PostgreSQL 连接，所有 service tools 都从这里获取连接。
"""

import tushare as ts
import psycopg2
import psycopg2.extras
from service.config import DB_CONFIG, get_env_tushare_token
from service.tushare_rate_limit import install_distributed_rate_limit


def get_conn():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)


def get_pro() -> ts.pro_api:
    """
    获取 Tushare Pro API 实例。
    供需要直调 Tushare 的 service tools 使用。
    """
    from collectors.base import get_config
    token = get_env_tushare_token() or get_config("tushare.token")
    if not token:
        raise RuntimeError(
            "Tushare token is not configured; set TUSHARE_TOKEN or "
            "sys_config['tushare.token']"
        )
    ts.set_token(token)
    return install_distributed_rate_limit(ts.pro_api())


def query(sql: str, params: tuple = None, as_dict: bool = True) -> list[dict]:
    """
    通用查询，返回 dict 列表。

    用法：
      query("SELECT * FROM trade_cal WHERE cal_date = %s", ("20260512",))
      query("SELECT * FROM trade_cal LIMIT %s", (5,))
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def execute(sql: str, params: tuple | None = None) -> int:
    """Execute one mutating statement in its own committed transaction."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            affected = cur.rowcount
        conn.commit()
        return affected
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
