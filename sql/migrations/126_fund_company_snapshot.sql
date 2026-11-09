-- Pin the exact rows in a complete fund directory response. Preserve all
-- normalized historical records and the legacy projection until the first
-- complete directory has been published.
CREATE TABLE fund_company_snapshot_membership (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    requested_at timestamptz NOT NULL,
    record_hashes text[] NOT NULL CHECK (cardinality(record_hashes) > 0)
);
DO $$
DECLARE old_query text;
BEGIN
    old_query := rtrim(pg_get_viewdef('tushare_current_fund_company'::regclass), E'; \n');
    EXECUTE 'CREATE OR REPLACE VIEW tushare_current_fund_company AS
        SELECT n.* FROM fund_company_snapshot_membership m
        CROSS JOIN LATERAL unnest(m.record_hashes) h(hash)
        JOIN tushare_norm_fund_company n ON n._record_hash=h.hash
        UNION ALL SELECT legacy.* FROM (' || old_query || ') legacy
        WHERE NOT EXISTS (SELECT 1 FROM fund_company_snapshot_membership)';
END $$;
