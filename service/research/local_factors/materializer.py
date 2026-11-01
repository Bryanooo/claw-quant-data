"""Database materializer for the versioned local 272-factor snapshot."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from typing import Any
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2.extras

from service.db import get_conn

from .alpha101 import Alpha101Panel
from .catalog import (
    FACTOR_COUNT,
    FACTOR_IMPLEMENTATION_VERSION,
    FACTOR_SCHEMA_VERSION,
    FACTOR_SPECS,
    MAX_ABS_FACTOR_VALUE,
)
from .financial import FinancialCrossSection, FinancialFactorEvaluator
from .market import MarketFactorEvaluator, MarketFactorPanel
from .provider_validation import write_provider_validation


# The schema digest is the immutable identity of the V4 formula contract. It
# must not change merely because transaction handling, batching or logging in
# this module changes; doing so previously made harmless deployment changes
# look like a formula migration. Actual formula changes require a new schema
# version and a newly reviewed digest.
FORMULA_DIGEST = "f69d586a6b77870c266925568f5e411550e6aeb54ff5aec694f4d0ae2bb84727"

# Keep a separate implementation fingerprint for row-level lineage. This may
# change when execution code changes without invalidating the 272-position
# formula ABI.
IMPLEMENTATION_DIGEST = hashlib.sha256(json.dumps(
    {
        "implementation_version": FACTOR_IMPLEMENTATION_VERSION,
        "source_digests": {
            name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ("materializer.py", "financial.py", "market.py", "alpha101.py", "alpha101_formulas.py", "quality.py")
        } | {name: hashlib.sha256((Path(__file__).parents[2] / name).read_bytes()).hexdigest()
             for name in ("research/technical_indicators.py", "orchestration_v2/transformations.py")},
        "factors": [
            {
                "position": item.position,
                "name": item.name,
                "family": item.family,
                "formula": item.formula,
                "overlap": (
                    item.overlap_kind, item.overlap_dataset,
                    item.overlap_field, item.convention_note,
                ),
            }
            for item in FACTOR_SPECS
        ],
    },
    ensure_ascii=False,
    separators=(",", ":"),
).encode()).hexdigest()

MAX_MARKET_LOOKBACK = 1325


def sync_factor_catalog(connection: Any) -> None:
    """Upsert the immutable code-owned position catalog into PostgreSQL."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO local_factor_schema (
                schema_version, factor_count, formula_digest,
                lifecycle_status, description, activated_at
            ) VALUES (%s, %s, %s, 'active', %s, NOW())
            ON CONFLICT (schema_version) DO UPDATE SET
                factor_count=EXCLUDED.factor_count,
                formula_digest=EXCLUDED.formula_digest,
                description=EXCLUDED.description
            WHERE local_factor_schema.formula_digest=EXCLUDED.formula_digest
               OR local_factor_schema.formula_digest=repeat('0',64)
            """,
            (
                FACTOR_SCHEMA_VERSION, FACTOR_COUNT, FORMULA_DIGEST,
                "Local WorldQuant Alpha101 plus Tushare-compatible Growth, "
                "Liquidity, Momentum, Quality, Reversal, Risk, Size and Value factors",
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("factor schema formula changed: allocate a new version before publication")
        values = [(
            FACTOR_SCHEMA_VERSION, item.position, item.name, item.family,
            item.formula, item.computation_group, item.overlap_kind,
            item.overlap_dataset, item.overlap_field, item.convention_note,
        ) for item in FACTOR_SPECS]
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO local_factor_catalog (
                schema_version, factor_position, factor_name, factor_family,
                formula, computation_group, overlap_kind, overlap_dataset,
                overlap_field, convention_note
            ) VALUES %s
            ON CONFLICT (schema_version, factor_position) DO UPDATE SET
                factor_name=EXCLUDED.factor_name,
                factor_family=EXCLUDED.factor_family,
                formula=EXCLUDED.formula,
                computation_group=EXCLUDED.computation_group,
                overlap_kind=EXCLUDED.overlap_kind,
                overlap_dataset=EXCLUDED.overlap_dataset,
                overlap_field=EXCLUDED.overlap_field,
                convention_note=EXCLUDED.convention_note
            WHERE (
                local_factor_catalog.factor_name, local_factor_catalog.factor_family,
                local_factor_catalog.formula, local_factor_catalog.computation_group,
                local_factor_catalog.overlap_kind, local_factor_catalog.overlap_dataset,
                local_factor_catalog.overlap_field, local_factor_catalog.convention_note
            ) IS DISTINCT FROM (
                EXCLUDED.factor_name, EXCLUDED.factor_family,
                EXCLUDED.formula, EXCLUDED.computation_group,
                EXCLUDED.overlap_kind, EXCLUDED.overlap_dataset,
                EXCLUDED.overlap_field, EXCLUDED.convention_note
            )
            """,
            values,
            page_size=272,
        )
        cursor.execute(
            """
            SELECT count(*)
            FROM local_factor_catalog
            WHERE schema_version=%s
            """,
            (FACTOR_SCHEMA_VERSION,),
        )
        if int(cursor.fetchone()[0]) != FACTOR_COUNT:
            raise RuntimeError("local factor catalog did not persist all 272 positions")


