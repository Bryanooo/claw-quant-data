"""Reference-only V2 workflow; never publishes whole-market factor readiness."""
from datetime import date

from service.acquisition_runtime.models import BatchChildSpec
from service.acquisition_runtime.registry import TASKS
from service.data_coverage.models import CoverageAuditResult
from service.db import query
from service.orchestration_v2.contracts import DatasetStateUpdate, DataStatus, ExecutionRequest
from service.orchestration_v2.contracts import TaskDefinitionDocument
from service.research.local_factors.catalog import FACTOR_SPECS
from service.research.local_factors.reference_sampling import (
    MAX_WINDOW_DAYS,
    SAMPLE_METHOD,
    reference_sample_plan,
)

TASK_KEY = 'factor_reference_sample'

# One session returns one row per catalogued factor; a windowed response is
# the same rows multiplied by the number of sessions and must stay below the
# provider's 6,000-row cap.
REFERENCE_PAGE_SIZE = 1_000
REFERENCE_WINDOW_PAGE_SIZE = 6_000

# Routine dispatch waits until this many unverified sessions have accumulated,
# then settles the whole backlog with one window execution. One window costs
# one provider call per security, so amortised cost is SAMPLE_SIZE / threshold
# calls per session; the price is that a fresh session stays unverified until
# the batch fires.
WINDOW_DISPATCH_THRESHOLD = MAX_WINDOW_DAYS


def request_window(params):
    """Split one request's parameters into its date form and its page budget.

    A single session keeps the exact ``trade_date`` request the provider
    contract was probed with. A window switches to ``start_date``/``end_date``
    and widens the page to the provider's 6,000-row cap, because a windowed
    response is only complete while it stays strictly below that cap.
    """
    windowed = 'start_date' in params
    return (windowed,
            {'start_date': params['start_date'], 'end_date': params['end_date']}
            if windowed else {'trade_date': params['trade_date']},
            REFERENCE_WINDOW_PAGE_SIZE if windowed else REFERENCE_PAGE_SIZE)


def _window_bounds(params):
    from datetime import datetime
    if 'start_date' in params:
        return (datetime.strptime(params['start_date'], '%Y%m%d').date(),
                datetime.strptime(params['end_date'], '%Y%m%d').date())
    day = datetime.strptime(params['trade_date'], '%Y%m%d').date()
    return day, day


def _historical_sessions(params, names):
    """Replay only physically complete security/session factor catalogues.

    Cross-sectional row counts cannot establish supplier absence for a
    particular security. Missing keys require an actual response manifest.
    Explicitly stored NULL values remain returned keys, not missing keys.
    """
    start, end = _window_bounds(params)
    calendar = query('''SELECT cal_date FROM trade_cal WHERE exchange='SSE'
                        AND is_open=1 AND cal_date BETWEEN %s AND %s
                        ORDER BY cal_date''', (start, end))
    sessions = [row['cal_date'] for row in calendar if row.get('cal_date')]
    if not sessions:
        return None
    rows = query('''SELECT trade_date, factor_name, factor_value
        FROM tushare_current_factor_value
        WHERE ts_code=%s AND trade_date BETWEEN %s AND %s''',
        (params['ts_code'], start, end))
    by_day = {}
    for row in rows or []:
        if row['factor_name'] in names:
            by_day.setdefault(row['trade_date'], {})[row['factor_name']] = row['factor_value']
    if any(set(by_day.get(day, {})) != names for day in sessions):
        return None
    manifests = []
    for day in sessions:
        present = by_day.get(day) or {}
        nulls = sorted(name for name, value in present.items() if value is None)
        manifests.append({
            'ts_code': params['ts_code'], 'trade_date': day.strftime('%Y%m%d'),
            'verified': True, 'reference_response_manifest': True,
            'returned_keys': sorted(present), 'explicit_null_keys': nulls,
            'supplier_missing_keys': sorted(names - set(present)),
            'source': 'historical_db',
        })
    return manifests, len(rows or [])


