-- Backup snapshots prove observation, never original announcement-time availability.
SET LOCAL lock_timeout = '5s';
CREATE TABLE financial_backup_source (
    sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    file_name text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    archive_created_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    verified_at timestamptz NOT NULL DEFAULT now(),
    available_on date NOT NULL,
    CHECK (completed_at >= archive_created_at),
    CHECK (available_on > (completed_at AT TIME ZONE 'Asia/Shanghai')::date)
);
CREATE TABLE financial_backup_row (
    backup_sha256 text NOT NULL REFERENCES financial_backup_source(sha256),
    statement_table text NOT NULL CHECK (statement_table IN
        ('income','balancesheet','cashflow','fina_indicator')),
    fingerprint bytea NOT NULL,
    original_row jsonb NOT NULL,
    PRIMARY KEY (backup_sha256, statement_table, fingerprint)
);
COMMENT ON TABLE financial_backup_row IS
    'Retained original backup payload and exact typed revision link. No overwrite of supplier latest tables.';
