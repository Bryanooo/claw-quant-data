"""Execution-scoped transport certificates; one page never certifies a fan-out."""
from typing import Any


def request_verified(item: dict[str, Any]) -> bool:
    proof = item.get('completion_evidence') or {}
    if not isinstance(proof, dict):
        return False
    if (proof.get('table_name') == 'fina_mainbz' or 'FinaMainbzCollector' in str(proof.get('collector_name', ''))):
        if proof.get('mainbz_classifications_verified') is not True:
            return False
    normalization = proof.get('normalization') or {}
    if not isinstance(normalization, dict):
        return False
    if proof.get('reference_response_manifest') and proof.get('source') == 'historical_db':
        sessions = proof.get('day_manifests') or [proof]
        if not isinstance(sessions, list) or proof.get('supplier_missing_keys'):
            return False
        if any(not isinstance(session, dict) or session.get('supplier_missing_keys') for session in sessions):
            return False
    if item.get('completion_status') == 'empty' and _rows_fetched(item) is None:
        return False
    return (
        item.get('completion_status') in {'complete', 'empty'}
        and proof.get('verified') is True
        and proof.get('skip_store') is not True
        and normalization.get('complete') is not False
        and not normalization.get('quarantined_rows')
    )


def _rows_fetched(item):
    value = item.get('rows_fetched')
    if value is None and item.get('completion_status') == 'empty':
        return 0
    if type(value) is int and value >= 0 or isinstance(value, str) and len(value) <= 18 and value.isascii() and value.isdecimal():
        count = int(value)
        if item.get('completion_status') != 'empty' or count == 0:
            return count
    return None


def transport_manifest(evidence, requests=None) -> dict:
    """Match every frozen request; deduplicate resumed evidence by request key.

    ``None`` retains the direct audit API's caller-owned scope. Runtime callers
    always provide the actual frozen request manifest (including an empty one).
    """
    records = list(evidence or ())
    keyed = {str(item['request_key']): item for item in records if item.get('request_key')}
    expected = {str(item['request_key']) for item in requests or () if item.get('request_key')}
    if requests is None:
        selected = list(keyed.values()) if len(keyed) == len(records) else records
        missing = []
    else:
        missing = sorted(expected - keyed.keys())
        selected = [keyed[key] for key in sorted(expected & keyed.keys())]
        # Legacy checkpoints without a request key are safe only for a single
        # planned request; they must not stand in for an entire market fan-out.
        if len(expected) == 1 and not keyed and len(records) == 1:
            selected, missing = records, []
    invalid = [str(item.get('request_key') or 'legacy') for item in selected if not request_verified(item)]
    verified = bool(selected) and not missing and not invalid
    if requests is not None and (not expected or len(expected) != len(requests)):
        verified = False
    counts = [_rows_fetched(item) for item in selected]
    total = sum(counts) if counts and all(n is not None for n in counts) else None
    return {'verified': verified, 'expected_requests': len(requests) if requests is not None else len(records),
            'verified_requests': sum(request_verified(item) for item in selected),
            'missing_request_keys': missing, 'invalid_request_keys': invalid,
            'records': selected, 'rows_fetched': total}