def acquire_reference(spec):
    """One bounded, exact security response, with durable absence evidence."""
    from collectors.tushare_raw import CatalogRawCollector, IncompleteCollectionError
    from service.acquisition_runtime.models import TaskExecutionResult
    params = spec.parameters['parameters']
    names = {s.name for s in FACTOR_SPECS}
    replayed = _historical_sessions(params, names)
    if replayed is not None:
        manifests, row_count = replayed
        windowed = 'start_date' in params
        returned, nulls = set(), set()
        for entry in manifests:
            returned.update(entry['returned_keys'])
            nulls.update(entry['explicit_null_keys'])
        evidence = {'verified': True, 'reference_response_manifest': True,
                    'ts_code': params['ts_code'],
                    'trade_date': params['end_date'] if windowed else params['trade_date'],
                    'returned_keys': sorted(returned),
                    'explicit_null_keys': sorted(nulls),
                    'supplier_missing_keys': sorted(names - returned),
                    'pagination': 'historical_replay', 'page_limit': 0,
                    'source': 'historical_db',
                    'numerical_equivalence': False,
                    'day_manifests': manifests, 'day_count': len(manifests)}
        if windowed:
            evidence['window'] = {'start_date': params['start_date'],
                                  'end_date': params['end_date']}
        return TaskExecutionResult(rows_inserted=0, rows_fetched=row_count,
            completion_status='complete', completion_evidence=evidence)
    windowed, _, page_size = request_window(params)
    collector = CatalogRawCollector('factor_value')
    try:
        frame = collector.fetch(**params, limit=page_size, offset=0)
    except Exception as exc:
        from collectors.base import classify_tushare_error, CollectorRateLimitError
        from service.tushare_rate_limit import (
            TushareRateSlotDeferredError, mark_daily_quota_exhausted,
        )
        classified = classify_tushare_error(exc)
        if isinstance(classified, CollectorRateLimitError):
            if '次/天' in str(exc):
                mark_daily_quota_exhausted('factor_value')
            raise TushareRateSlotDeferredError(
                'factor_value', classified.retry_after_seconds
            ) from exc
        if classified is not None:
            raise classified from exc
        raise
    if frame is None:
        raise IncompleteCollectionError('reference response is not a dataframe')
    if len(frame) >= page_size:
        raise IncompleteCollectionError('reference response reached page limit')
    returned, nulls = set(), set()
    manifests = []
    if len(frame):
        required = {'ts_code', 'trade_date', 'factor_name', 'factor_value'}
        if not required.issubset(frame.columns):
            raise IncompleteCollectionError('reference response lacks contract columns')
        dates = set(str(item) for item in frame.trade_date)
        if windowed:
            outside = [item for item in dates
                       if item < params['start_date'] or item > params['end_date']]
            if outside or set(frame.ts_code) != {params['ts_code']}:
                raise IncompleteCollectionError('reference response scope or keys mismatch')
            if frame.duplicated(['trade_date', 'factor_name']).any():
                raise IncompleteCollectionError('reference response scope or keys mismatch')
        elif (set(frame.ts_code) != {params['ts_code']} or
                dates != {params['trade_date']} or
                frame.factor_name.duplicated().any()):
            raise IncompleteCollectionError('reference response scope or keys mismatch')
        returned = set(frame.factor_name)
        if returned - names:
            raise IncompleteCollectionError('unknown reference factor keys')
        nulls = set(frame.loc[frame.factor_value.isna(), 'factor_name'])
        # A windowed response carries several sessions, so absence evidence is
        # recorded per session; a whole-window summary would let one truncated
        # day hide behind the others.
        for day, group in frame.groupby(frame.trade_date.astype(str)):
            day_keys = set(group.factor_name)
            manifests.append({
                'ts_code': params['ts_code'], 'trade_date': str(day),
                'verified': True, 'reference_response_manifest': True,
                'returned_keys': sorted(day_keys),
                'explicit_null_keys': sorted(
                    set(group.loc[group.factor_value.isna(), 'factor_name'])),
                'supplier_missing_keys': sorted(names - day_keys),
            })
    elif not windowed:
        # An empty single-session response is itself the absence evidence for
        # that session. An empty window cannot say which sessions it covers,
        # so it records none and the audit reports every session as missing.
        manifests.append({
            'ts_code': params['ts_code'], 'trade_date': params['trade_date'],
            'verified': True, 'reference_response_manifest': True,
            'returned_keys': [], 'explicit_null_keys': [],
            'supplier_missing_keys': sorted(names),
        })
    stored = collector.store(frame) if len(frame) else 0
    if stored != len(frame) or not getattr(collector, 'normalization_evidence', {}).get('complete', True):
        raise IncompleteCollectionError('reference storage did not preserve the response')
    evidence = {'verified': True, 'reference_response_manifest': True,
                'ts_code': params['ts_code'],
                'trade_date': params['end_date'] if windowed else params['trade_date'],
                'returned_keys': sorted(returned), 'explicit_null_keys': sorted(nulls),
                'supplier_missing_keys': sorted(names-returned),
                'pagination': 'terminal_short_page', 'page_limit': page_size,
                'numerical_equivalence': False}
    if manifests:
        evidence['day_manifests'] = manifests
        evidence['day_count'] = len(manifests)
    if windowed:
        evidence['window'] = {'start_date': params['start_date'],
                              'end_date': params['end_date']}
    return TaskExecutionResult(rows_inserted=stored, rows_fetched=len(frame),
        completion_status='complete' if len(frame) else 'empty',
        completion_evidence=evidence)


