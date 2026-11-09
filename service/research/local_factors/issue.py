"""Interpret persisted factor evidence, including reasons written by older workers."""

from .quality import required_bars


def issue_category(name, has_value, evidence):
    if evidence.get('reason') == 'no_target_daily_bar':
        return 'no_target_daily_bar'
    reason = evidence.get('unresolved', {}).get(name) or evidence.get('excluded', {}).get(name) or ''
    age = evidence.get('listing_sessions_observed')
    if has_value:
        if isinstance(age, int) and (name.startswith(('high_low_', 'alpha101_')) or name == 'days_beyond_upper_lower_21d'):
            if (need := required_bars(name)) is not None and age < need:
                return 'incorrect_short_window_value'
        return 'calculated'
    if reason == 'numerically_unstable_extreme_value':
        return 'numeric_guard'
    if reason in ('undefined_formula_domain_with_complete_market_window', 'alpha101_result_requires_formula_input_review'):
        return 'formula_inputs_require_review'
    if reason == 'insufficient_listing_history':
        need = required_bars(name)
        return ('waiting_for_history' if need and isinstance(age, int) and age < need
                else 'formula_inputs_require_review')
    if reason == 'missing_input_or_undefined_requires_audit' and isinstance(age, int):
        need = required_bars(name)
        if need and age < need:
            return 'waiting_for_history'
    if reason == 'insufficient_listing_history_for_five_year_market_cap' or reason.startswith('insufficient_traded_bars'):
        return 'waiting_for_history'
    if reason.startswith('missing_financial_inputs:') or reason.startswith('missing_market_inputs:') or reason == 'missing_or_incomplete_adjustment':
        return 'trace_missing_inputs'
    if reason and evidence.get('excluded', {}).get(name) == reason:
        return 'excluded_by_domain'
    if reason.startswith(('invalid_market_inputs:', 'conflicting_financial_inputs:')):
        return 'invalid_source_input'
    return 'formula_inputs_require_review'
