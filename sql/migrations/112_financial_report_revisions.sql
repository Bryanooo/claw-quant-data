-- Preserve typed financial payloads. Current tables remain the public latest-value
-- relations. Their created_at is an insert timestamp, not proof of revision age.
SET LOCAL lock_timeout = '5s';

CREATE FUNCTION archive_financial_batch(base_name text, source_table regclass, seed boolean)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    archive_name text := base_name || '_revision';
    kind text := CASE WHEN base_name='fina_indicator' THEN '0' ELSE 's.report_type' END;
    disclosure text := CASE WHEN base_name='fina_indicator' THEN 's.ann_date'
                            ELSE 'greatest(s.f_ann_date, s.ann_date)' END;
    dated text := CASE WHEN base_name='fina_indicator' THEN 'false'
                       ELSE $expr$s.f_ann_date IS NOT NULL AND
                            (s.update_flag='0' OR s.f_ann_date > s.ann_date)$expr$ END;
    keys text := CASE WHEN base_name='fina_indicator' THEN 'ts_code,end_date'
                      ELSE 'ts_code,end_date,report_type' END;
    columns_sql text;
    updates_sql text;
BEGIN
    IF base_name NOT IN ('income','balancesheet','cashflow','fina_indicator') THEN
        RAISE EXCEPTION 'unsupported financial statement table %', base_name;
    END IF;
    -- Concurrent backfills for the same table must agree about first observation.
    PERFORM pg_advisory_xact_lock(hashtext('finance_revision'), hashtext(base_name));
    EXECUTE format($q$
        WITH incoming AS MATERIALIZED (
            SELECT DISTINCT ON (fingerprint) s AS source_row, s.ts_code, s.end_date,
                   %3$s AS kind, %4$s AS published_on, (%5$s) AS dated,
                   fingerprint, (SELECT count(*) FROM jsonb_each(jsonb_strip_nulls(j.data))) AS populated
            FROM %2$s s
            CROSS JOIN LATERAL (SELECT to_jsonb(s) - 'created_at' AS data) j
            CROSS JOIN LATERAL (SELECT sha256(convert_to(j.data::text,'UTF8')) AS fingerprint) h
        ), variants AS (
            SELECT *, count(*) OVER (PARTITION BY ts_code,end_date,kind,published_on) AS variants
            FROM incoming
        )
        INSERT INTO %1$I (row_data, ts_code, end_date, kind, published_on, available_on,
                          fingerprint, populated)
        SELECT ROW((v.source_row).*)::%6$I, ts_code,end_date,kind,published_on,
               CASE WHEN dated AND variants=1 AND NOT EXISTS (
                         SELECT 1 FROM %1$I prev WHERE prev.ts_code=v.ts_code
                           AND prev.end_date=v.end_date AND prev.kind=v.kind
                           AND prev.published_on=v.published_on)
                    THEN published_on
                    ELSE greatest(published_on, (statement_timestamp() AT TIME ZONE 'Asia/Shanghai')::date)
               END, fingerprint, populated
        FROM variants v ON CONFLICT (fingerprint) DO NOTHING
    $q$, archive_name, source_table, kind, disclosure, dated, base_name);
    IF seed THEN RETURN; END IF;

    SELECT string_agg(format('%I',attname),',' ORDER BY attnum),
           string_agg(format('%1$I=EXCLUDED.%1$I',attname),',' ORDER BY attnum)
               FILTER (WHERE attname <> ALL(string_to_array(keys,',')))
      INTO columns_sql, updates_sql FROM pg_attribute
      WHERE attrelid=base_name::regclass AND attnum>0 AND NOT attisdropped AND attname<>'created_at';
    EXECUTE format($q$
        WITH affected AS (SELECT DISTINCT s.ts_code,s.end_date,%3$s AS kind FROM %2$s s),
        winners AS (
            SELECT DISTINCT ON (r.ts_code,r.end_date,r.kind) (r.row_data).*
            FROM %1$I r JOIN affected USING(ts_code,end_date,kind)
            ORDER BY r.ts_code,r.end_date,r.kind,r.published_on DESC NULLS LAST,
                     (r.row_data).update_flag DESC NULLS LAST, r.first_seen_at DESC,
                     r.populated DESC, r.fingerprint
        )
        INSERT INTO %4$I AS current (%5$s) SELECT %5$s FROM winners
        ON CONFLICT (%6$s) DO UPDATE SET %7$s
        WHERE (to_jsonb(current)-'created_at') IS DISTINCT FROM (to_jsonb(EXCLUDED)-'created_at')
    $q$, archive_name, source_table, kind, base_name, columns_sql, keys, updates_sql);
END
$$;

DO $$
DECLARE
    t text;
    archive_name text;
    type_filter text;
BEGIN
    FOREACH t IN ARRAY ARRAY['income','balancesheet','cashflow','fina_indicator'] LOOP
        archive_name := t || '_revision';
        EXECUTE format('LOCK TABLE %I IN SHARE ROW EXCLUSIVE MODE',t);
        EXECUTE format('CREATE TABLE %I (
            row_data %I NOT NULL, ts_code varchar(32) NOT NULL, end_date date NOT NULL,
            kind integer NOT NULL, published_on date, available_on date NOT NULL,
            first_seen_at timestamptz NOT NULL DEFAULT statement_timestamp(),
            populated integer NOT NULL, fingerprint bytea PRIMARY KEY)',archive_name,t);
        EXECUTE format('CREATE INDEX ON %I (ts_code,end_date,kind,published_on DESC)', archive_name);
        PERFORM archive_financial_batch(t,t::regclass,true);
        type_filter := CASE WHEN t='fina_indicator' THEN 'true'
             ELSE 'CASE WHEN requested_type IS NULL THEN all_types OR kind IN (1,4,5) ELSE kind=requested_type END' END;
        EXECUTE format($f$
            CREATE FUNCTION %1$I(cutoff date, symbols text[] DEFAULT NULL,
                               period_from date DEFAULT NULL, period_to date DEFAULT NULL,
                               requested_type integer DEFAULT NULL, all_types boolean DEFAULT false)
            RETURNS SETOF %2$I LANGUAGE sql STABLE PARALLEL SAFE AS $fn$
                SELECT (chosen.row_data).* FROM (
                    SELECT DISTINCT ON (ts_code,end_date,CASE WHEN all_types THEN kind ELSE 0 END) row_data FROM %3$I
                    WHERE available_on <= cutoff AND %4$s
                      AND (symbols IS NULL OR ts_code=ANY(symbols))
                      AND (period_from IS NULL OR end_date>=period_from)
                      AND (period_to IS NULL OR end_date<=period_to)
                    ORDER BY ts_code,end_date,CASE WHEN all_types THEN kind ELSE 0 END,
                             published_on DESC NULLS LAST,kind ASC,
                             (row_data).update_flag DESC NULLS LAST,first_seen_at DESC,
                             populated DESC,fingerprint
                ) chosen
            $fn$
        $f$, t || '_as_of',t,archive_name,type_filter);
    END LOOP;
END
$$;