def reference_definition(base_document):
    """Build a draft from the published endpoint binding, not a new source."""
    import copy
    data = copy.deepcopy(base_document)
    data.update(task_key=TASK_KEY, input_datasets=['local_factor_snapshot'],
                output_datasets=[TASK_KEY], dependencies=[],
                schedule={'mode': 'manual', 'timezone': 'Asia/Shanghai'},
                scope_contract={'cadence': 'daily', 'reference_only': True,
                                'sample_method': SAMPLE_METHOD},
                resource={'resource_class': 'generic', 'priority': 10,
                          'max_node_concurrency': 1, 'source_quota_key': 'factor_value'},
                validation_contract={'outputs': [TASK_KEY], 'dataset_audits': [{
                    'dataset_name': TASK_KEY, 'audit_mode': 'expected_partition',
                    'period_granularity': 'day', 'rule_revision': 1,
                    'date_column': 'trade_date', 'require_transport_proof': False,
                }]})
    return TaskDefinitionDocument.model_validate(data)


def frozen_codes(execution):
    scope = execution.get('frozen_scope') or {}
    codes = scope.get('reference_securities', [])
    if (scope.get('reference_sample_method') != SAMPLE_METHOD or
            not isinstance(codes, list) or not 30 <= len(codes) <= 128 or
            any(not isinstance(code, str) or not code for code in codes) or
            len(codes) != len(set(codes))):
        raise ValueError('reference execution requires a frozen unique 30..128 security sample')
    return codes


def frozen_days(execution):
    """Sessions an execution covers, oldest first.

    One execution may span several sessions so that a single request per
    security replaces one request per security per day. The bound is the
    provider's row cap, not a scheduling preference.
    """
    scope = execution.get('frozen_scope') or {}
    stored = scope.get('reference_trade_dates')
    days = [date.fromisoformat(item) for item in stored
            if isinstance(item, str)] if isinstance(stored, list) else []
    if not days:
        days = [execution['observation_end']]
    days = sorted(set(days))
    if any(day < execution['observation_start'] or day > execution['observation_end'] for day in days):
        raise ValueError('reference sessions fall outside the frozen observation range')
    if len(days) > MAX_WINDOW_DAYS:
        raise ValueError(
            f'reference execution may cover at most {MAX_WINDOW_DAYS} sessions')
    return days


