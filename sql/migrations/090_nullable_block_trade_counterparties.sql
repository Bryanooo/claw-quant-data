-- Historical bond block trades can omit broker counterparties. Preserve the
-- unknown values as NULL while retaining idempotent natural-key upserts.
ALTER TABLE block_trade
    ADD COLUMN IF NOT EXISTS block_trade_id BIGSERIAL;

ALTER TABLE block_trade
    DROP CONSTRAINT IF EXISTS block_trade_pkey;

ALTER TABLE block_trade
    DROP CONSTRAINT IF EXISTS uq_block_trade_natural_key;

ALTER TABLE block_trade
    ALTER COLUMN buyer DROP NOT NULL,
    ALTER COLUMN seller DROP NOT NULL;

ALTER TABLE block_trade
    ADD CONSTRAINT block_trade_pkey PRIMARY KEY (block_trade_id);

ALTER TABLE block_trade
    ADD CONSTRAINT uq_block_trade_natural_key
    UNIQUE NULLS NOT DISTINCT (ts_code, trade_date, price, buyer, seller);
