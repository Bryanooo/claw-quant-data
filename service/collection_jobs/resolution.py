"""Shared SQL predicates for effective collection-failure resolution.

The execution ledger is immutable: a failed row remains failed after a later
run repairs the same scope.  Operator views therefore need a second,
effective state which answers whether that historical failure still requires
action.  Keeping this predicate in one module prevents the instance ledger and
the health centre from drifting to different definitions of "unresolved".
"""

from __future__ import annotations


def _api_name(alias: str) -> str:
    return f"COALESCE({alias}.api_name, {alias}.parameters->>'api_name')"


def _dataset_name(alias: str) -> str:
    api_name = _api_name(alias)
    return f"""
        CASE {api_name}
            WHEN 'trade_cal' THEN 'trade_calendar'
            WHEN 'daily' THEN 'stock_daily'
            WHEN 'daily_basic' THEN 'stock_daily_basic'
            WHEN 'bak_basic' THEN 'bak_basic'
            WHEN 'stk_limit' THEN 'stock_limit'
            WHEN 'suspend_d' THEN 'stock_suspend'
            WHEN 'fina_indicator' THEN 'financial_indicator'
            WHEN 'fina_indicator_vip' THEN 'financial_indicator'
            WHEN 'fx_daily' THEN 'forex_daily'
            WHEN 'ths_daily' THEN 'industry_daily'
            WHEN 'balancesheet_vip' THEN 'balancesheet'
            WHEN 'cashflow_vip' THEN 'cashflow'
            WHEN 'income_vip' THEN 'income'
            WHEN 'express_vip' THEN 'express'
            WHEN 'fina_mainbz_vip' THEN 'fina_mainbz'
            WHEN 'forecast_vip' THEN 'forecast'
            ELSE {api_name}
        END
    """


def failure_predicate(alias: str) -> str:
    """Return the immutable-ledger failure predicate."""
    return (
        f"({alias}.status='failed' OR "
        f"{alias}.completion_status IN ('failed','incomplete'))"
    )


def within_delivery_window(alias: str) -> str:
    return f"""
        (
            {alias}.status='success'
            AND {alias}.completion_status='incomplete'
            AND {alias}.expected_for IS NOT NULL
            AND EXISTS (
                SELECT 1
                FROM sys_collection_delivery_plan AS delivery
                WHERE delivery.api_name={_api_name(alias)}
                  AND delivery.expected_for={alias}.expected_for
                  AND NOW() <= delivery.due_at
            )
        )
    """


def recovered_job_id(alias: str) -> str:
    return f"""
        SELECT recovered.job_id
        FROM sys_collection_job AS recovered
        WHERE recovered.status='success'
          AND recovered.job_kind='leaf'
          AND recovered.job_id > {alias}.job_id
          AND {_api_name('recovered')}={_api_name(alias)}
          AND (
                ({alias}.expected_for IS NOT NULL
                 AND recovered.expected_for={alias}.expected_for)
             OR ({alias}.period_key IS NOT NULL
                 AND recovered.period_key={alias}.period_key)
          )
          AND (
                {alias}.status='failed'
             OR recovered.completion_status='complete'
          )
        ORDER BY recovered.job_id
        LIMIT 1
    """


def recovered_job_exists(alias: str) -> str:
    return f"""
        EXISTS (
            SELECT 1
            FROM sys_collection_job AS recovered
            WHERE recovered.status='success'
              AND recovered.job_kind='leaf'
              AND recovered.job_id > {alias}.job_id
              AND {_api_name('recovered')}={_api_name(alias)}
              AND (
                    ({alias}.expected_for IS NOT NULL
                     AND recovered.expected_for={alias}.expected_for)
                 OR ({alias}.period_key IS NOT NULL
                     AND recovered.period_key={alias}.period_key)
              )
              AND (
                    {alias}.status='failed'
                 OR recovered.completion_status='complete'
              )
        )
    """


def recovered_campaign_id(alias: str) -> str:
    return f"""
        SELECT recovered_campaign.campaign_id
        FROM sys_collection_fanout_campaign AS recovered_campaign
        WHERE {alias}.parent_job_id IS NULL
          AND recovered_campaign.api_name={_api_name(alias)}
          AND recovered_campaign.status='success'
          AND recovered_campaign.completion_status='complete'
          AND (
                {alias}.expected_for IS NULL
             OR recovered_campaign.expected_for >= {alias}.expected_for
          )
          AND recovered_campaign.request @>
              jsonb_build_object('api_name', {_api_name(alias)})
          AND (
                COALESCE({alias}.parameters->'parameters', '{{}}'::jsonb)
                    = '{{}}'::jsonb
             OR recovered_campaign.request @>
                COALESCE({alias}.parameters->'parameters', '{{}}'::jsonb)
          )
        ORDER BY recovered_campaign.campaign_id
        LIMIT 1
    """