def plan_requests(execution):
    codes = frozen_codes(execution)
    days = frozen_days(execution)
    # One request per security per window; the window size is bounded by the
    # provider row cap, so a wider window never costs another call.
    windowed, window, page_size = request_window(
        {'start_date': days[0].strftime('%Y%m%d'), 'end_date': days[-1].strftime('%Y%m%d')}
        if len(days) > 1 else {'trade_date': days[0].strftime('%Y%m%d')})
    span = f'{days[0]}..{days[-1]}' if windowed else str(days[0])
    return tuple(BatchChildSpec(
        task_name='tushare_interface', api_name='factor_value',
        parameters={'api_name': 'factor_value',
                    'parameters': dict(ts_code=code, **window),
                    'complete': True, 'page_size': page_size,
                    'max_pages': 10, 'resume': True},
        idempotency_key=f'reference:{SAMPLE_METHOD}:{span}:{code}',
        cadence='daily', period_key=span, expected_for=days[-1],
        handler=TASKS.handler_metadata('tushare_interface', {'api_name': 'factor_value',
            'parameters': dict(ts_code=code, **window)}),
        priority=10, resource_class='generic',
    ) for code in codes)


def _manifest_sessions(item):
    """Per-session manifests from one request, older flat events included."""
    sessions = item.get('day_manifests')
    if isinstance(sessions, list) and sessions:
        return [entry for entry in sessions if isinstance(entry, dict)]
    return [item]


def audit_sample(execution):
    codes = frozen_codes(execution)
    days = frozen_days(execution)
    wanted_days = {day.strftime('%Y%m%d') for day in days}
    names = [spec.name for spec in FACTOR_SPECS]
    rows = query('''SELECT DISTINCT ON (COALESCE(payload->>'request_key',
            payload->'completion_evidence'->>'ts_code', event_id::text))
            payload->'completion_evidence' AS manifest
        FROM orchestration_v2.task_execution_event WHERE task_execution_id=%s
          AND event_type='node.acquire.request_completed'
          AND sequence_number > COALESCE((SELECT MAX(sequence_number)
            FROM orchestration_v2.task_execution_event WHERE task_execution_id=%s
              AND event_type='execution.operator_retry'
              AND payload->>'reset_data_nodes'='true'), 0)
          ORDER BY COALESCE(payload->>'request_key',
            payload->'completion_evidence'->>'ts_code', event_id::text), sequence_number DESC''',
        (execution['task_execution_id'], execution['task_execution_id']))
    manifests = {}
    for row in rows:
        item = row['manifest'] or {}
        if item.get('verified') is not True or item.get('reference_response_manifest') is not True:
            continue
        for entry in _manifest_sessions(item):
            returned = set(entry.get('returned_keys', []))
            absent = set(entry.get('supplier_missing_keys', []))
            # Old replay manifests inferred absence from market-wide counts.
            # They cannot certify missing keys for this security/session.
            if entry.get('source', item.get('source')) == 'historical_db' and absent:
                continue
            if (entry.get('trade_date') in wanted_days
                    and entry.get('ts_code') in codes and returned.isdisjoint(absent)
                    and returned | absent == set(names)
                    and set(entry.get('explicit_null_keys', [])).issubset(returned)):
                manifests[(entry['ts_code'], entry['trade_date'])] = entry
    missing = {f'{code}@{day.isoformat()}': 'missing_verified_response'
               for code in codes for day in days
               if (code, day.strftime('%Y%m%d')) not in manifests}
    supplier_missing = {}
    for (code, _), item in manifests.items():
        if item['supplier_missing_keys']:
            supplier_missing.setdefault(code, set()).update(item['supplier_missing_keys'])
    supplier_missing = {code: sorted(keys) for code, keys in supplier_missing.items()}
    good = len(manifests)
    sources = {}
    for item in manifests.values():
        key = item.get('source', 'provider')
        sources[key] = sources.get(key, 0) + 1
    evidence = {'scope': 'reference_sample_only', 'whole_market_certified': False,
                'sample_method': SAMPLE_METHOD, 'sampled_codes': codes,
                'manifest_sources': sources,
                'expected_factor_count': len(names), 'missing_responses': missing,
                'supplier_missing_keys': supplier_missing,
                'expected_sessions': [day.isoformat() for day in days],
                'session_count': len(days),
                'explicit_null_keys': {f'{c}@{d}': m['explicit_null_keys']
                                       for (c, d), m in manifests.items()},
                'numerical_equivalence': False,
                'null_policy': 'explicit null rows retained; not numerical equivalence'}
    expected = len(codes) * len(days)
    result = CoverageAuditResult(
        dataset_name=TASK_KEY, strategy='reference_sample',
        start_date=days[0], end_date=days[-1],
        status='gaps' if missing else 'complete', expected_partitions=expected,
        present_partitions=good, missing_partitions=len(missing), observed_partitions=good,
        coverage_ratio=good/expected, partitions=(), evidence=evidence,
    )
    validation = {'verified': True, 'audit_status': result.status, 'evidence': evidence}
    update = DatasetStateUpdate(
        dataset_name=TASK_KEY, observation_key=execution['observation_key'],
        observation_start=days[0], observation_end=days[-1], contract_version=SAMPLE_METHOD,
        expectation_status='expected', data_status=DataStatus.GAPS if missing else DataStatus.COMPLETE,
        expected_count=expected, actual_count=good,
        validation_summary=validation, gap_summary={'missing_responses': missing,
                                                   'supplier_missing_keys': supplier_missing},
    )
    return [(result, update, validation)]


