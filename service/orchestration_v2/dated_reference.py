"""Closed-date reference refreshes. One execution owns all provider partitions."""
from datetime import date, timedelta

from service.db import query
from service.orchestration_v2.contracts import ExecutionRequest

TYPES = ('HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK')


def partitions(key, day):
    value = day.strftime('%Y%m%d')
    if key == 'pledge_stat':
        return ({'end_date': value},)
    if key == 'stock_hsgt':
        return tuple({'trade_date': value, 'type': kind} for kind in TYPES)
    raise ValueError(f'unknown dated reference: {key}')


def enqueue(store, key, day):
    partitions(key, day)  # reject unknown keys before creating an instance
    return store.create_execution(ExecutionRequest(
        task_key=key, purpose='daily', trigger_source='schedule',
        observation_key=day.isoformat(), observation_start=day, observation_end=day,
        idempotency_key=f'v2:dated-reference:{key}:{day}:v1',
        frozen_scope={'dated_reference': key, 'force_acquire': True},
    ))


def dispatch(store, now):
    # Before the evening patrol only closed preceding dates are eligible.
    cutoff = now.date() - timedelta(days=int(now.hour < 19))
    days = query("SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 "
                 "AND cal_date BETWEEN %s AND %s ORDER BY cal_date",
                 (cutoff-timedelta(days=6), cutoff))
    active = store.active_task_keys()
    scopes = [('stock_hsgt', r['cal_date']) for r in days]
    errors = {}
    if 'pledge_stat' in active and now.hour >= 19:
        # Release end_dates move around holidays (e.g. 20260924 and 20260930).
        # Probe at most eight exact dates per evening patrol, without treating
        # an empty probe as an accepted full-market partition.
        from collectors.stock.reference.pledge_stat import PledgeStatCollector
        provider = None
        for offset in range(8):
            day = cutoff - timedelta(days=offset)
            try:
                if provider is None:
                    provider = PledgeStatCollector().pro
                frame = provider.pledge_stat(end_date=day.strftime('%Y%m%d'), limit=1)
                if not frame.empty:
                    if set(frame.end_date.astype(str)) != {day.strftime('%Y%m%d')}:
                        raise ValueError('provider ignored pledge end_date')
                    scopes.append(('pledge_stat', day))
            except Exception as exc:
                errors[f'pledge_stat:{day}'] = str(exc)
                break  # do not multiply throttled/failed provider requests
    for key, day in scopes:
        if key in active:
            try:
                enqueue(store, key, day)
            except Exception as exc:
                errors[f'{key}:{day}'] = str(exc)
    if 'stk_rewards' in active and now.hour >= 21:
        from service.acquisition_runtime.fanout import list_fanout_values
        try:
            period = date(now.year - 1, 12, 31)
            codes = sorted(set(list_fanout_values('stock', as_of=period,
                               active_since=date(period.year, 1, 1))))
            reward_partitions(period, codes)  # validate the cap before creating any work
            store.create_execution(ExecutionRequest(
                task_key='stk_rewards', purpose='daily', trigger_source='schedule',
                observation_key=period.isoformat(), observation_start=period, observation_end=period,
                idempotency_key=f'v2:reward-review:{now:%Y-%m}:{period}',
                frozen_scope={'annual_reward_codes': codes, 'force_acquire': True}))
        except Exception as exc:
            errors['stk_rewards'] = str(exc)
    return errors


def reward_partitions(day, codes):
    if (not isinstance(codes, list) or not 0 < len(codes) <= 6400 or
            len(set(codes)) != len(codes) or (day.month, day.day) != (12, 31)):
        raise ValueError('invalid annual salary scope (maximum 320 batches)')
    return tuple({'ts_code': ','.join(codes[i:i+20]), 'end_date': day.strftime('%Y%m%d')}
                 for i in range(0, len(codes), 20))
