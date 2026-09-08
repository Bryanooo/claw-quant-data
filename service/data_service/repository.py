"""Safe SQL repository for registered datasets."""

from datetime import date, timedelta
from typing import Any

from psycopg2 import sql

from service.data_service.models import DatasetQuery, DatasetSpec


class DatasetRepository:
    def __init__(self, database):
        self._database = database

    def ping(self) -> bool:
        row = self._database.fetch_one("SELECT 1 AS ok")
        return bool(row and row["ok"] == 1)

    def columns(self, dataset: DatasetSpec) -> list[dict]:
        return self._database.fetch_all(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (dataset.read_table,),
        )

    def records(self, dataset: DatasetSpec, query: DatasetQuery) -> list[dict]:
        where_sql, params = self._where_clause(dataset, query)
        direction = sql.SQL("DESC" if dataset.default_descending else "ASC")
        order_columns = dataset.default_order or dataset.primary_keys
        # PostgreSQL applies a trailing direction only to the immediately
        # preceding expression.  Build every term explicitly so a contract
        # such as (trade_date, ts_code) really returns the newest partition
        # first instead of sorting trade_date ascending and ts_code descending.
        order_sql = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(column), direction)
            for column in order_columns
        )

        statement = sql.SQL(
            "SELECT * FROM {table}{where} ORDER BY {order} "
            "LIMIT %s OFFSET %s"
        ).format(
            table=sql.Identifier(dataset.read_table),
            where=where_sql,
            order=order_sql,
        )
        return self._database.fetch_all(
            statement,
            (*params, query.limit, query.offset),
        )

    def count(self, dataset: DatasetSpec, query: DatasetQuery) -> int:
        where_sql, params = self._where_clause(dataset, query)
        statement = sql.SQL("SELECT count(*) AS total FROM {table}{where}").format(
            table=sql.Identifier(dataset.read_table),
            where=where_sql,
        )
        row = self._database.fetch_one(statement, params)
        return int(row["total"]) if row else 0

    def latest_value(self, dataset: DatasetSpec) -> Any:
        if not dataset.date_column:
            return None
        statement = sql.SQL(
            "SELECT max({date_column}) AS latest_value FROM {table}"
        ).format(
            date_column=sql.Identifier(dataset.date_column),
            table=sql.Identifier(dataset.table),
        )
        row = self._database.fetch_one(statement)
        return row["latest_value"] if row else None

    def estimated_rows(self, dataset: DatasetSpec) -> int:
        row = self._database.fetch_one(
            """
            WITH target AS (
                SELECT rel.oid, rel.relkind
                FROM pg_class AS rel
                JOIN pg_namespace AS namespace
                  ON namespace.oid = rel.relnamespace
                WHERE namespace.nspname = 'public' AND rel.relname = %s
            ), relations AS (
                SELECT oid FROM target WHERE relkind IN ('r', 'p', 'm')
                UNION
                SELECT dependency.refobjid
                FROM target
                JOIN pg_rewrite AS rewrite ON rewrite.ev_class = target.oid
                JOIN pg_depend AS dependency
                  ON dependency.objid = rewrite.oid
                 AND dependency.refclassid = 'pg_class'::regclass
                WHERE target.relkind = 'v'
                  AND dependency.refobjid <> target.oid
            )
            SELECT COALESCE(
                       MAX(GREATEST(
                           COALESCE(stats.n_live_tup, 0),
                           COALESCE(rel.reltuples, 0),
                           0
                       )),
                       0
                   )::bigint AS estimated_rows
            FROM relations
            JOIN pg_class AS rel ON rel.oid = relations.oid
            LEFT JOIN pg_stat_user_tables AS stats ON stats.relid = rel.oid
            """,
            (dataset.table,),
        )
        return int(row["estimated_rows"]) if row else 0

    def search_news(
        self,
        dataset: DatasetSpec,
        *,
        terms: tuple[str, ...],
        start_date: date,
        end_date: date,
        limit: int,
    ) -> list[dict]:
        """Search governed major-news rows with bounded, literal keywords."""
        clean_terms = tuple(term.strip() for term in terms if term.strip())[:5]
        if not clean_terms:
            return []
        term_conditions: list[sql.Composed] = []
        params: list[Any] = []
        for term in clean_terms:
            pattern = f"%{term}%"
            term_conditions.append(
                sql.SQL("({title} ILIKE %s OR {content} ILIKE %s)").format(
                    title=sql.Identifier("title"),
                    content=sql.Identifier("content"),
                )
            )
            params.extend((pattern, pattern))
        statement = sql.SQL(
            "SELECT {hash}, {title}, LEFT({content}, 2000) AS {content}, "
            "{published}, {source} FROM {table} "
            "WHERE ({terms}) AND {published} >= %s AND {published} < %s "
            "ORDER BY {published} DESC LIMIT %s"
        ).format(
            hash=sql.Identifier("_record_hash"),
            title=sql.Identifier("title"),
            content=sql.Identifier("content"),
            published=sql.Identifier("pub_time"),
            source=sql.Identifier("src"),
            table=sql.Identifier(dataset.read_table),
            terms=sql.SQL(" OR ").join(term_conditions),
        )
        return self._database.fetch_all(
            statement,
            (*params, start_date, end_date + timedelta(days=1), limit),
        )

    @staticmethod
    def _where_clause(
        dataset: DatasetSpec,
        query: DatasetQuery,
    ) -> tuple[sql.Composed, tuple[Any, ...]]:
        conditions: list[sql.Composed] = []
        params: list[Any] = []

        for filter_name, value in query.exact_filters.items():
            column = dataset.exact_filters[filter_name]
            conditions.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
            params.append(value)

        if dataset.date_column:
            date_column = sql.Identifier(dataset.date_column)
            if query.date is not None:
                conditions.append(sql.SQL("{} = %s").format(date_column))
                params.append(query.date)
            if query.start_date is not None:
                conditions.append(sql.SQL("{} >= %s").format(date_column))
                params.append(query.start_date)
            if query.end_date is not None:
                conditions.append(sql.SQL("{} <= %s").format(date_column))
                params.append(query.end_date)

        if not conditions:
            return sql.SQL(""), tuple(params)
        return (
            sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions),
            tuple(params),
        )
