"""Independent shape/value checks for materialized research payloads."""
from psycopg2 import sql


def business_predicate(dataset, *, require_valuation_readiness=True):
    if dataset == 'local_factor_snapshot':
        from service.research.local_factors.catalog import FACTOR_SPECS, MAX_ABS_FACTOR_VALUE
        from service.research.local_factors.materializer import FORMULA_DIGEST
        from service.research.local_factors.quality import required_bars
        names = [spec.name for spec in FACTOR_SPECS]
        # Old snapshots can contain finite values computed before a window existed.
        minimum_sessions = [required_bars(name) if name.startswith(('high_low_', 'alpha101_'))
                            or name == 'days_beyond_upper_lower_21d' else 0 for name in names]
        return sql.SQL('''
            formula_digest={digest} AND cardinality(factor_values)=272
            AND length(ready_mask::text)=272
            AND ready_count=length(replace(ready_mask::text,'0',''))
            AND audit_evidence->>'status'='ready'
            AND audit_evidence->'unresolved'='{{}}'::jsonb
            AND NOT EXISTS (
                SELECT 1 FROM unnest(factor_values) WITH ORDINALITY AS v(value,pos)
                WHERE NOT COALESCE(CASE WHEN substring(ready_mask::text,v.pos::int,1)='1'
                    THEN v.value BETWEEN -{maximum} AND {maximum}
                         AND (audit_evidence->>'listing_sessions_observed' IS NULL
                              OR (jsonb_typeof(audit_evidence->'listing_sessions_observed')='number'
                                  AND audit_evidence->'listing_sessions_observed' >= to_jsonb(({sessions}::int[])[v.pos])))
                    ELSE v.value IS NULL
                         AND length(audit_evidence->'excluded'->>({names}::text[])[v.pos])>0
                         AND (audit_evidence->'excluded'->>({names}::text[])[v.pos])
                             NOT IN ('numerically_unstable_extreme_value',
                                     'undefined_formula_domain_with_complete_market_window')
                    END, false))
        ''').format(digest=sql.Literal(FORMULA_DIGEST), maximum=sql.Literal(MAX_ABS_FACTOR_VALUE),
                    names=sql.Literal(names), sessions=sql.Literal(minimum_sessions))
    if dataset == 'technical_factor_snapshot':
        import json
        from service.research.local_factors.ownership import TECHNICAL_FEATURES, SHARED_TECHNICAL_FIELDS
        from service.research.local_factors.catalog import MAX_ABS_FACTOR_VALUE, FACTOR_BY_NAME
        names = list(TECHNICAL_FEATURES)
        shared_names = list(SHARED_TECHNICAL_FIELDS.values())
        shared_values = sql.SQL(',').join(sql.SQL('f.factor_values[{}]').format(
            sql.Literal(FACTOR_BY_NAME[name].position)) for name in shared_names)
        # Parse the native JSON once. Repeated scalar projections of the wide,
        # toasted compatibility view decompressed it once per indicator.
        return sql.SQL("""
            EXISTS (SELECT 1 FROM local_factor_current f
                WHERE f.trade_date=technical_factor_snapshot.snapshot_date
                  AND f.ts_code=technical_factor_snapshot.ts_code
                  AND f.technical_values->>'adjustment_status'='applied'
                  AND f.audit_evidence->>'technical_status'='ready'
                  AND NOT EXISTS (
                    SELECT 1 FROM jsonb_each({defaults}::jsonb || f.technical_values) v
                    WHERE v.key=ANY({names}::text[]) AND NOT COALESCE(
                        (jsonb_typeof(v.value)='number' AND v.value BETWEEN {minimum}::jsonb AND {maximum_json}::jsonb)
                        OR (v.value='null'::jsonb AND length(f.audit_evidence->'excluded'->>v.key)>0),false))
                  AND NOT EXISTS (
                    SELECT 1 FROM unnest(ARRAY[{shared_values}]::float8[]) WITH ORDINALITY v(value,pos)
                    WHERE NOT COALESCE(v.value BETWEEN -{maximum} AND {maximum}
                        OR (v.value IS NULL
                            AND length(f.audit_evidence->'excluded'->>({shared_names}::text[])[v.pos])>0), false)))
        """).format(defaults=sql.Literal(json.dumps(dict.fromkeys(names))), names=sql.Literal(names),
                    minimum=sql.Literal(json.dumps(-MAX_ABS_FACTOR_VALUE)),
                    maximum_json=sql.Literal(json.dumps(MAX_ABS_FACTOR_VALUE)),
                    shared_values=shared_values,maximum=sql.Literal(MAX_ABS_FACTOR_VALUE),
                    shared_names=sql.Literal(shared_names))
    if dataset == 'valuation_percentile_snapshot':
        checks = []
        for code in ('000300.SH', '000688.SH'):
            if require_valuation_readiness:
                checks.append(sql.SQL("(snapshots->{code}->'meta'->'publication'->>'publishable'='true' AND snapshots->{code}->'meta'->'publication'->>'certified_object'='same_date_valid_sample_distribution' AND snapshots->{code}->'meta'->'publication'->'blockers'='[]'::jsonb)").format(code=sql.Literal(code)))
            for metric in ('pe', 'pe_ttm', 'pb', 'ps_ttm', 'dv_ttm'):
                # A legitimately empty distribution (e.g. no positive profit)
                # has count zero and a null median; it is not missing input.
                checks.append(sql.SQL('''(
                    snapshots->{code}->'meta'->'numerical_check'->>{check}='passed'
                    AND jsonb_typeof(snapshots->{code}->'data'->'metrics'->{metric}->'valid_count')='number'
                    AND snapshots->{code}->'data'->'metrics'->{metric}->'missing_member_rows'='[]'::jsonb
                    AND COALESCE(snapshots->{code}->'data'->'metrics'->{metric}->'invalid_field_codes','[]'::jsonb)='[]'::jsonb
                    AND (snapshots->{code}->'data'->'metrics'->{metric}->>'valid_count')::numeric
                         +jsonb_array_length(snapshots->{code}->'data'->'metrics'->{metric}->'missing_codes')
                         +jsonb_array_length(snapshots->{code}->'data'->'metrics'->{metric}->'nonpositive_excluded_codes')
                         =(snapshots->{code}->'data'->'metrics'->{metric}->>'population')::numeric
                    AND ((snapshots->{code}->'data'->'metrics'->{metric}->'valid_count' = '0'::jsonb
                          AND snapshots->{code}->'data'->'metrics'->{metric}->'median'='null'::jsonb)
                         OR (snapshots->{code}->'data'->'metrics'->{metric}->'valid_count' > '0'::jsonb
                             AND jsonb_typeof(snapshots->{code}->'data'->'metrics'->{metric}->'median')='number'
                             AND (snapshots->{code}->'data'->'metrics'->{metric}->>'median')::numeric BETWEEN -1e100 AND 1e100))
                )''').format(code=sql.Literal(code), metric=sql.Literal(metric),
                              check=sql.Literal(metric+'_count_median')))
        return sql.SQL(' AND ').join(checks)
    return sql.SQL('TRUE')
