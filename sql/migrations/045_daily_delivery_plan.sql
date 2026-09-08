-- Durable business-day delivery expectations for the operator dashboard.
-- A plan is deliberately separate from execution jobs: if the scheduler fails
-- before creating a job, the missing delivery remains visible and auditable.
CREATE TABLE IF NOT EXISTS sys_collection_delivery_plan (
    delivery_plan_id BIGSERIAL PRIMARY KEY,
    business_date    DATE NOT NULL,
    plan_key         VARCHAR(160) NOT NULL,
    source_type      VARCHAR(16) NOT NULL,
    source_key       VARCHAR(128) NOT NULL,
    api_name         VARCHAR(64) NOT NULL,
    title            TEXT NOT NULL,
    cadence          VARCHAR(16) NOT NULL,
    scheduled_for    TIMESTAMPTZ NOT NULL,
    due_at           TIMESTAMPTZ NOT NULL,
    expected_for     DATE,
    period_key       VARCHAR(32),
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_collection_delivery_plan UNIQUE (business_date, plan_key),
    CONSTRAINT ck_collection_delivery_source
        CHECK (source_type IN ('dedicated', 'policy', 'fanout')),
    CONSTRAINT ck_collection_delivery_window CHECK (due_at >= scheduled_for)
);

CREATE INDEX IF NOT EXISTS idx_collection_delivery_plan_day
    ON sys_collection_delivery_plan(business_date, scheduled_for, source_type);

COMMENT ON TABLE sys_collection_delivery_plan IS
    'Expected routine data deliveries for one Shanghai business date';
COMMENT ON COLUMN sys_collection_delivery_plan.business_date IS
    'Dashboard operating date, distinct from the upstream data partition date';