def certified_execution_sql(alias: str = 'execution', *, empty: bool = False) -> str:
    """SQL predicate over the immutable plan and all post-reset request proofs.

    The alias is code-owned. Require an acquire completion checkpoint as well
    as every planned request, including for attention executions whose later
    business validation failed. Operator retries invalidate earlier proofs.
    """
    if not alias.replace('_', '').isalnum():
        raise ValueError('invalid execution alias')
    reset = f"""COALESCE((SELECT MAX(reset.sequence_number)
        FROM orchestration_v2.task_execution_event reset
        WHERE reset.task_execution_id={alias}.task_execution_id
          AND reset.event_type='execution.operator_retry'
          AND reset.payload->>'reset_data_nodes'='true'),0)"""
    plan = f"CASE WHEN jsonb_typeof({alias}.frozen_scope->'requests')='array' THEN {alias}.frozen_scope->'requests' ELSE '[]'::jsonb END"
    zero_rows = """AND (proof.payload->>'rows_fetched' ~ '^0+$' OR
                        (proof.payload->>'rows_fetched' IS NULL AND proof.payload->>'completion_status'='empty'))""" if empty else ''
    # Resolve checkpoints once per execution. Looking up every prior and newer
    # event for every request makes a full-market fan-out quadratic.
    return f"""(
      WITH planned AS MATERIALIZED (
        SELECT NULLIF(r->>'request_key','') AS key FROM jsonb_array_elements({plan}) r
      ), plan_info AS (
        SELECT count(*) AS size, count(DISTINCT key) AS valid_keys, min(key) AS only_key FROM planned
      ), recent AS MATERIALIZED (
        SELECT e.payload, e.sequence_number, e.event_type
        FROM orchestration_v2.task_execution_event e
        WHERE e.task_execution_id={alias}.task_execution_id AND e.sequence_number>{reset}
          AND e.event_type IN ('node.acquire.request_completed','node.acquire.completed')
      ), requests AS (
        SELECT payload, sequence_number, payload->>'request_key' AS key, count(*) OVER () AS total
        FROM recent WHERE event_type='node.acquire.request_completed'
      ), latest AS (
        SELECT DISTINCT ON (normalized.key) normalized.key, normalized.payload
        FROM (
          SELECT CASE WHEN r.key IS NULL AND r.total=1 AND p.size=1 THEN p.only_key
                      ELSE r.key END AS key, r.payload, r.sequence_number
          FROM requests r CROSS JOIN plan_info p
        ) normalized ORDER BY normalized.key, normalized.sequence_number DESC
      )
      SELECT p.size > 0 AND p.size=p.valid_keys
        AND EXISTS (SELECT 1 FROM recent WHERE event_type='node.acquire.completed')
        AND NOT EXISTS (
          SELECT 1 FROM planned request LEFT JOIN latest proof USING (key)
          WHERE NOT COALESCE((({alias}.task_key <> 'fina_mainbz' OR
                 proof.payload->'completion_evidence'->>'mainbz_classifications_verified'='true')
            AND NOT (COALESCE(proof.payload->'completion_evidence'->>'source','')='historical_db'
                AND COALESCE(proof.payload->'completion_evidence'->>'reference_response_manifest','false')='true'
                AND (COALESCE(proof.payload->'completion_evidence'->'supplier_missing_keys','[]'::jsonb) <> '[]'::jsonb
                     OR COALESCE(jsonb_typeof(proof.payload->'completion_evidence'->'day_manifests'),'array') <> 'array'
                     OR EXISTS (SELECT 1 FROM jsonb_array_elements(
                            CASE WHEN jsonb_typeof(proof.payload->'completion_evidence'->'day_manifests')='array'
                            THEN proof.payload->'completion_evidence'->'day_manifests' ELSE '[]'::jsonb END) session
                         WHERE jsonb_typeof(session) <> 'object'
                           OR COALESCE(session->'supplier_missing_keys','[]'::jsonb) <> '[]'::jsonb)))
            AND (proof.payload->>'completion_status' <> 'empty' OR proof.payload->>'rows_fetched' IS NULL
                 OR proof.payload->>'rows_fetched' ~ '^0+$')
            {zero_rows}
            AND proof.payload->>'completion_status' IN ('complete','empty')
            AND proof.payload->'completion_evidence'->>'verified'='true'
            AND COALESCE(proof.payload->'completion_evidence'->>'skip_store','false') <> 'true'
            AND COALESCE(proof.payload->'completion_evidence'->'normalization'->>'complete','true') <> 'false'
            AND COALESCE(proof.payload->'completion_evidence'->'normalization'->>'quarantined_rows','0') = '0'),false)
        )
      FROM plan_info p
    )"""
