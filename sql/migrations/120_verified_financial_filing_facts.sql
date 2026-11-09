-- Field-level evidence from reviewed original filings, never vendor row rewrites.
SET LOCAL lock_timeout = '5s';
CREATE TABLE financial_filing_fact (
    fact_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    artifact_id bigint NOT NULL REFERENCES source_raw_artifact(artifact_id),
    artifact_sha256 char(64) NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    statement_table text NOT NULL CHECK (statement_table IN ('income','balancesheet','cashflow')),
    ts_code varchar(32) NOT NULL,
    end_date date NOT NULL,
    published_on date NOT NULL CHECK (published_on >= end_date),
    -- Publication time is unknown: never assume a release before that day's close.
    available_on date GENERATED ALWAYS AS (published_on + 1) STORED,
    field_name text NOT NULL CHECK (field_name ~ '^[a-z][a-z0-9_]+$'),
    value_yuan numeric(28,4) NOT NULL CHECK (value_yuan::text NOT IN ('NaN','Infinity','-Infinity')),
    page_number integer NOT NULL CHECK (page_number > 0),
    row_label text NOT NULL,
    original_unit text NOT NULL CHECK (original_unit IN ('人民币元','人民币千元','人民币万元')),
    scope text NOT NULL DEFAULT 'consolidated' CHECK (scope='consolidated'),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    reviewed_by text NOT NULL CHECK (length(btrim(reviewed_by))>0),
    reviewed_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    UNIQUE(artifact_id,statement_table,ts_code,end_date,field_name)
);
CREATE INDEX idx_financial_filing_fact_lookup ON financial_filing_fact
    (statement_table,ts_code,end_date,published_on DESC) WHERE revoked_at IS NULL;
COMMENT ON TABLE financial_filing_fact IS
    'Reviewed exact fields with original artifact and publication evidence. Not a complete statement, vendor overwrite, or global factor acceptance.';
