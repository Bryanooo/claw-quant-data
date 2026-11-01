CREATE TABLE IF NOT EXISTS valuation_percentile_snapshot (
    trade_date date PRIMARY KEY,
    formula_version text NOT NULL,
    audit_status text NOT NULL CHECK (audit_status IN ('ready','partial')),
    snapshots jsonb NOT NULL,
    source_execution_id bigint,
    computed_at timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(snapshots) = 'object'),
    CHECK (audit_status <> 'ready' OR
           (snapshots ? '000300.SH' AND snapshots ? '000688.SH'))
);
COMMENT ON TABLE valuation_percentile_snapshot IS
    'Code-owned two-index valuation distribution; partial diagnostics are not certified coverage';