def _read_frame(connection: Any, sql: str, params: tuple[Any, ...]) -> pd.DataFrame:
    # RealDictCursor creates one Python dict per source row; the 1,325-session
    # full-market input can exceed six million rows and previously peaked above
    # 20 GiB before calculation even began.  Stream ordinary tuples in bounded
    # chunks and attach column names once.
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [item.name for item in cursor.description]
        chunks: list[pd.DataFrame] = []
        while batch := cursor.fetchmany(100_000):
            chunks.append(pd.DataFrame.from_records(batch, columns=columns))
    if not chunks:
        return pd.DataFrame(columns=columns)
    if len(chunks) == 1:
        return chunks[0]
    return pd.concat(chunks, ignore_index=True, copy=False)


def _pivot(frame: pd.DataFrame, field: str, *, columns: pd.Index) -> pd.DataFrame:
    values = frame.pivot(index="trade_date", columns="ts_code", values=field)
    return values.reindex(columns=columns).sort_index().astype("float32")


def frame_digest(frame: pd.DataFrame) -> str:
    """Fingerprint consumed values, order, index and columns, not row counts."""
    digest = hashlib.sha256(repr(tuple(frame.columns)).encode())
    digest.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
    return digest.hexdigest()


def _fill_documented_suspension_sessions(
    matrices: dict[str, pd.DataFrame],
    traded_amount_cny: pd.DataFrame,
    suspension_rows: pd.DataFrame,
    listing_dates: pd.Series,
) -> tuple[pd.DataFrame, pd.Series, int]:
    """Apply the standard zero-return convention only to proven suspensions.

    A suspended stock has no provider daily row.  Leaving that cell as NaN
    makes every long rolling factor fail even though the absence is expected;
    filling every absence would hide real history gaps.  This helper therefore
    forward-fills prices and market value, and writes zero activity, only when
    ``suspend_d`` independently documents that exact security/date.
    """

    close = matrices["close"]
    mask = pd.DataFrame(False, index=close.index, columns=close.columns)
    if not suspension_rows.empty:
        suspensions = suspension_rows.copy()
        suspensions["trade_date"] = pd.to_datetime(suspensions["trade_date"])
        suspensions = suspensions.drop_duplicates(["trade_date", "ts_code"])
        present = suspensions[
            suspensions["trade_date"].isin(mask.index)
            & suspensions["ts_code"].isin(mask.columns)
        ]
        if not present.empty:
            coordinates = pd.MultiIndex.from_frame(
                present[["trade_date", "ts_code"]]
            )
            stacked = mask.stack(future_stack=True)
            stacked.loc[stacked.index.intersection(coordinates)] = True
            mask = stacked.unstack(fill_value=False).reindex_like(mask).astype(bool)

    documented_missing = close.isna() & mask
    previous_close = close.ffill()
    for field in ("open", "high", "low", "close"):
        matrices[field] = matrices[field].mask(
            documented_missing,
            previous_close,
        )
    for field in ("vol", "amount", "turnover_rate"):
        matrices[field] = matrices[field].mask(documented_missing, 0.0)
    for field in ("total_mv", "circ_mv"):
        matrices[field] = matrices[field].mask(
            documented_missing,
            matrices[field].ffill(),
        )
    traded_amount_cny = traded_amount_cny.mask(documented_missing, 0.0)

    parsed_listing = pd.to_datetime(
        listing_dates.reindex(close.columns),
        format="%Y%m%d",
        errors="coerce",
    )
    listed = pd.DataFrame(
        close.index.to_numpy()[:, None]
        >= parsed_listing.to_numpy()[None, :],
        index=close.index,
        columns=close.columns,
    )
    unexplained = (close.isna() & listed & ~mask).sum(axis=0).astype("int32")
    return traded_amount_cny, unexplained, int(documented_missing.sum().sum())


