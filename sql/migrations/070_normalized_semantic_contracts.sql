-- Promote audited generic-normalization identities to stable current-state
-- read contracts.  Lossless payload versions remain in tushare_norm_*; rows
-- with an incomplete required identity remain there for audit/replay and are
-- deliberately not exposed as a trustworthy current observation.

DO $$
DECLARE
    item RECORD;
    identity_sql TEXT;
    required_sql TEXT;
    revision_order_sql TEXT;
    view_name TEXT;
BEGIN
    FOR item IN
        SELECT * FROM (VALUES
            (
                'eco_cal',
                ARRAY['date', 'time', 'currency', 'country', 'event'],
                ARRAY['date', 'currency', 'country', 'event'],
                NULL::TEXT
            ),
            (
                'factor_value',
                ARRAY['trade_date', 'ts_code', 'factor_name'],
                ARRAY['trade_date', 'ts_code', 'factor_name'],
                NULL::TEXT
            ),
            (
                'fina_audit',
                ARRAY['ts_code', 'end_date'],
                ARRAY['ts_code', 'end_date'],
                'ann_date'
            ),
            (
                'fund_nav',
                ARRAY['nav_date', 'ts_code'],
                ARRAY['nav_date', 'ts_code'],
                'ann_date'
            ),
            (
                'fund_portfolio',
                ARRAY['ts_code', 'end_date', 'symbol'],
                ARRAY['ts_code', 'end_date', 'symbol'],
                'ann_date'
            ),
            (
                'index_weight',
                ARRAY['trade_date', 'index_code', 'con_code'],
                ARRAY['trade_date', 'index_code', 'con_code'],
                NULL::TEXT
            ),
            (
                'major_news',
                ARRAY['src', 'pub_time', 'title'],
                ARRAY['src', 'pub_time', 'title'],
                'pub_time'
            ),
            (
                'slb_sec_detail',
                ARRAY['trade_date', 'ts_code', 'tenor'],
                ARRAY['trade_date', 'ts_code', 'tenor'],
                NULL::TEXT
            )
        ) AS reviewed(
            api_name,
            identity_fields,
            required_identity_fields,
            availability_field
        )
    LOOP
        SELECT string_agg(format('%I', field_name), ', ')
        INTO identity_sql
        FROM unnest(item.identity_fields) AS field_name;

        SELECT string_agg(
                   format(
                       'NULLIF(BTRIM((%I)::text), '''') IS NOT NULL',
                       field_name
                   ),
                   ' AND '
               )
        INTO required_sql
        FROM unnest(item.required_identity_fields) AS field_name;

        revision_order_sql := CASE
            WHEN item.availability_field IS NULL THEN ''
            ELSE format('%I DESC NULLS LAST, ', item.availability_field)
        END;
        view_name := 'tushare_current_' || item.api_name;

        EXECUTE format(
            'CREATE OR REPLACE VIEW %I AS '
            || 'SELECT DISTINCT ON (%s) * FROM %I WHERE %s '
            || 'ORDER BY %s, %s_source_collected_at DESC, '
            || '_last_seen_at DESC, _record_hash DESC',
            view_name,
            identity_sql,
            'tushare_norm_' || item.api_name,
            required_sql,
            identity_sql,
            revision_order_sql
        );
        EXECUTE format(
            'COMMENT ON VIEW %I IS %L',
            view_name,
            'Latest trustworthy payload per contract-reviewed business identity; '
            || 'incomplete identities remain lossless in the version table'
        );
    END LOOP;
END $$;