def dispatch_reference_sample(repository, day, *, exact_date=False, window_days=1):
    # Explicit activation follows the live single-security contract probe.
    active = repository.get_active_definition(TASK_KEY)
    if active is None:
        return {'created': False, 'reason': 'awaiting_verified_activation'}
    # Quota may recover after midnight or on a weekend. Select a committed
    # recent data date, not the wall-clock date; do not launch historical bulk.
    from datetime import timedelta
    if not exact_date:
        rows = query('''SELECT max(trade_date) AS day FROM local_factor_snapshot
                        WHERE schema_version='local-272-v4'
                          AND trade_date BETWEEN %s AND %s''', (day-timedelta(days=7), day))
        if not rows or rows[0]['day'] is None:
            return {'created': False, 'reason': 'no_recent_local_snapshot'}
        day = rows[0]['day']
        # Catch-up: the routine trigger only fires once enough unverified
        # sessions have piled up, then settles the oldest sessions of the
        # backlog. One window costs one provider call per security, so the
        # amortised cost per session drops by the window width.
        verified = query('''SELECT max(observation_end) AS day
            FROM orchestration_v2.task_execution
            WHERE task_key=%s AND status='success' ''', (TASK_KEY,))
        last_verified = verified[0]['day'] if verified else None
        lower = last_verified or (day - timedelta(days=WINDOW_DISPATCH_THRESHOLD * 2 + 10))
        pending = [row['cal_date'] for row in query(
            '''SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1
               AND cal_date > %s AND cal_date <= %s ORDER BY cal_date''',
            (lower, day)) if row.get('cal_date')]
        if len(pending) < WINDOW_DISPATCH_THRESHOLD:
            return {'created': False, 'reason': 'window_not_due',
                    'unverified_sessions': len(pending),
                    'dispatch_threshold': WINDOW_DISPATCH_THRESHOLD,
                    'last_verified': str(last_verified) if last_verified else None}
        window_days = min(MAX_WINDOW_DAYS, len(pending))
        day = pending[window_days - 1]
    plan = reference_sample_plan(day, window_days=window_days)
    if plan['status'] != 'planned':
        return {'created': False, 'reason': plan['status']}
    days = [date.fromisoformat(item) for item in plan.get('trade_dates') or []
            if isinstance(item, str)] or [day]
    execution, created = repository.create_execution(ExecutionRequest(
        task_key=TASK_KEY, purpose='daily', trigger_source='schedule',
        idempotency_key=(f'{TASK_KEY}:{SAMPLE_METHOD}:{days[0]}:{days[-1]}'
                         f':definition:{active["version"]}'),
        observation_key=f'reference-sample:{days[0]}:{days[-1]}',
        observation_start=days[0], observation_end=days[-1],
        frozen_scope={'reference_securities': plan['securities'],
                      'reference_sample_method': SAMPLE_METHOD,
                      'reference_trade_dates': plan.get('trade_dates') or []},
    ))
    return {'created': created, 'execution_id': execution['task_execution_id'],
            'window_days': len(days), 'estimated_calls': plan.get('estimated_calls', 0)}