def _load_market_panel(
    connection: Any, target_date: date,
) -> tuple[MarketFactorPanel, pd.Index, dict[str, int]]:
    rows = _read_frame(
        connection,
        """
        WITH selected_dates AS (
            SELECT trade_date
            FROM (SELECT DISTINCT trade_date FROM daily WHERE trade_date <= %s) AS dates
            ORDER BY trade_date DESC
            LIMIT %s
        ), target_codes AS (
            SELECT ts_code FROM daily WHERE trade_date=%s
        ), factors AS (
            SELECT DISTINCT ON (source.ts_code, source.trade_date)
                   source.ts_code, source.trade_date,
                   source.adj_factor::DOUBLE PRECISION AS adj_factor
            FROM tushare_norm_adj_factor AS source
            JOIN selected_dates USING (trade_date)
            JOIN target_codes USING (ts_code)
            ORDER BY source.ts_code, source.trade_date,
                     source._last_seen_at DESC, source._record_hash DESC
        ), basics AS (
            SELECT DISTINCT ON (source.ts_code, source.trade_date)
                   source.ts_code, source.trade_date,
                   source.turnover_rate::DOUBLE PRECISION AS turnover_rate,
                   source.total_mv::DOUBLE PRECISION AS total_mv,
                   source.circ_mv::DOUBLE PRECISION AS circ_mv
            FROM tushare_norm_daily_basic AS source
            JOIN selected_dates USING (trade_date)
            JOIN target_codes USING (ts_code)
            ORDER BY source.ts_code, source.trade_date,
                     source._last_seen_at DESC, source._record_hash DESC
        )
        SELECT daily.trade_date, daily.ts_code,
               daily.open::DOUBLE PRECISION AS open,
               daily.high::DOUBLE PRECISION AS high,
               daily.low::DOUBLE PRECISION AS low,
               daily.close::DOUBLE PRECISION AS close,
               daily.vol::DOUBLE PRECISION AS vol,
               daily.amount::DOUBLE PRECISION AS amount,
               factors.adj_factor, basics.turnover_rate, basics.total_mv,
               basics.circ_mv, stock.industry, stock.list_date
        FROM daily
        JOIN selected_dates USING (trade_date)
        JOIN target_codes USING (ts_code)
        JOIN stock_basic AS stock USING (ts_code)
        LEFT JOIN factors USING (ts_code, trade_date)
        LEFT JOIN basics USING (ts_code, trade_date)
        ORDER BY daily.trade_date, daily.ts_code
        """,
        (target_date, MAX_MARKET_LOOKBACK, target_date),
    )
    if rows.empty:
        raise RuntimeError(f"no stock daily bars for local factors on {target_date}")
    rows["trade_date"] = pd.to_datetime(rows["trade_date"])
    current = rows.loc[rows["trade_date"].dt.date == target_date, "ts_code"]
    securities = pd.Index(sorted(current.astype(str).unique()), name="ts_code")
    numeric = (
        "open", "high", "low", "close", "vol", "amount", "adj_factor",
        "turnover_rate", "total_mv", "circ_mv",
    )
    for field in numeric:
        rows[field] = pd.to_numeric(rows[field], errors="coerce")
    source_digest = frame_digest(rows)
    traded_amount_cny = _pivot(rows, "amount", columns=securities) * 1000.0
    listing_dates = rows.drop_duplicates("ts_code").set_index("ts_code")["list_date"].reindex(securities)
    # Match the shared technical product's latest-factor-adjusted price basis.
    # Multiplying by the raw factor alone changes absolute indicators such as
    # MA and MACD by an arbitrary historical scale and prevents exact reuse.
    latest_adjustment = (
        rows.sort_values("trade_date")
        .drop_duplicates("ts_code", keep="last")
        .set_index("ts_code")["adj_factor"]
    )
    adjustment = rows["adj_factor"] / rows["ts_code"].map(latest_adjustment)
    for field in ("open", "high", "low", "close", "amount"):
        rows[field] = rows[field] * adjustment
    matrices = {field: _pivot(rows, field, columns=securities) for field in numeric}
    industries = (
        rows.drop_duplicates("ts_code", keep="last")
        .set_index("ts_code")["industry"].reindex(securities)
        .fillna("__unknown__")
    )
    first_date = rows["trade_date"].min().date()
    suspension_rows = _read_frame(
        connection,
        """
        SELECT DISTINCT trade_date, ts_code
        FROM suspend_d
        WHERE trade_date BETWEEN %s AND %s
          AND ts_code=ANY(%s)
        ORDER BY trade_date, ts_code
        """,
        (first_date, target_date, list(securities)),
    )
    traded_amount_cny, unexplained_market_gaps, suspension_cells_filled = (
        _fill_documented_suspension_sessions(
            matrices,
            traded_amount_cny,
            suspension_rows,
            listing_dates,
        )
    )
    index_rows = _read_frame(
        connection,
        """
        SELECT trade_date, ts_code,
               close::DOUBLE PRECISION AS close,
               vol::DOUBLE PRECISION AS vol
        FROM index_daily
        WHERE ts_code IN ('000300.SH', '000001.SH')
          AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date, ts_code
        """,
        (first_date, target_date),
    )
    if index_rows.empty:
        raise RuntimeError("benchmark index history is missing for local factors")
    index_rows["trade_date"] = pd.to_datetime(index_rows["trade_date"])
    index_close = index_rows.pivot(index="trade_date", columns="ts_code", values="close").astype("float32")
    index_volume = index_rows.pivot(index="trade_date", columns="ts_code", values="vol").astype("float32")
    dates = matrices["close"].index
    index_close = index_close.reindex(dates)
    index_volume = index_volume.reindex(dates)
    alpha_panel = Alpha101Panel(
        matrices["open"], matrices["high"], matrices["low"], matrices["close"],
        matrices["vol"], matrices["amount"], matrices["total_mv"], industries,
    )
    diagnostics = {
        "market_rows": int(len(rows)),
        "market_dates": int(rows["trade_date"].nunique()),
        "securities": int(len(securities)),
        "missing_adjustment_rows": int(rows["adj_factor"].isna().sum()),
        "missing_daily_basic_rows": int(rows["total_mv"].isna().sum()),
        "market_input_digest": source_digest,
        "benchmark_input_digest": frame_digest(index_rows),
        "suspension_input_digest": frame_digest(suspension_rows),
        "documented_suspension_cells_filled": suspension_cells_filled,
        "unexplained_market_gap_cells": int(unexplained_market_gaps.sum()),
        "unexplained_market_gap_securities": int((unexplained_market_gaps > 0).sum()),
    }
    return MarketFactorPanel(
        alpha_panel, matrices["turnover_rate"], matrices["total_mv"],
        matrices["circ_mv"], index_close["000300.SH"],
        index_close["000001.SH"], index_volume["000300.SH"],
        index_volume["000001.SH"],
        traded_amount_cny=traded_amount_cny, listing_dates=listing_dates,
        unexplained_market_gaps=unexplained_market_gaps,
    ), securities, diagnostics


