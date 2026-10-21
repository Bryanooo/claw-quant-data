-- A-share Fama-French three-factor daily returns, derived from already-governed
-- stock_daily, daily_basic (total market cap) and balancesheet (reported total
-- shareholder equity including minority interests). One row is written for every exchange trading day;
-- absence is explicit and auditable instead of silently dropping a session
-- where the cross-section is too thin to split.

-- Construction (Fama-French 1993, 2x3 sorts, value-weighted):
--   MKT = value-weighted all-A return minus the risk-free rate.
--   SMB = mean of the three small portfolios minus mean of the three big
--         portfolios, where size split is by the total-market-cap median.
--   HML = mean of the two high-B/M portfolios minus mean of the two low-B/M
--         portfolios, where B/M splits are by the 30th and 70th percentiles
--         of book-to-market (parent equity / total market cap).
-- Universe: all A-shares excluding ST and stocks listed fewer than 60 trading
-- days; a session with fewer than 20 eligible names is recorded with NULL
-- factor values and a non-ready status rather than fabricating a split.

CREATE TABLE IF NOT EXISTS fama_french_daily (
    trade_date                DATE PRIMARY KEY,
    mkt                       NUMERIC,
    smb                       NUMERIC,
    hml                       NUMERIC,
    risk_free                 NUMERIC,
    eligible_count            INTEGER NOT NULL DEFAULT 0,
    book_value_eligible_count INTEGER NOT NULL DEFAULT 0,
    small_count               INTEGER NOT NULL DEFAULT 0,
    big_count                 INTEGER NOT NULL DEFAULT 0,
    status                    VARCHAR(32) NOT NULL,
    formula_version           VARCHAR(64) NOT NULL,
    computed_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_execution_id       BIGINT,
    CONSTRAINT ck_fama_french_daily_counts CHECK (
        eligible_count >= 0 AND book_value_eligible_count >= 0
        AND small_count >= 0 AND big_count >= 0
    ),
    CONSTRAINT ck_fama_french_daily_status CHECK (
        status IN ('ready', 'insufficient_universe')
    ),
    CONSTRAINT ck_fama_french_daily_ready_values CHECK (
        status <> 'ready'
        OR (mkt IS NOT NULL AND smb IS NOT NULL AND hml IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_fama_french_daily_status
    ON fama_french_daily(status, trade_date DESC);

COMMENT ON TABLE fama_french_daily IS
    'V2 derived daily A-share Fama-French three-factor returns (MKT/SMB/HML), value-weighted 2x3 sorts';
COMMENT ON COLUMN fama_french_daily.mkt IS
    'Value-weighted all-A return minus risk-free rate, decimal (not percent)';
COMMENT ON COLUMN fama_french_daily.smb IS
    'Small-minus-big size premium, decimal; split by total market cap median';
COMMENT ON COLUMN fama_french_daily.hml IS
    'High-minus-low value premium, decimal; B/M splits at 30th/70th percentile';
COMMENT ON COLUMN fama_french_daily.risk_free IS
    'Daily risk-free rate used in MKT, decimal';
COMMENT ON COLUMN fama_french_daily.eligible_count IS
    'Number of eligible stocks in the cross-section for that session';
COMMENT ON COLUMN fama_french_daily.book_value_eligible_count IS
    'Eligible stocks with positive point-in-time book equity used by the six SMB/HML portfolios';
COMMENT ON COLUMN fama_french_daily.status IS
    'ready requires a non-thin cross-section; insufficient_universe keeps NULLs explicit';
COMMENT ON COLUMN fama_french_daily.formula_version IS
    'Versioned construction contract, e.g. ff3-a-share-v1';
