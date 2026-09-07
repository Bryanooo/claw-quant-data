-- Safe current-state read views for contract-reviewed versioned datasets.
-- Complete logical identities are reduced to their latest payload. Rows with
-- any missing identity dimension remain visible individually and are never
-- collapsed. The lossless normalized base tables are unchanged.

DO $$
DECLARE
    item RECORD;
    identity_sql TEXT;
    complete_sql TEXT;
    view_name TEXT;
    index_name TEXT;
BEGIN
    FOR item IN
        SELECT * FROM (VALUES
            ('bc_otcqt', ARRAY['trade_date', 'qt_time', 'bank', 'ts_code']),
            ('cb_basic', ARRAY['ts_code']),
            ('cb_daily', ARRAY['trade_date', 'ts_code']),
            ('cb_rate', ARRAY['ts_code', 'rate_start_date', 'rate_end_date']),
            ('cb_rating', ARRAY['ts_code', 'rating_date', 'rating_com_name', 'rating_type']),
            ('cn_schedule', ARRAY['month', 'publish_date', 'title']),
            ('daily_basic', ARRAY['trade_date', 'ts_code']),
            ('etf_sh_cons', ARRAY['trade_date', 'ts_code', 'con_code']),
            ('etf_share_size', ARRAY['trade_date', 'ts_code']),
            ('etf_sz_cons', ARRAY['trade_date', 'ts_code', 'con_code']),
            ('fund_company', ARRAY['name']),
            ('fund_manager', ARRAY['ts_code', 'name', 'begin_date']),
            ('fund_share', ARRAY['trade_date', 'ts_code']),
            ('fut_basic', ARRAY['ts_code']),
            ('fut_daily', ARRAY['trade_date', 'ts_code']),
            ('fut_holding', ARRAY['trade_date', 'symbol', 'broker']),
            ('fut_settle', ARRAY['trade_date', 'ts_code']),
            ('fut_weekly_detail', ARRAY['week', 'exchange', 'prd']),
            ('fut_wsr', ARRAY['trade_date', 'symbol', 'warehouse', 'wh_id', 'grade', 'brand', 'place']),
            ('limit_list_ths', ARRAY['trade_date', 'ts_code']),
            ('shibor_quote', ARRAY['date', 'bank']),
            ('us_basic', ARRAY['ts_code'])
        ) AS reviewed(api_name, identity_fields)
    LOOP
        SELECT string_agg(format('%I', field_name), ', '),
               string_agg(format('%I IS NOT NULL', field_name), ' AND ')
        INTO identity_sql, complete_sql
        FROM unnest(item.identity_fields) AS field_name;

        view_name := 'tushare_current_' || item.api_name;
        index_name := 'idx_tushare_norm_' || item.api_name || '_business_identity';

        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS %I ON %I (%s, _source_collected_at DESC, _last_seen_at DESC)',
            index_name,
            'tushare_norm_' || item.api_name,
            identity_sql
        );
        EXECUTE format(
            'CREATE OR REPLACE VIEW %I AS '
            || '(SELECT DISTINCT ON (%s) * FROM %I WHERE %s '
            || 'ORDER BY %s, _source_collected_at DESC, _last_seen_at DESC, _record_hash DESC) '
            || 'UNION ALL SELECT * FROM %I WHERE NOT (%s)',
            view_name,
            identity_sql,
            'tushare_norm_' || item.api_name,
            complete_sql,
            identity_sql,
            'tushare_norm_' || item.api_name,
            complete_sql
        );
        EXECUTE format(
            'COMMENT ON VIEW %I IS %L',
            view_name,
            'Latest payload per contract-reviewed business identity; incomplete identities remain lossless'
        );
    END LOOP;
END $$;