_INCOME_COLUMNS = {
    "basic_eps": "basic_eps", "revenue": "revenue", "oper_cost": "oper_cost",
    "sell_exp": "sell_exp", "admin_exp": "admin_exp", "fin_exp": "fin_exp",
    "biz_tax_surchg": "biz_tax_surchg", "operate_profit": "operate_profit",
    "total_profit": "total_profit", "income_tax": "income_tax",
    "n_income": "net_profit", "n_income_attr_p": "net_profit_parent",
    "ebit": "ebit", "ebitda": "ebitda",
}
_BALANCE_COLUMNS = {
    "money_cap": "cash", "trad_asset": "trad_asset",
    "accounts_receiv": "accounts_receiv", "prepayment": "prepayment",
    "inventories": "inventories", "total_cur_assets": "total_cur_assets",
    "fix_assets": "fix_assets", "defer_tax_assets": "defer_tax_assets",
    "total_assets": "total_assets", "adv_receipts": "adv_receipts",
    "total_cur_liab": "total_cur_liab", "total_ncl": "total_ncl",
    "total_liab": "total_liab", "total_hldr_eqy_inc_min_int": "equity",
    "minority_int": "minority_int", "total_share": "total_share",
    "lt_rec": "longterm_receivable",
}
_CASHFLOW_COLUMNS = {
    "n_cashflow_act": "operating_cashflow",
    "n_cashflow_inv_act": "investing_cashflow",
    "n_cash_flows_fnc_act": "financing_cashflow",
    "c_inf_fr_operate_a": "operating_cash_inflow",
    "stot_inflows_inv_act": "investing_cash_inflow",
    "stot_out_inv_act": "investing_cash_outflow",
    "c_paid_to_for_empl": "staff_paid", "free_cashflow": "free_cashflow",
}
_INDICATOR_COLUMNS = {"profit_dedt": "profit_dedt"}
_FLOW_METRICS = frozenset({
    *_INCOME_COLUMNS.values(), *_CASHFLOW_COLUMNS.values(),
    *_INDICATOR_COLUMNS.values(),
}) - {"basic_eps"}


def _statement_rows(
    connection: Any,
    table: str,
    columns: dict[str, str],
    target_date: date,
) -> pd.DataFrame:
    selected = ", ".join(columns)
    availability = "ann_date" if table == "fina_indicator" else "greatest(ann_date, f_ann_date)"
    report_filter = "" if table == "fina_indicator" else "AND report_type IN ('1', '4')"
    rows = _read_frame(
        connection,
        f"""
        SELECT DISTINCT ON (ts_code, end_date)
               ts_code, end_date, ann_date, {selected}
        FROM {table}
        WHERE {availability} <= %s
          {report_filter}
          AND end_date >= %s
        ORDER BY ts_code, end_date, {availability} DESC, ann_date DESC, created_at DESC
        """,
        (target_date, target_date - timedelta(days=6 * 366)),
    )
    if rows.empty:
        return rows
    return rows.rename(columns=columns)


def _single_quarter(record: pd.Series, prior: pd.Series | None, metric: str) -> float:
    value = record.get(metric)
    if pd.isna(value):
        return np.nan
    end = pd.Timestamp(record["end_date"])
    if not end.is_quarter_end:
        return np.nan
    if end.month == 3:
        return float(value)
    if prior is None:
        return np.nan
    prior_end = pd.Timestamp(prior["end_date"])
    prior_value = prior.get(metric)
    if prior_end == end - pd.offsets.QuarterEnd(1) and not pd.isna(prior_value):
        return float(value) - float(prior_value)
    return np.nan


def _ttm_value(records: pd.DataFrame, position: int, metric: str, *, indexed=None) -> float:
    record = records.iloc[position]
    value = record.get(metric)
    if pd.isna(value):
        return np.nan
    end = pd.Timestamp(record["end_date"])
    if end.month == 12:
        return float(value)
    prior_year_end = pd.Timestamp(end.year - 1, 12, 31)
    prior_period_end = pd.Timestamp(end.year - 1, end.month, end.day)
    if indexed is None:
        indexed = records.set_index("end_date")
    if prior_year_end not in indexed.index or prior_period_end not in indexed.index:
        return np.nan
    annual = indexed.loc[prior_year_end, metric]
    previous_period = indexed.loc[prior_period_end, metric]
    if pd.isna(annual) or pd.isna(previous_period):
        return np.nan
    return float(value) + float(annual) - float(previous_period)