def recovered_campaign_exists(alias: str) -> str:
    return f"""
        EXISTS (
            SELECT 1
            FROM sys_collection_fanout_campaign AS recovered_campaign
            WHERE {alias}.parent_job_id IS NULL
              AND recovered_campaign.api_name={_api_name(alias)}
              AND recovered_campaign.status='success'
              AND recovered_campaign.completion_status='complete'
              AND (
                    {alias}.expected_for IS NULL
                 OR recovered_campaign.expected_for >= {alias}.expected_for
              )
              AND recovered_campaign.request @>
                  jsonb_build_object('api_name', {_api_name(alias)})
              AND (
                    COALESCE({alias}.parameters->'parameters', '{{}}'::jsonb)
                        = '{{}}'::jsonb
                 OR recovered_campaign.request @>
                    COALESCE({alias}.parameters->'parameters', '{{}}'::jsonb)
              )
        )
    """


def recovered_audit_id(alias: str) -> str:
    return f"""
        SELECT recovered_audit.audit_id
        FROM sys_data_coverage_audit AS recovered_audit
        WHERE {alias}.expected_for IS NOT NULL
          AND recovered_audit.dataset_name={_dataset_name(alias)}
          AND recovered_audit.status='complete'
          AND {alias}.expected_for BETWEEN
              recovered_audit.start_date AND recovered_audit.end_date
          AND recovered_audit.finished_at > {alias}.finished_at
        ORDER BY recovered_audit.finished_at, recovered_audit.audit_id
        LIMIT 1
    """


def recovered_audit_exists(alias: str) -> str:
    return f"""
        EXISTS (
            SELECT 1
            FROM sys_data_coverage_audit AS recovered_audit
            WHERE {alias}.expected_for IS NOT NULL
              AND recovered_audit.dataset_name={_dataset_name(alias)}
              AND recovered_audit.status='complete'
              AND {alias}.expected_for BETWEEN
                  recovered_audit.start_date AND recovered_audit.end_date
              AND recovered_audit.finished_at > {alias}.finished_at
        )
    """


def unresolved_failure_predicate(alias: str) -> str:
    """Return failures which still need operator action.

    Batch parents and period-less probes are audit history rather than
    independently recoverable data scopes.  Leaf failures stop being current
    incidents after a later matching job, complete fan-out campaign, or
    coverage audit proves the scope healthy.
    """
    return f"""
        (
            {failure_predicate(alias)}
            AND {alias}.job_kind='leaf'
            AND {_api_name(alias)} IS NOT NULL
            AND ({alias}.period_key IS NOT NULL OR {alias}.expected_for IS NOT NULL)
            AND NOT {within_delivery_window(alias)}
            AND NOT {recovered_job_exists(alias)}
            AND NOT {recovered_campaign_exists(alias)}
            AND NOT {recovered_audit_exists(alias)}
        )
    """


def resolution_columns(alias: str) -> str:
    """Project effective resolution fields for one selected ledger page."""
    failed = failure_predicate(alias)
    unresolved = unresolved_failure_predicate(alias)
    job = recovered_job_id(alias)
    campaign = recovered_campaign_id(alias)
    audit = recovered_audit_id(alias)
    has_job = recovered_job_exists(alias)
    has_campaign = recovered_campaign_exists(alias)
    has_audit = recovered_audit_exists(alias)
    window = within_delivery_window(alias)
    return f"""
        CASE
            WHEN NOT {failed} THEN NULL
            WHEN {unresolved} THEN 'unresolved'
            WHEN {has_job} OR {has_campaign} OR {has_audit} THEN 'recovered'
            WHEN {window} THEN 'pending_recovery'
            ELSE 'historical'
        END AS resolution_state,
        CASE
            WHEN NOT {failed} THEN NULL
            WHEN {unresolved} THEN 'still_unresolved'
            WHEN {has_job} THEN 'recovered_by_later_job'
            WHEN {has_campaign} THEN 'recovered_by_fanout_campaign'
            WHEN {has_audit} THEN 'recovered_by_coverage_audit'
            WHEN {window} THEN 'within_delivery_window'
            WHEN {alias}.job_kind='batch' THEN 'batch_parent_history'
            WHEN {_api_name(alias)} IS NULL
              OR ({alias}.period_key IS NULL AND {alias}.expected_for IS NULL)
              THEN 'scope_not_actionable'
            ELSE 'historical_non_actionable'
        END AS resolution_reason,
        CASE
            WHEN {failed} AND {has_job} THEN ({job})
            ELSE NULL
        END AS resolved_by_job_id,
        CASE
            WHEN {failed} AND NOT {has_job} AND {has_campaign} THEN ({campaign})
            ELSE NULL
        END AS resolved_by_campaign_id,
        CASE
            WHEN {failed} AND NOT {has_job} AND NOT {has_campaign} AND {has_audit}
              THEN ({audit})
            ELSE NULL
        END AS resolved_by_audit_id
    """
