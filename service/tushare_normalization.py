"""Typed normalization contracts and lossless raw-to-standard materialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
from typing import Any

import psycopg2.extras
from psycopg2 import sql

from service.db import get_conn
from service.tushare_catalog import TushareInterfaceCatalog


SCHEMA_VERSION = 1
NORMALIZED_TABLE_PREFIX = "tushare_norm_"

_TIMESTAMP_FIELDS = {"trade_time", "pub_time", "create_time", "update_time"}
_TIME_FIELDS = {"time", "qt_time"}
_DATE_ALIASES = {"imp_anndate"}
_TECHNICAL_UPSTREAM_FIELDS = {"id", "create_by", "update_by", "create_time", "update_time"}


@dataclass(frozen=True, slots=True)
class NormalizedField:
    name: str
    upstream_type: str
    sql_type: str
    description: str


@dataclass(frozen=True, slots=True)
class NormalizationContract:
    api_name: str
    title: str
    description: str
    category: str
    table_name: str
    source_doc_id: int | None
    fields: tuple[NormalizedField, ...]
    date_column: str | None
    # Required fields used to reject structurally unusable records.
    identity_fields: tuple[str, ...]
    # Logical grouping fields for payload versions. These are metadata, not a
    # database uniqueness promise; see identity_confidence.
    business_identity_fields: tuple[str, ...]
    identity_confidence: str
    schema_version: int = SCHEMA_VERSION

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    api_name: str
    raw_rows: int
    normalized_rows: int
    quarantined_rows: int
    unknown_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    contract_complete: bool = True

    @property
    def complete(self) -> bool:
        return self.quarantined_rows == 0 and self.contract_complete

    def as_evidence(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "raw_rows": self.raw_rows,
            "normalized_rows": self.normalized_rows,
            "quarantined_rows": self.quarantined_rows,
            "unknown_fields": list(self.unknown_fields),
            "missing_fields": list(self.missing_fields),
            "contract_complete": self.contract_complete,
            "complete": self.complete,
        }


class NormalizationIncompleteError(RuntimeError):
    retryable = False
    completion_status = "incomplete"

    def __init__(self, result: NormalizationResult):
        self.result = result
        super().__init__(
            f"{result.api_name} normalized {result.normalized_rows}/{result.raw_rows} "
            f"rows; {result.quarantined_rows} rows were quarantined"
        )


def normalized_table_name(api_name: str) -> str:
    return f"{NORMALIZED_TABLE_PREFIX}{api_name}"


def _sql_type(name: str, upstream_type: str) -> str:
    normalized_type = (upstream_type or "str").lower()
    if name in _TIMESTAMP_FIELDS or normalized_type == "datetime":
        return "TIMESTAMP WITHOUT TIME ZONE"
    if name in _TIME_FIELDS:
        return "TIME WITHOUT TIME ZONE"
    if name in _DATE_ALIASES or name == "date" or name.endswith("_date"):
        return "DATE"
    if normalized_type == "float":
        return "NUMERIC"
    if normalized_type == "int":
        return "BIGINT"
    return "TEXT"


def _canonical_date_column(fields: tuple[NormalizedField, ...]) -> str | None:
    names = {field.name for field in fields if field.sql_type == "DATE"}
    for candidate in (
        "trade_date",
        "cal_date",
        "ann_date",
        "end_date",
        "report_date",
        "nav_date",
        "publish_date",
        "date",
    ):
        if candidate in names:
            return candidate
    return None


def _identity_fields(
    fields: tuple[NormalizedField, ...],
    date_column: str | None,
) -> tuple[str, ...]:
    names = {field.name for field in fields}
    identity: list[str] = []
    code_field = None
    for candidate in (
        "ts_code",
        "index_code",
        "con_code",
        "symbol",
        "code",
        "id",
    ):
        if candidate in names:
            code_field = candidate
            break
    if code_field:
        for candidate in ("trade_date", "cal_date", "nav_date", "date"):
            if candidate in names:
                identity.append(candidate)
                break
        identity.append(code_field)
    else:
        for candidate in ("month", "quarter", "week", "name", "title"):
            if candidate in names:
                identity.append(candidate)
                break
        if not identity and date_column:
            identity.append(date_column)
    return tuple(dict.fromkeys(identity))


# Reviewed against the output contracts and examples linked in docs/tushare.
# The fields identify one logical observation; changing measures remain payload
# versions under the lossless _record_hash primary key.
_REVIEWED_BUSINESS_IDENTITIES: dict[str, tuple[str, ...]] = {
    "bc_otcqt": ("trade_date", "qt_time", "bank", "ts_code"),
    "cb_basic": ("ts_code",),
    "cb_daily": ("trade_date", "ts_code"),
    "cb_rate": ("ts_code", "rate_start_date", "rate_end_date"),
    "cb_rating": ("ts_code", "rating_date", "rating_com_name", "rating_type"),
    "cn_schedule": ("month", "publish_date", "title"),
    "daily_basic": ("trade_date", "ts_code"),
    "etf_sh_cons": ("trade_date", "ts_code", "con_code"),
    "etf_share_size": ("trade_date", "ts_code"),
    "etf_sz_cons": ("trade_date", "ts_code", "con_code"),
    "fund_company": ("name",),
    "fund_manager": ("ts_code", "name", "begin_date"),
    "fund_share": ("trade_date", "ts_code"),
    "fut_basic": ("ts_code",),
    "fut_daily": ("trade_date", "ts_code"),
    "fut_holding": ("trade_date", "symbol", "broker"),
    "fut_settle": ("trade_date", "ts_code"),
    "fut_weekly_detail": ("week", "exchange", "prd"),
    "fut_wsr": (
        "trade_date", "symbol", "warehouse", "wh_id", "grade", "brand", "place"
    ),
    "limit_list_ths": ("trade_date", "ts_code"),
    "shibor_quote": ("date", "bank"),
    "us_basic": ("ts_code",),
}


def _business_identity_fields(
    api_name: str,
    fields: tuple[NormalizedField, ...],
    fallback: tuple[str, ...],
) -> tuple[tuple[str, ...], str]:
    reviewed = _REVIEWED_BUSINESS_IDENTITIES.get(api_name)
    if reviewed is None:
        return fallback, "heuristic"
    missing = set(reviewed) - {field.name for field in fields}
    if missing:
        raise ValueError(
            f"reviewed business identity for {api_name} references missing fields: "
            + ", ".join(sorted(missing))
        )
    return reviewed, "contract_reviewed"


@lru_cache(maxsize=1)
def load_normalization_contracts() -> tuple[NormalizationContract, ...]:
    contracts: list[NormalizationContract] = []
    for interface in TushareInterfaceCatalog().list():
        if not interface.collectable:
            continue
        if interface.implementation.get("mode") != "generic_raw":
            continue
        fields = tuple(
            NormalizedField(
                name=str(value["name"]),
                upstream_type=str(value.get("type") or "str"),
                sql_type=_sql_type(
                    str(value["name"]),
                    str(value.get("type") or "str"),
                ),
                description=str(value.get("description") or ""),
            )
            for value in interface.output_parameters
            if value.get("name")
        )
        date_column = _canonical_date_column(fields)
        required_identity = _identity_fields(fields, date_column)
        business_identity, identity_confidence = _business_identity_fields(
            interface.api_name,
            fields,
            required_identity,
        )
        contracts.append(
            NormalizationContract(
                api_name=interface.api_name,
                title=interface.title,
                description=interface.description,
                category=interface.category,
                table_name=normalized_table_name(interface.api_name),
                source_doc_id=interface.source_doc_id,
                fields=fields,
                date_column=date_column,
                identity_fields=required_identity,
                business_identity_fields=business_identity,
                identity_confidence=identity_confidence,
            )
        )
    return tuple(contracts)


class NormalizationRegistry:
    def __init__(self, contracts: tuple[NormalizationContract, ...] | None = None):
        values = contracts if contracts is not None else load_normalization_contracts()
        self._contracts = {contract.api_name: contract for contract in values}

    def get(self, api_name: str) -> NormalizationContract:
        try:
            return self._contracts[api_name]
        except KeyError as exc:
            raise ValueError(f"normalization contract is missing: {api_name}") from exc

    def list(self) -> tuple[NormalizationContract, ...]:
        return tuple(sorted(self._contracts.values(), key=lambda item: item.api_name))


NORMALIZATION_CONTRACTS = NormalizationRegistry()


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _json(value: Any) -> psycopg2.extras.Json:
    return psycopg2.extras.Json(
        value,
        dumps=lambda item: json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            default=_json_default,
        ),
    )


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text in {"-", "--", "None", "null", "N/A"}:
        return None
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    return date.fromisoformat(text)


def _convert(value: Any, field: NormalizedField) -> Any:
    if value is None or value == "":
        return None
    if field.sql_type == "DATE":
        return _parse_date(value)
    if field.sql_type == "TIMESTAMP WITHOUT TIME ZONE":
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        return parsed.replace(tzinfo=None)
    if field.sql_type == "TIME WITHOUT TIME ZONE":
        return value if isinstance(value, time) else time.fromisoformat(str(value))
    if field.sql_type == "BIGINT":
        parsed = Decimal(str(value))
        if parsed != parsed.to_integral_value():
            raise ValueError(f"{value!r} is not an integer")
        return int(parsed)
    if field.sql_type == "NUMERIC":
        if str(value).strip() in {"-", "--", "None", "null", "N/A"}:
            return None
        parsed = Decimal(str(value))
        if not parsed.is_finite():
            return None
        return parsed
    return str(value)


class TushareNormalizer:
    """Materialize raw payloads without risking loss of their source records."""

    def __init__(self, registry: NormalizationRegistry | None = None):
        self._registry = registry or NORMALIZATION_CONTRACTS

    def normalize(
        self,
        api_name: str,
        request_hash: str,
        records: list[tuple[str, dict[str, Any]]],
        *,
        source_doc_id: int | None,
        collected_at: datetime | None = None,
        strict_contract: bool = False,
    ) -> NormalizationResult:
        contract = self._registry.get(api_name)
        observed_at = collected_at or datetime.now(timezone.utc)
        expected = set(contract.field_names)
        observed: set[str] = set()
        unknown: set[str] = set()
        normalized_values: list[tuple[Any, ...]] = []
        failures: list[tuple[str, dict[str, Any], str, str]] = []

        for record_hash, payload in records:
            canonical: dict[str, Any] = {}
            collision = None
            for original_name, value in payload.items():
                name = str(original_name)
                normalized_name = name.lower()
                if normalized_name in canonical and name != normalized_name:
                    collision = normalized_name
                    break
                canonical[normalized_name] = value
            if collision:
                failures.append(
                    (record_hash, payload, "field_collision", f"duplicate field {collision}")
                )
                continue

            observed.update(canonical)
            extra = {
                name: value
                for name, value in canonical.items()
                if name not in expected
            }
            unknown.update(extra)
            missing_identity = [
                name
                for name in contract.identity_fields
                if canonical.get(name) in (None, "")
            ]
            if missing_identity:
                failures.append(
                    (
                        record_hash,
                        payload,
                        "missing_identity",
                        "missing identity fields: " + ", ".join(missing_identity),
                    )
                )
                continue
            try:
                values = tuple(
                    _convert(canonical.get(field.name), field)
                    for field in contract.fields
                )
            except (InvalidOperation, TypeError, ValueError) as exc:
                failures.append(
                    (record_hash, payload, "type_conversion", str(exc)[:1000])
                )
                continue
            normalized_values.append(
                (
                    record_hash,
                    request_hash,
                    source_doc_id,
                    observed_at,
                    contract.schema_version,
                    _json(extra),
                    *values,
                )
            )

        missing = expected - observed
        connection = get_conn()
        try:
            with connection.cursor() as cursor:
                if normalized_values:
                    self._upsert_rows(cursor, connection, contract, normalized_values)
                    cursor.execute(
                        """
                        UPDATE sys_tushare_normalization_error
                        SET resolved_at=NOW(), last_seen_at=NOW(),
                            resolution_reason='record_reprocessed'
                        WHERE api_name=%s AND request_hash=%s
                          AND record_hash = ANY(%s)
                        """,
                        (
                            api_name,
                            request_hash,
                            [value[0] for value in normalized_values],
                        ),
                    )
                for record_hash, payload, error_code, message in failures:
                    cursor.execute(
                        """
                        INSERT INTO sys_tushare_normalization_error (
                            api_name, request_hash, record_hash, payload,
                            error_code, error_message
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (api_name, request_hash, record_hash) DO UPDATE SET
                            payload=EXCLUDED.payload, error_code=EXCLUDED.error_code,
                            error_message=EXCLUDED.error_message, attempts=
                                sys_tushare_normalization_error.attempts + 1,
                            last_seen_at=NOW(), resolved_at=NULL
                        """,
                        (
                            api_name,
                            request_hash,
                            record_hash,
                            _json(payload),
                            error_code,
                            message,
                        ),
                    )
                self._record_drift(cursor, api_name, unknown, "unexpected_field")
                self._record_drift(cursor, api_name, missing, "missing_field")
                if strict_contract and not unknown and not missing and not failures:
                    cursor.execute(
                        """
                        UPDATE sys_tushare_schema_drift
                        SET resolved_at=NOW()
                        WHERE api_name=%s AND resolved_at IS NULL
                        """,
                        (api_name,),
                    )
                cursor.execute(
                    """
                    INSERT INTO sys_tushare_normalization_run (
                        api_name, request_hash, schema_version, status,
                        raw_rows, normalized_rows, quarantined_rows,
                        unknown_fields, missing_fields
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        api_name,
                        request_hash,
                        contract.schema_version,
                        "complete"
                        if not failures and (not strict_contract or not missing)
                        else "partial",
                        len(records),
                        len(normalized_values),
                        len(failures),
                        _json(sorted(unknown)),
                        _json(sorted(missing)),
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return NormalizationResult(
            api_name=api_name,
            raw_rows=len(records),
            normalized_rows=len(normalized_values),
            quarantined_rows=len(failures),
            unknown_fields=tuple(sorted(unknown)),
            missing_fields=tuple(sorted(missing)),
            contract_complete=not strict_contract or not missing,
        )

    def resolve_superseded_scope(
        self,
        api_name: str,
        request_parameters: dict[str, Any],
    ) -> int:
        """Resolve quarantined legacy rows after a complete scope recollection."""
        logical_scope = {
            key: value
            for key, value in request_parameters.items()
            if key not in {"fields", "limit", "offset"}
        }
        connection = get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sys_tushare_normalization_error error_row
                    SET resolved_at=NOW(), last_seen_at=NOW(),
                        resolution_reason='superseded_by_complete_scope'
                    WHERE error_row.api_name=%s AND error_row.resolved_at IS NULL
                      AND EXISTS (
                          SELECT 1 FROM tushare_raw_record raw_row
                          WHERE raw_row.api_name=error_row.api_name
                            AND raw_row.request_hash=error_row.request_hash
                            AND raw_row.record_hash=error_row.record_hash
                            AND (raw_row.request_params - 'fields') = %s::jsonb
                      )
                    """,
                    (api_name, json.dumps(logical_scope, ensure_ascii=False, sort_keys=True)),
                )
                affected = cursor.rowcount
            connection.commit()
            return affected
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _upsert_rows(cursor, connection, contract, values) -> None:
        metadata_columns = (
            "_record_hash",
            "_request_hash",
            "_source_doc_id",
            "_source_collected_at",
            "_schema_version",
            "_extra_payload",
        )
        columns = (*metadata_columns, *contract.field_names)
        statement = sql.SQL(
            "INSERT INTO {table} ({columns}) VALUES %s "
            "ON CONFLICT (_record_hash) DO UPDATE SET "
            "_request_hash=EXCLUDED._request_hash, "
            "_source_collected_at=GREATEST({table}._source_collected_at, "
            "EXCLUDED._source_collected_at), "
            "_last_seen_at=NOW(), _extra_payload=EXCLUDED._extra_payload"
        ).format(
            table=sql.Identifier(contract.table_name),
            columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        )
        psycopg2.extras.execute_values(
            cursor,
            statement.as_string(connection),
            values,
            page_size=1000,
        )

    @staticmethod
    def _record_drift(cursor, api_name: str, fields: set[str], drift_type: str) -> None:
        for field_name in fields:
            if field_name in _TECHNICAL_UPSTREAM_FIELDS:
                severity = "info"
            else:
                severity = "warning"
            cursor.execute(
                """
                INSERT INTO sys_tushare_schema_drift (
                    api_name, field_name, drift_type, severity
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (api_name, field_name, drift_type) DO UPDATE SET
                    occurrences=sys_tushare_schema_drift.occurrences + 1,
                    severity=EXCLUDED.severity, last_seen_at=NOW(), resolved_at=NULL
                """,
                (api_name, field_name, drift_type, severity),
            )