def _derive_investing_inflow(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Derive a missing subtotal only from the same PIT cashflow statement.

    Net investing cashflow = investing inflow - investing outflow.
    Never overwrite reported values or turn incomplete/invalid inputs into zero.
    Raw source rows and their digest remain unchanged.
    """
    result = frame.copy()
    fields = ('investing_cash_inflow', 'investing_cash_outflow', 'investing_cashflow')
    evidence = {'rule': 'same_statement_investing_inflow=net+outflow:v1', 'rows': 0}
    if not all(field in result for field in fields):
        return result, evidence
    inflow, outflow, net = (pd.to_numeric(result[f], errors='coerce') for f in fields)
    derived = outflow + net
    valid = inflow.isna() & np.isfinite(outflow) & np.isfinite(net) & np.isfinite(derived)
    valid &= (outflow >= 0) & (derived >= 0)
    result.loc[valid, 'investing_cash_inflow'] = derived[valid]
    proof = result.loc[valid, ['ts_code', 'end_date', *fields]]
    evidence.update(rows=int(valid.sum()), evidence_digest=frame_digest(proof),
                    examples=proof.head(10).astype(str).to_dict('records'))
    return result, evidence


def _load_financial_panel(
    connection: Any,
    target_date: date,
    securities: pd.Index,
    market_panel: MarketFactorPanel,
    *,
    include_lag: bool = True,
) -> tuple[FinancialCrossSection, dict[str, int]]:
    frames = [
        _statement_rows(connection, "income", _INCOME_COLUMNS, target_date),
        _statement_rows(connection, "balancesheet", _BALANCE_COLUMNS, target_date),
        _statement_rows(connection, "cashflow", _CASHFLOW_COLUMNS, target_date),
        _statement_rows(connection, "fina_indicator", _INDICATOR_COLUMNS, target_date),
    ]
    input_digests = [frame_digest(item) for item in frames]
    frames[2], cashflow_derivation = _derive_investing_inflow(frames[2])
    nonempty = [item for item in frames if not item.empty]
    if not nonempty:
        empty = FinancialCrossSection(
            securities, market_panel.alpha101.close.iloc[-1],
            market_panel.total_mv.iloc[-1],
        )
        return empty, {"statement_rows": 0, "statement_securities": 0,
                       "financial_input_digests": input_digests}
    statements = nonempty[0]
    for frame in nonempty[1:]:
        statements = statements.merge(
            frame.drop(columns=["ann_date"]),
            on=["ts_code", "end_date"], how="outer",
        )
    statements["end_date"] = pd.to_datetime(statements["end_date"])
    metric_names = sorted(set().union(
        _INCOME_COLUMNS.values(), _BALANCE_COLUMNS.values(),
        _CASHFLOW_COLUMNS.values(), _INDICATOR_COLUMNS.values(),
    ))
    for metric in metric_names:
        if metric not in statements:
            statements[metric] = np.nan
        statements[metric] = pd.to_numeric(statements[metric], errors="coerce")
    statements["equity_parent"] = statements["equity"] - statements["minority_int"].fillna(0)
    metric_names.append("equity_parent")
    buckets = {
        name: {metric: {} for metric in metric_names}
        for name in (
            "current", "previous", "year_ago", "previous_year_ago", "ttm",
            "ttm_previous", "ttm_year_ago", "annual", "annual_year_ago",
            "annual_five_year_ago", "five_year_mean",
        )
    }
    for ts_code, records in statements.groupby("ts_code"):
        if ts_code not in securities:
            continue
        records = records.sort_values("end_date").drop_duplicates("end_date", keep="last").reset_index(drop=True)
        indexed_records = records.set_index("end_date")
        current_position = len(records) - 1
        previous_position = current_position - 1
        current_end = records.iloc[current_position]["end_date"]
        lookup = {pd.Timestamp(row.end_date): index for index, row in records.iterrows()}
        previous_position = lookup.get(current_end - pd.offsets.QuarterEnd(1), -1)
        year_end = pd.Timestamp(current_end.year - 1, current_end.month, current_end.day)
        previous_year_end = (
            pd.Timestamp(records.iloc[previous_position]["end_date"]) - pd.DateOffset(years=1)
            if previous_position >= 0 else None
        )
        annual_positions = [
            index for index, value in enumerate(records["end_date"])
            if pd.Timestamp(value).month == 12
        ]
        positions = {
            "current": current_position,
            "previous": previous_position,
            "year_ago": lookup.get(year_end, -1),
            "previous_year_ago": lookup.get(previous_year_end, -1),
            "annual": annual_positions[-1] if annual_positions else -1,
            "annual_year_ago": lookup.get(records.iloc[annual_positions[-1]]["end_date"] - pd.DateOffset(years=1), -1) if annual_positions else -1,
            "annual_five_year_ago": lookup.get(records.iloc[annual_positions[-1]]["end_date"] - pd.DateOffset(years=5), -1) if annual_positions else -1,
        }
        for bucket, position in positions.items():
            if position < 0:
                continue
            record = records.iloc[position]
            prior = records.iloc[position - 1] if position > 0 else None
            for metric in metric_names:
                value = (
                    _single_quarter(record, prior, metric)
                    if bucket in {"current", "previous", "year_ago", "previous_year_ago"}
                    and metric in _FLOW_METRICS
                    else record.get(metric)
                )
                buckets[bucket][metric][ts_code] = value
        ttm_positions = {
            "ttm": current_position,
            "ttm_previous": previous_position,
            "ttm_year_ago": lookup.get(year_end, -1),
        }
        for bucket, position in ttm_positions.items():
            if position < 0:
                continue
            for metric in metric_names:
                buckets[bucket][metric][ts_code] = (
                    _ttm_value(records, position, metric, indexed=indexed_records)
                    if metric in _FLOW_METRICS
                    else records.iloc[position].get(metric)
                )
        recent_annual = annual_positions[-5:]
        if recent_annual:
            for metric in metric_names:
                buckets["five_year_mean"][metric][ts_code] = pd.to_numeric(
                    records.iloc[recent_annual][metric], errors="coerce"
                ).mean()
    # Construct aligned arrays once, instead of millions of scalar Series.loc
    # writes. Missing security/metric pairs still remain NaN, never zero.
    buckets = {
        bucket: {metric: pd.Series(values, dtype=float).reindex(securities)
                 for metric, values in metrics.items()}
        for bucket, metrics in buckets.items()
    }
    # Tushare daily_basic.total_mv is expressed in CNY 10,000 while financial
    # statement amounts are CNY.  Normalize once at this boundary so every
    # market-value denominator in the financial evaluator has one unit.
    current_market_cap_cny = (
        market_panel.total_mv.iloc[-1].reindex(securities) * 10_000.0
    )
    buckets["five_year_mean"]["market_cap"] = (
        market_panel.total_mv.mean().reindex(securities) * 10_000.0
    )
    dividends = _read_frame(
        connection,
        """
        SELECT ts_code, sum(cash_div_tax) AS cash_dividend
        FROM dividend
        WHERE ex_date > %s AND ex_date <= %s
        GROUP BY ts_code
        """,
        (target_date - timedelta(days=3 * 366), target_date),
    )
    dividend_series = (
        dividends.set_index("ts_code")["cash_dividend"].astype(float).reindex(securities)
        if not dividends.empty else pd.Series(np.nan, index=securities)
    )
    panel = FinancialCrossSection(
        securities=securities,
        close=market_panel.alpha101.close.iloc[-1].reindex(securities),
        total_mv=current_market_cap_cny,
        current=buckets["current"], previous=buckets["previous"],
        year_ago=buckets["year_ago"],
        previous_year_ago=buckets["previous_year_ago"],
        ttm=buckets["ttm"], ttm_previous=buckets["ttm_previous"],
        ttm_year_ago=buckets["ttm_year_ago"], annual=buckets["annual"],
        annual_year_ago=buckets["annual_year_ago"],
        annual_five_year_ago=buckets["annual_five_year_ago"],
        five_year_mean=buckets["five_year_mean"],
        dividend_cash_3y=dividend_series,
    )
    lag_diagnostics = {}
    if include_lag:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT cal_date FROM trade_cal
                WHERE exchange='SSE' AND is_open=1 AND cal_date<=%s
                ORDER BY cal_date DESC OFFSET 63 LIMIT 1""", (target_date,))
            result = cursor.fetchone()
        if result:
            lag_panel, lag_diagnostics = _load_financial_panel(
                connection, result[0], securities, market_panel, include_lag=False)
            panel.roe_ttm_lag63d = (
                lag_panel.values("ttm", "net_profit_parent")
                / lag_panel.values("current", "equity").replace(0, np.nan))
    return panel, {
        "statement_rows": int(len(statements)),
        "statement_securities": int(statements["ts_code"].nunique()),
        "financial_input_digests": input_digests,
        "cashflow_derivation": cashflow_derivation,
        "dividend_input_digest": frame_digest(dividends),
        "lag63_input": lag_diagnostics,
    }


