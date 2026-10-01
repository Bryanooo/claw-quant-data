"""
ST股票列表采集器（含风险警示板明细）
接口：
  - stock_st  → ST股票列表（3000积分，每天9:20更新）
  - st        → ST风险警示板明细（6000积分）

两步走：
1. 每日调 stock_st 获取当日所有ST股票列表
2. 按发布日期/实施日期增量获取当日变更，并继承上一快照；仅对首次出现且
   当日事件缺失的标的调用单标的 st 接口兜底

注意：此采集器的 fetch 方法做了两个 API 的合并，store 也因此保留了自定义逻辑。
"""

import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str


class StockSTCollector(BaseCollector):
    API_NAME = "stock_st"  # 仅用于标识，实际 fetch 也会调 st 接口
    table_name = "stock_st"
    pk_columns = ["ts_code", "trade_date"]
    DETAIL_FIELDS = "ts_code,name,pub_date,imp_date,st_tpye,st_reason,st_explain"

    # ── step 1: 获取当日ST列表 ──
    def fetch_stock_st(self, trade_date: str) -> pd.DataFrame:
        """调 stock_st 接口获取当日ST股票列表"""
        df = self.pro.stock_st(
            trade_date=trade_date,
            fields="ts_code,name,trade_date,type,type_name"
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts_code", "name", "trade_date", "type", "type_name"])
        return df

    # ── step 2: 获取单只股票的风险警示明细 ──
    def fetch_st_detail(self, ts_code: str) -> list[dict]:
        """调 st 接口获取某只股票的ST警示板明细"""
        df = self.pro.st(
            ts_code=ts_code,
            fields=self.DETAIL_FIELDS,
        )
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    def fetch_st_updates(self, trade_date: str) -> list[dict]:
        """Fetch only detail events published or taking effect on a date.

        ``st`` is an event history endpoint rather than a daily snapshot.  Two
        bounded date queries cover both announcements and effective changes;
        querying every currently-ST security would turn one daily job into
        hundreds of upstream calls.
        """
        frames: list[pd.DataFrame] = []
        for date_field in ("pub_date", "imp_date"):
            frame = self.pro.st(
                **{date_field: trade_date, "fields": self.DETAIL_FIELDS}
            )
            if frame is not None and not frame.empty:
                frames.append(frame)
        if not frames:
            return []
        combined = pd.concat(frames, ignore_index=True)
        return combined.drop_duplicates().to_dict(orient="records")

    def _load_previous_details(
        self,
        ts_codes: list[str],
        trade_date: str,
    ) -> dict[str, dict]:
        """Load the latest known detail state before ``trade_date`` in one query."""
        if not ts_codes:
            return {}
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (ts_code)
                           ts_code, pub_date, imp_date, st_type,
                           st_reason, st_explain
                    FROM stock_st
                    WHERE ts_code = ANY(%s)
                      AND trade_date < %s::DATE
                      AND (pub_date IS NOT NULL OR imp_date IS NOT NULL
                           OR st_type IS NOT NULL OR st_reason IS NOT NULL
                           OR st_explain IS NOT NULL)
                    ORDER BY ts_code, trade_date DESC
                    """,
                    (ts_codes, trade_date),
                )
                return {row["ts_code"]: dict(row) for row in cur.fetchall()}
        finally:
            conn.close()

    @staticmethod
    def _latest_details(records: list[dict]) -> dict[str, dict]:
        """Select the newest event for every security deterministically."""
        result: dict[str, dict] = {}
        for record in records:
            code = safe_str(record.get("ts_code"))
            if not code:
                continue
            candidate_key = (
                safe_str(record.get("imp_date")) or "",
                safe_str(record.get("pub_date")) or "",
            )
            current = result.get(code)
            current_key = (
                safe_str(current.get("imp_date")) or "",
                safe_str(current.get("pub_date")) or "",
            ) if current else ("", "")
            if current is None or candidate_key >= current_key:
                result[code] = record
        return result

    # ── 采集入口 ──
    def fetch(self, **params) -> pd.DataFrame:
        """
        参数：
          - trade_date: 交易日期 YYYYMMDD
        """
        trade_date = params.get("trade_date", "")
        include_details = bool(params.get("include_details", False))
        if not trade_date:
            raise ValueError("必须指定 trade_date")

        # step 1: 获取ST列表
        self.logger.info(f"📋 step1: 获取 {trade_date} ST列表...")
        list_df = self.fetch_stock_st(trade_date)
        if list_df.empty:
            return list_df

        stocks = list_df.to_dict(orient="records")
        self.logger.info(f"  共 {len(stocks)} 只ST标的")

        # Historical stock_st completeness is one bounded list request per
        # date.  The separate ``st`` detail endpoint is security-scoped and
        # date-independent; refetching it for every stock on every historical
        # date multiplies a 1-request leaf into ~200 requests without adding
        # historical information.  Daily refresh may explicitly enrich the
        # current snapshot once.
        if not include_details:
            return list_df.assign(
                pub_date=None,
                imp_date=None,
                st_type=None,
                st_reason=None,
                st_explain=None,
            )

        # step 2: 当日事件覆盖前日状态；仅首次出现的标的逐只兜底。
        codes = [s["ts_code"] for s in stocks]
        detail_map = self._load_previous_details(codes, trade_date)
        updates = self._latest_details(self.fetch_st_updates(trade_date))
        detail_map.update(updates)

        missing_codes = [code for code in codes if code not in detail_map]
        if missing_codes:
            self.logger.info(
                "🔍 step2: %s 个首次出现标的缺少当日事件，执行单标的兜底...",
                len(missing_codes),
            )
        for code in missing_codes:
            details = self.fetch_st_detail(code)
            selected = self._latest_details(details).get(code)
            if selected:
                detail_map[code] = selected

        # step 3: 合并数据
        merged = []
        for s in stocks:
            code = s["ts_code"]
            row = {
                "ts_code": code,
                "name": s.get("name"),
                "trade_date": s.get("trade_date"),
                "type": s.get("type"),
                "type_name": s.get("type_name"),
                "pub_date": None,
                "imp_date": None,
                "st_type": None,
                "st_reason": None,
                "st_explain": None,
            }
            if code in detail_map:
                d = detail_map[code]
                row["pub_date"] = safe_str(d.get("pub_date"))
                row["imp_date"] = safe_str(d.get("imp_date"))
                # Tushare historically exposed the misspelled ``st_tpye``;
                # accept both spellings so a provider correction is harmless.
                row["st_type"] = safe_str(d.get("st_type") or d.get("st_tpye"))
                row["st_reason"] = safe_str(d.get("st_reason"))
                row["st_explain"] = safe_str(d.get("st_explain"))
            merged.append(row)

        return pd.DataFrame(merged)

    def store(self, df: pd.DataFrame) -> int:
        """自定义 store：合并了 stock_st 和 st 两个接口的数据"""
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0

                insert_sql = """
                    INSERT INTO stock_st (ts_code, name, trade_date, type, type_name,
                                          pub_date, imp_date, st_type, st_reason, st_explain)
                    VALUES %s
                    ON CONFLICT (ts_code, trade_date) DO UPDATE
                    SET name = EXCLUDED.name,
                        type = EXCLUDED.type,
                        type_name = EXCLUDED.type_name,
                        pub_date = COALESCE(EXCLUDED.pub_date, stock_st.pub_date),
                        imp_date = COALESCE(EXCLUDED.imp_date, stock_st.imp_date),
                        st_type = COALESCE(EXCLUDED.st_type, stock_st.st_type),
                        st_reason = COALESCE(EXCLUDED.st_reason, stock_st.st_reason),
                        st_explain = COALESCE(EXCLUDED.st_explain, stock_st.st_explain)
                """

                vals = [tuple(r.get(c) for c in [
                    "ts_code", "name", "trade_date", "type", "type_name",
                    "pub_date", "imp_date", "st_type", "st_reason", "st_explain"
                ]) for r in rows]

                psycopg2.extras.execute_values(cur, insert_sql, vals, page_size=1000)

            conn.commit()
            return len(rows)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
