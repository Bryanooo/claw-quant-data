"""Actionable, bounded audit findings shared by API, worker and review reports."""


def audit_issues(result):
    issues = list(result.evidence.get('issues') or [])
    evidence = result.evidence
    if evidence.get('calendar_complete_for_range') is False:
        issues.append({'code': 'calendar_incomplete', 'calendar': evidence.get('calendar_exchange')})
    for partition in result.partitions:
        if partition.status not in {'missing', 'partial'}:
            continue
        reasons = getattr(partition, 'issues', ()) or (('missing_partition',) if partition.status == 'missing' else ('incomplete_partition',))
        for reason in reasons:
            issues.append({'code': reason, 'date': str(partition.partition_date),
                           'rows': partition.row_count, 'actual_entities': partition.entity_count,
                           'expected_entities': partition.expected_entity_count,
                           'entity_ratio': partition.entity_coverage_ratio})
    if evidence.get('empty_confirmed_after_window') is False:
        issues.append({'code': 'empty_response_not_mature', 'confirm_on_or_after': evidence.get('empty_confirm_on_or_after')})
    if result.status == 'unverified' and not issues:
        scope = evidence.get('declared_scope_evidence') or {}
        issues.append({'code': 'scope_transport_unverified', 'scope': [str(result.start_date), str(result.end_date)],
                       'first_unverified_date': scope.get('first_unverified_date'),
                       'unresolved_failures': scope.get('unresolved_failures', evidence.get('unresolved_failures')),
                       'active_jobs': scope.get('active_jobs', evidence.get('active_history_jobs'))})
    return issues


def audit_failure_detail(results):
    outputs = {}
    messages = []
    for result, update, _ in results:
        if update.ready:
            continue
        issues = audit_issues(result)
        outputs[update.dataset_name] = {
            'status': update.data_status.value, 'expected': result.expected_partitions,
            'present': result.present_partitions, 'missing': result.missing_partitions,
            'partial': result.partial_partitions, 'issues': issues[:20], 'issue_count': len(issues),
        }
        codes = ','.join(dict.fromkeys(item['code'] for item in issues)) or result.status
        messages.append(f'{update.dataset_name}: {codes}; missing={result.missing_partitions}, partial={result.partial_partitions}')
    return '; '.join(messages)[:4000], {'outputs': outputs}