def _load_exact_overlaps(
    technical_rows: list[dict], securities: pd.Index,
) -> dict[str, pd.Series]:
    from .ownership import SHARED_TECHNICAL_FIELDS

    rows = pd.DataFrame(technical_rows)
    if rows.empty:
        raise RuntimeError("unified technical producer returned no securities")
    indexed = rows.set_index("ts_code").reindex(securities)
    # Preserve missing values. Never switch to a differently seeded RSI/EMA
    # formula just because the authoritative producer cannot calculate it.
    return {
        name: pd.to_numeric(indexed[field], errors="coerce")
        for field, name in SHARED_TECHNICAL_FIELDS.items()
    }


def _snapshot_rows(
    target_date: date,
    securities: pd.Index,
    values: dict[str, pd.Series],
    *,
    source_execution_id: int | None,
    input_revision_digest: str,
) -> list[tuple[Any, ...]]:
    missing_producers = sorted({item.name for item in FACTOR_SPECS} - set(values))
    if missing_producers:
        raise RuntimeError(f"local factor producers missing: {missing_producers}")
    rows: list[tuple[Any, ...]] = []
    for ts_code in securities:
        factor_values: list[float | None] = []
        ready_bits: list[str] = []
        unavailable: list[int] = []
        for spec in FACTOR_SPECS:
            value = values[spec.name].get(ts_code, np.nan)
            ready = (
                value is not None
                and np.isfinite(float(value))
                and abs(float(value)) <= MAX_ABS_FACTOR_VALUE
            )
            factor_values.append(float(value) if ready else None)
            ready_bits.append("1" if ready else "0")
            if not ready:
                unavailable.append(spec.position)
        ready_count = FACTOR_COUNT - len(unavailable)
        status = (
            "ready" if ready_count == FACTOR_COUNT
            else "missing_input" if ready_count == 0
            else "partial"
        )
        rows.append((
            FACTOR_SCHEMA_VERSION, target_date, ts_code, factor_values,
            "".join(ready_bits), ready_count, unavailable, status,
            input_revision_digest, FORMULA_DIGEST, source_execution_id,
        ))
    return rows


def _write_provider_validation(
    cursor: Any, target_date: date,
) -> dict[str, int | str]:
    """Compatibility wrapper around bounded daily provider validation."""

    return write_provider_validation(cursor, target_date, FACTOR_SCHEMA_VERSION)


def _sync_factor_catalog_committed() -> None:
    """Publish immutable catalog metadata outside the date transaction.

    Holding the catalog UPSERT row locks while a full-market date is being
    calculated silently serializes otherwise independent V2 backfill
    executions.  The catalog is versioned and formula-addressed, so it can be
    committed as a short preflight before the per-date repeatable-read
    transaction starts.
    """

    connection = get_conn()
    try:
        sync_factor_catalog(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _reuse_certified_snapshot(
    target_date: date, *, source_execution_id: int | None,
) -> dict[str, Any] | None:
    """Attach an exact existing V4 publication to a governed V2 execution.

    Historical batches may calculate a date before its control-plane
    execution is created. Re-reading seven million market rows merely to make
    ``dataset_state`` aware of an already certified snapshot is wasteful. This
    fast path is deliberately strict: the current formula digest, full daily
    security coverage and all 272 validation rows must already exist.
    """

    connection = get_conn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH expected AS (
                    SELECT count(DISTINCT ts_code)::INTEGER AS expected_count
                    FROM daily WHERE trade_date=%s
                ), snapshot AS (
                    SELECT count(*)::INTEGER AS actual_count,
                           bool_and(formula_digest=%s) AS current_formula,
                           count(*) FILTER (WHERE audit_status='ready')::INTEGER AS ready,
                           count(*) FILTER (WHERE audit_status NOT IN ('ready', 'not_expected')
                               OR technical_audit_status NOT IN ('ready', 'not_expected'))::INTEGER AS partial
                    FROM local_factor_snapshot
                    WHERE schema_version=%s AND trade_date=%s
                ), validation AS (
                    SELECT count(*)::INTEGER AS factor_count,
                           max(sampled_security_count)::INTEGER AS sampled,
                           max(validation_elapsed_ms)::INTEGER AS elapsed
                    FROM local_factor_validation
                    WHERE schema_version=%s AND trade_date=%s
                )
                SELECT expected_count, actual_count,
                       current_formula AND NOT EXISTS (
                           SELECT 1 FROM daily d
                           WHERE d.trade_date=%s AND NOT EXISTS (
                               SELECT 1 FROM local_factor_snapshot s
                               WHERE s.trade_date=d.trade_date AND s.ts_code=d.ts_code
                                 AND s.schema_version=%s
                           )
                       ), ready,
                       partial, factor_count, sampled, elapsed
                FROM expected CROSS JOIN snapshot CROSS JOIN validation
                """,
                (
                    target_date, FORMULA_DIGEST, FACTOR_SCHEMA_VERSION,
                    target_date, FACTOR_SCHEMA_VERSION, target_date,
                    target_date, FACTOR_SCHEMA_VERSION,
                ),
            )
            row = cursor.fetchone()
            if not row:
                return None
            expected, actual, current, ready, partial, factor_count, sampled, elapsed = row
            if not (
                int(expected or 0) > 0
                and int(actual or 0) >= int(expected)
                and bool(current)
                and int(partial or 0) == 0
                and int(factor_count or 0) == FACTOR_COUNT
            ):
                return None
            cursor.execute(
                """
                UPDATE local_factor_snapshot
                SET source_execution_id=%s
                WHERE schema_version=%s AND trade_date=%s
                """,
                (source_execution_id, FACTOR_SCHEMA_VERSION, target_date),
            )
        connection.commit()
        return {
            "dataset": "local_factor_snapshot",
            "snapshot_date": target_date.isoformat(),
            "schema_version": FACTOR_SCHEMA_VERSION,
            "formula_digest": FORMULA_DIGEST,
            "implementation_digest": IMPLEMENTATION_DIGEST,
            "factor_count": FACTOR_COUNT,
            "rows_written": 0,
            "rows_reused": int(actual),
            "publishable": True,
            "data_ready": int(partial or 0) == 0,
            "quality_ready_securities": int(ready or 0),
            "quality_partial_securities": int(partial or 0),
            "validation_factor_count": int(factor_count or 0),
            "validation_sampled_securities": int(sampled or 0),
            "validation_elapsed_ms": int(elapsed or 0),
            "reused_existing_snapshot": True,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def materialize_local_factor_snapshot(
    target_date: date,
    *,
    source_execution_id: int | None = None,
    reuse_existing_snapshot: bool = False,
) -> dict[str, Any]:
    """Calculate and atomically publish one full-market 272-factor session."""

    _sync_factor_catalog_committed()
    if reuse_existing_snapshot:
        reused = _reuse_certified_snapshot(
            target_date, source_execution_id=source_execution_id,
        )
        if reused is not None:
            return reused
    connection = get_conn()
    try:
        from service.orchestration_v2.transformations import build_technical_factor_rows
        from .ownership import technical_payload

        connection.set_session(isolation_level="REPEATABLE READ")
        with connection.cursor() as lock_cursor:
            lock_cursor.execute(
                "SELECT pg_try_advisory_xact_lock(hashtext(%s), %s)",
                (
                    f"local_factor_snapshot:{FACTOR_SCHEMA_VERSION}",
                    (target_date - date(2000, 1, 1)).days,
                ),
            )
            if not lock_cursor.fetchone()[0]:
                raise RuntimeError(
                    f"local factor publication already running for {target_date}"
                )
        technical_rows = build_technical_factor_rows(
            target_date, source_execution_id=source_execution_id,
            connection=connection,
        )
        technical_by_code = {row["ts_code"]: row for row in technical_rows}
        market_panel, securities, market_diagnostics = _load_market_panel(
            connection, target_date
        )
        missing_technical = set(securities) - set(technical_by_code)
        if missing_technical:
            raise RuntimeError(f"technical producer missing active securities: {sorted(missing_technical)[:10]}")
        exact = _load_exact_overlaps(technical_rows, securities)
        market_values = MarketFactorEvaluator(
            market_panel, exact_overlaps=exact
        ).evaluate_latest()
        financial_panel, financial_diagnostics = _load_financial_panel(
            connection, target_date, securities, market_panel
        )
        financial_values = FinancialFactorEvaluator(financial_panel).evaluate_latest()
        duplicate = set(market_values).intersection(financial_values)
        if duplicate:
            raise RuntimeError(f"duplicate factor producers: {sorted(duplicate)}")
        values = {**market_values, **financial_values}
        from .quality import audit_security
        input_revision_digest = hashlib.sha256(json.dumps({
            "date": target_date.isoformat(),
            "formula": FORMULA_DIGEST,
            "implementation": IMPLEMENTATION_DIGEST,
            **market_diagnostics,
            **financial_diagnostics,
            "technical_input_digests": [row.get("source_value_digest") for row in technical_rows],
        }, sort_keys=True).encode()).hexdigest()
        # Preserve the security-master diagnostic rows (including suspended
        # stocks). No-trade securities get missing arrays, not yesterday's
        # factor values relabelled as today's cross-section.
        output_securities = pd.Index(sorted(set(securities) | set(technical_by_code)))
        rows = _snapshot_rows(
            target_date, output_securities, values,
            source_execution_id=source_execution_id,
            input_revision_digest=input_revision_digest,
        )
        quality = {code: audit_security(
            code, values, technical_by_code[code], market_panel, financial_panel
        )
                   for code in output_securities}
        rows = [(*row, psycopg2.extras.Json(technical_payload(technical_by_code[row[2]])),
                 quality[row[2]]["status"], psycopg2.extras.Json(quality[row[2]]),
                 quality[row[2]]["technical_status"]) for row in rows]
        with connection.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                """
                INSERT INTO local_factor_snapshot (
                    schema_version, trade_date, ts_code, factor_values,
                    ready_mask, ready_count, unavailable_positions,
                    calculation_status, input_revision_digest,
                    formula_digest, source_execution_id, technical_values, audit_status, audit_evidence, technical_audit_status
                ) VALUES %s
                ON CONFLICT (schema_version, trade_date, ts_code) DO UPDATE SET
                    factor_values=EXCLUDED.factor_values,
                    ready_mask=EXCLUDED.ready_mask,
                    ready_count=EXCLUDED.ready_count,
                    unavailable_positions=EXCLUDED.unavailable_positions,
                    calculation_status=EXCLUDED.calculation_status,
                    input_revision_digest=EXCLUDED.input_revision_digest,
                    formula_digest=EXCLUDED.formula_digest,
                    source_execution_id=EXCLUDED.source_execution_id,
                    technical_values=EXCLUDED.technical_values,
                    audit_status=EXCLUDED.audit_status,
                    audit_evidence=EXCLUDED.audit_evidence,
                    technical_audit_status=EXCLUDED.technical_audit_status,
                    computed_at=NOW()
                """,
                rows,
                template="(%s,%s,%s,%s,%s::bit(272),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                page_size=500,
            )
            cursor.execute(
                """
                DELETE FROM local_factor_snapshot
                WHERE schema_version=%s AND trade_date=%s
                  AND NOT (ts_code = ANY(%s))
                """,
                (FACTOR_SCHEMA_VERSION, target_date, list(output_securities)),
            )
            # Formula versions remain in the catalog for lineage, but one
            # trade date has only one official materialized feature vector.
            # Once the current version is written successfully, retaining
            # older vectors is duplicate supply and can make callers select
            # inconsistent values.
            cursor.execute(
                """
                DELETE FROM local_factor_validation
                WHERE trade_date=%s AND schema_version<>%s
                """,
                (target_date, FACTOR_SCHEMA_VERSION),
            )
            cursor.execute(
                """
                DELETE FROM local_factor_snapshot
                WHERE trade_date=%s AND schema_version<>%s
                """,
                (target_date, FACTOR_SCHEMA_VERSION),
            )
            cursor.execute(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE calculation_status='ready') AS ready,
                       count(*) FILTER (WHERE calculation_status='partial') AS partial,
                       count(*) FILTER (WHERE calculation_status='missing_input') AS missing_input,
                       min(ready_count) AS min_ready_count,
                       avg(ready_count) AS avg_ready_count,
                       max(ready_count) AS max_ready_count,
                       avg(pg_column_size(factor_values)) AS avg_factor_bytes
                FROM local_factor_snapshot
                WHERE schema_version=%s AND trade_date=%s
                """,
                (FACTOR_SCHEMA_VERSION, target_date),
            )
            summary = dict(zip(
                ("total", "ready", "partial", "missing_input", "min_ready_count", "avg_ready_count", "max_ready_count", "avg_factor_bytes"),
                cursor.fetchone(),
            ))
            cursor.execute("""
                SELECT count(*),count(*) FILTER (WHERE ready_count=0)
                FROM local_factor_snapshot WHERE schema_version=%s AND trade_date=%s
                  AND ts_code=ANY(%s)
            """, (FACTOR_SCHEMA_VERSION, target_date, list(securities)))
            active_count, active_missing = cursor.fetchone()
            # Provider comparison runs in its own scheduled transaction. A slow
            # or unavailable reference source must never roll back calculation.
            validation = {"validation_execution_status": "scheduled_separately"}
        connection.commit()
        return {
            "dataset": "local_factor_snapshot",
            "snapshot_date": target_date.isoformat(),
            "schema_version": FACTOR_SCHEMA_VERSION,
            "formula_digest": FORMULA_DIGEST,
            "implementation_digest": IMPLEMENTATION_DIGEST,
            "factor_count": FACTOR_COUNT,
            "rows_written": len(rows),
            # Successful computation can publish diagnostic partial rows;
            # the independent coverage audit filters audit_status='ready'.
            # This flag certifies execution, NOT dataset readiness.
            "publishable": int(summary["total"] or 0) == len(output_securities)
            and active_count == len(securities) and active_count > 0,
            "data_ready": all(quality[code]["status"] == "ready" for code in securities),
            "quality_ready_securities": sum(quality[code]["status"] == "ready" for code in securities),
            "quality_partial_securities": sum(quality[code]["status"] != "ready" for code in securities),
            "nontrading_diagnostic_rows": len(output_securities)-len(securities),
            **market_diagnostics,
            **financial_diagnostics,
            **validation,
            **{
                key: float(value) if key in {"avg_ready_count", "avg_factor_bytes"} and value is not None
                else int(value or 0)
                for key, value in summary.items()
            },
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
