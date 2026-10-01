-- Independent V2 orchestration control plane.  The legacy sys_collection_*
-- tables remain untouched and continue to be the active runtime until an
-- explicit, separately audited engine switch.

CREATE SCHEMA IF NOT EXISTS orchestration_v2;

CREATE TABLE orchestration_v2.acquisition_endpoint (
    acquisition_endpoint_id BIGSERIAL PRIMARY KEY,
    source_id                VARCHAR(64) NOT NULL
                             REFERENCES public.sys_data_source(source_id),
    endpoint_key             VARCHAR(128) NOT NULL,
    version                  INTEGER NOT NULL,
    lifecycle_status         VARCHAR(16) NOT NULL DEFAULT 'draft',
    acquisition_mode         VARCHAR(32) NOT NULL,
    handler_key              VARCHAR(128) NOT NULL,
    credential_ref           TEXT,
    request_contract         JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_contract        JSONB NOT NULL DEFAULT '{}'::jsonb,
    pagination_policy        JSONB NOT NULL DEFAULT '{}'::jsonb,
    rate_limit_policy        JSONB NOT NULL DEFAULT '{}'::jsonb,
    completeness_policy      JSONB NOT NULL DEFAULT '{}'::jsonb,
    contract_digest          CHAR(64) NOT NULL,
    parent_endpoint_id       BIGINT REFERENCES orchestration_v2.acquisition_endpoint(
                                 acquisition_endpoint_id
                             ),
    created_by               TEXT NOT NULL,
    activated_by             TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at             TIMESTAMPTZ,
    retired_at               TIMESTAMPTZ,
    CONSTRAINT uq_orchestration_v2_endpoint_version
        UNIQUE (source_id, endpoint_key, version),
    CONSTRAINT ck_orchestration_v2_endpoint_key CHECK (
        endpoint_key ~ '^[A-Za-z][A-Za-z0-9_.:-]*$'
    ),
    CONSTRAINT ck_orchestration_v2_endpoint_version CHECK (version > 0),
    CONSTRAINT ck_orchestration_v2_endpoint_lifecycle CHECK (
        lifecycle_status IN ('draft', 'active', 'retired')
    ),
    CONSTRAINT ck_orchestration_v2_endpoint_mode CHECK (
        acquisition_mode IN (
            'scheduled_pull', 'web_snapshot', 'query_through', 'stream'
        )
    ),
    CONSTRAINT ck_orchestration_v2_endpoint_handler CHECK (
        handler_key ~ '^[a-z][a-z0-9_.:-]{2,127}$'
    ),
    CONSTRAINT ck_orchestration_v2_endpoint_contracts CHECK (
        jsonb_typeof(request_contract)='object'
        AND jsonb_typeof(response_contract)='object'
        AND jsonb_typeof(pagination_policy)='object'
        AND jsonb_typeof(rate_limit_policy)='object'
        AND jsonb_typeof(completeness_policy)='object'
    ),
    CONSTRAINT ck_orchestration_v2_endpoint_digest CHECK (
        contract_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_orchestration_v2_endpoint_lifecycle_time CHECK (
        (lifecycle_status='draft' AND activated_at IS NULL AND retired_at IS NULL)
        OR (lifecycle_status='active' AND activated_at IS NOT NULL AND retired_at IS NULL)
        OR (lifecycle_status='retired' AND activated_at IS NOT NULL AND retired_at IS NOT NULL)
    )
);
CREATE UNIQUE INDEX uq_orchestration_v2_endpoint_active
    ON orchestration_v2.acquisition_endpoint(source_id, endpoint_key)
    WHERE lifecycle_status='active';
CREATE INDEX idx_orchestration_v2_endpoint_handler
    ON orchestration_v2.acquisition_endpoint(handler_key, lifecycle_status);

CREATE TABLE orchestration_v2.task_definition (
    task_definition_id       BIGSERIAL PRIMARY KEY,
    task_key                 VARCHAR(128) NOT NULL,
    version                  INTEGER NOT NULL,
    lifecycle_status         VARCHAR(16) NOT NULL DEFAULT 'draft',
    workflow_kind            VARCHAR(24) NOT NULL,
    definition_schema_version INTEGER NOT NULL DEFAULT 1,
    definition               JSONB NOT NULL,
    definition_digest        CHAR(64) NOT NULL,
    parent_definition_id     BIGINT REFERENCES orchestration_v2.task_definition(
                                 task_definition_id
                             ),
    app_revision             TEXT,
    image_digest             TEXT,
    created_by               TEXT NOT NULL,
    activated_by             TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at             TIMESTAMPTZ,
    retired_at               TIMESTAMPTZ,
    CONSTRAINT uq_orchestration_v2_task_definition_version
        UNIQUE (task_key, version),
    CONSTRAINT ck_orchestration_v2_task_key CHECK (
        task_key ~ '^[a-z][a-z0-9_.:-]{2,127}$'
    ),
    CONSTRAINT ck_orchestration_v2_task_version CHECK (version > 0),
    CONSTRAINT ck_orchestration_v2_task_lifecycle CHECK (
        lifecycle_status IN ('draft', 'active', 'retired')
    ),
    CONSTRAINT ck_orchestration_v2_task_kind CHECK (
        workflow_kind IN ('acquisition', 'transformation')
    ),
    CONSTRAINT ck_orchestration_v2_task_schema_version CHECK (
        definition_schema_version > 0
    ),
    CONSTRAINT ck_orchestration_v2_task_definition CHECK (
        jsonb_typeof(definition)='object'
    ),
    CONSTRAINT ck_orchestration_v2_task_digest CHECK (
        definition_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_orchestration_v2_task_lifecycle_time CHECK (
        (lifecycle_status='draft' AND activated_at IS NULL AND retired_at IS NULL)
        OR (lifecycle_status='active' AND activated_at IS NOT NULL AND retired_at IS NULL)
        OR (lifecycle_status='retired' AND activated_at IS NOT NULL AND retired_at IS NOT NULL)
    )
);
CREATE UNIQUE INDEX uq_orchestration_v2_task_definition_active
    ON orchestration_v2.task_definition(task_key)
    WHERE lifecycle_status='active';
CREATE INDEX idx_orchestration_v2_task_definition_kind
    ON orchestration_v2.task_definition(workflow_kind, lifecycle_status, task_key);

CREATE TABLE orchestration_v2.task_execution (
    task_execution_id        BIGSERIAL PRIMARY KEY,
    task_definition_id       BIGINT NOT NULL
                             REFERENCES orchestration_v2.task_definition(
                                 task_definition_id
                             ),
    task_key                 VARCHAR(128) NOT NULL,
    definition_version       INTEGER NOT NULL,
    definition_digest        CHAR(64) NOT NULL,
    purpose                  VARCHAR(24) NOT NULL,
    trigger_source           VARCHAR(24) NOT NULL,
    status                   VARCHAR(32) NOT NULL DEFAULT 'created',
    idempotency_key          TEXT NOT NULL UNIQUE,
    observation_key         TEXT NOT NULL,
    observation_start       DATE,
    observation_end         DATE,
    observation_period      TEXT,
    publication_date        DATE,
    data_available_at       TIMESTAMPTZ,
    collected_at            TIMESTAMPTZ,
    frozen_scope            JSONB NOT NULL DEFAULT '{}'::jsonb,
    scope_digest            CHAR(64) NOT NULL,
    current_node_key        VARCHAR(128),
    node_status             JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority                SMALLINT NOT NULL DEFAULT 50,
    resource_class          VARCHAR(64) NOT NULL DEFAULT 'default',
    eligible_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempt_count           INTEGER NOT NULL DEFAULT 0,
    max_attempts            INTEGER NOT NULL DEFAULT 3,
    lease_owner             VARCHAR(128),
    lease_token             VARCHAR(128),
    lease_expires_at        TIMESTAMPTZ,
    app_revision            TEXT,
    image_digest            TEXT,
    final_error_category    VARCHAR(64),
    final_error_message     TEXT,
    final_error_detail      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at              TIMESTAMPTZ,
    finished_at             TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_orchestration_v2_execution_purpose CHECK (
        purpose IN (
            'daily', 'initialization', 'backfill', 'repair', 'manual', 'shadow'
        )
    ),
    CONSTRAINT ck_orchestration_v2_execution_trigger CHECK (
        trigger_source IN (
            'schedule', 'dependency', 'manual', 'recovery', 'migration', 'shadow'
        )
    ),
    CONSTRAINT ck_orchestration_v2_execution_status CHECK (
        status IN (
            'created', 'queued', 'running', 'waiting_dependency', 'retrying',
            'validating', 'publishing', 'success', 'attention', 'superseded',
            'cancelled'
        )
    ),
    CONSTRAINT ck_orchestration_v2_execution_dates CHECK (
        observation_start IS NULL OR observation_end IS NULL
        OR observation_start <= observation_end
    ),
    CONSTRAINT ck_orchestration_v2_execution_scope CHECK (
        jsonb_typeof(frozen_scope)='object'
        AND scope_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_orchestration_v2_execution_nodes CHECK (
        jsonb_typeof(node_status)='object'
    ),
    CONSTRAINT ck_orchestration_v2_execution_attempts CHECK (
        attempt_count >= 0 AND max_attempts > 0
        AND attempt_count <= max_attempts
    ),
    CONSTRAINT ck_orchestration_v2_execution_priority CHECK (
        priority BETWEEN 0 AND 100
    ),
    CONSTRAINT ck_orchestration_v2_execution_lease CHECK (
        (lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)
        OR (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
    ),
    CONSTRAINT ck_orchestration_v2_execution_terminal_time CHECK (
        status NOT IN ('success', 'attention', 'superseded', 'cancelled')
        OR finished_at IS NOT NULL
    )
);
CREATE INDEX idx_orchestration_v2_execution_claim
    ON orchestration_v2.task_execution(priority DESC, eligible_at, task_execution_id)
    WHERE status IN ('created', 'queued', 'retrying');
CREATE INDEX idx_orchestration_v2_execution_active_lease
    ON orchestration_v2.task_execution(lease_expires_at, resource_class)
    WHERE status IN ('running', 'validating', 'publishing');
CREATE INDEX idx_orchestration_v2_execution_task_time
    ON orchestration_v2.task_execution(task_key, created_at DESC, task_execution_id DESC);
CREATE INDEX idx_orchestration_v2_execution_observation
    ON orchestration_v2.task_execution(
        observation_start, observation_end, task_key, status
    );

CREATE TABLE orchestration_v2.task_execution_event (
    event_id                 BIGSERIAL PRIMARY KEY,
    task_execution_id       BIGINT NOT NULL
                             REFERENCES orchestration_v2.task_execution(
                                 task_execution_id
                             ) ON DELETE RESTRICT,
    sequence_number         INTEGER NOT NULL,
    event_type              VARCHAR(64) NOT NULL,
    node_key                VARCHAR(128),
    attempt_number          INTEGER,
    event_key               TEXT,
    payload                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_references     JSONB NOT NULL DEFAULT '[]'::jsonb,
    occurred_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_orchestration_v2_execution_event_sequence
        UNIQUE (task_execution_id, sequence_number),
    CONSTRAINT uq_orchestration_v2_execution_event_identity
        UNIQUE (event_id, task_execution_id),
    CONSTRAINT ck_orchestration_v2_execution_event_sequence CHECK (
        sequence_number > 0
    ),
    CONSTRAINT ck_orchestration_v2_execution_event_type CHECK (
        event_type ~ '^[a-z][a-z0-9_.-]{2,63}$'
    ),
    CONSTRAINT ck_orchestration_v2_execution_event_attempt CHECK (
        attempt_number IS NULL OR attempt_number > 0
    ),
    CONSTRAINT ck_orchestration_v2_execution_event_payload CHECK (
        jsonb_typeof(payload)='object'
        AND jsonb_typeof(evidence_references)='array'
    )
);
CREATE UNIQUE INDEX uq_orchestration_v2_execution_event_key
    ON orchestration_v2.task_execution_event(event_key)
    WHERE event_key IS NOT NULL;
CREATE INDEX idx_orchestration_v2_execution_event_execution
    ON orchestration_v2.task_execution_event(task_execution_id, sequence_number);
CREATE INDEX idx_orchestration_v2_execution_event_type_time
    ON orchestration_v2.task_execution_event(event_type, occurred_at, event_id);

CREATE TABLE orchestration_v2.dataset_state (
    dataset_state_id         BIGSERIAL PRIMARY KEY,
    dataset_name             VARCHAR(128) NOT NULL,
    observation_key         TEXT NOT NULL,
    observation_start       DATE,
    observation_end         DATE,
    observation_period      TEXT,
    publication_date        DATE,
    available_at            TIMESTAMPTZ,
    collected_at            TIMESTAMPTZ,
    scope                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    scope_digest            CHAR(64) NOT NULL,
    contract_version        VARCHAR(64) NOT NULL,
    expectation_status      VARCHAR(16) NOT NULL DEFAULT 'unknown',
    data_status             VARCHAR(24) NOT NULL DEFAULT 'pending',
    ready                    BOOLEAN NOT NULL DEFAULT FALSE,
    expected_count          BIGINT,
    actual_count            BIGINT,
    gap_summary             JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary      JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_execution_id     BIGINT REFERENCES orchestration_v2.task_execution(
                                 task_execution_id
                             ),
    validation_event_id     BIGINT,
    revision                INTEGER NOT NULL DEFAULT 1,
    published_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_orchestration_v2_dataset_state_scope UNIQUE (
        dataset_name, observation_key, scope_digest
    ),
    CONSTRAINT fk_orchestration_v2_dataset_validation_event FOREIGN KEY (
        validation_event_id, source_execution_id
    ) REFERENCES orchestration_v2.task_execution_event(
        event_id, task_execution_id
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_name CHECK (
        dataset_name ~ '^[a-z][a-z0-9_.:-]{1,127}$'
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_dates CHECK (
        observation_start IS NULL OR observation_end IS NULL
        OR observation_start <= observation_end
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_scope CHECK (
        jsonb_typeof(scope)='object'
        AND scope_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_expectation CHECK (
        expectation_status IN ('expected', 'not_expected', 'unknown')
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_status CHECK (
        data_status IN (
            'pending', 'auditing', 'complete', 'empty_verified', 'gaps',
            'partial', 'indeterminate'
        )
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_counts CHECK (
        (expected_count IS NULL OR expected_count >= 0)
        AND (actual_count IS NULL OR actual_count >= 0)
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_documents CHECK (
        jsonb_typeof(gap_summary)='object'
        AND jsonb_typeof(validation_summary)='object'
    ),
    CONSTRAINT ck_orchestration_v2_dataset_state_revision CHECK (revision > 0),
    CONSTRAINT ck_orchestration_v2_dataset_state_ready CHECK (
        NOT ready OR (
            expectation_status='expected'
            AND data_status IN ('complete', 'empty_verified')
            AND published_at IS NOT NULL
            AND source_execution_id IS NOT NULL
            AND validation_event_id IS NOT NULL
        )
    )
);
CREATE INDEX idx_orchestration_v2_dataset_state_calendar
    ON orchestration_v2.dataset_state(
        observation_start, observation_end, data_status, dataset_name
    );
CREATE INDEX idx_orchestration_v2_dataset_state_attention
    ON orchestration_v2.dataset_state(updated_at DESC, dataset_name)
    WHERE data_status IN ('gaps', 'partial', 'indeterminate');
CREATE INDEX idx_orchestration_v2_dataset_state_ready
    ON orchestration_v2.dataset_state(dataset_name, observation_key, updated_at DESC)
    WHERE ready;

-- Published task/endpoint versions and execution facts are immutable.  A
-- draft can be edited or deleted; an active version can only be retired.
CREATE OR REPLACE FUNCTION orchestration_v2.guard_versioned_definition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        IF OLD.lifecycle_status <> 'draft' THEN
            RAISE EXCEPTION 'published orchestration definitions are immutable';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.lifecycle_status='draft' THEN
        IF NEW.lifecycle_status NOT IN ('draft', 'active') THEN
            RAISE EXCEPTION 'draft definitions may only remain draft or become active';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.lifecycle_status='active'
       AND NEW.lifecycle_status='retired'
       AND NEW.retired_at IS NOT NULL THEN
        IF to_jsonb(NEW) - ARRAY['lifecycle_status','retired_at','updated_at']
           IS DISTINCT FROM
           to_jsonb(OLD) - ARRAY['lifecycle_status','retired_at','updated_at'] THEN
            RAISE EXCEPTION 'retiring a definition cannot change its contract';
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'published orchestration definitions are immutable';
END;
$$;

CREATE TRIGGER trg_orchestration_v2_endpoint_immutable
BEFORE UPDATE OR DELETE ON orchestration_v2.acquisition_endpoint
FOR EACH ROW EXECUTE FUNCTION orchestration_v2.guard_versioned_definition();

CREATE TRIGGER trg_orchestration_v2_task_definition_immutable
BEFORE UPDATE OR DELETE ON orchestration_v2.task_definition
FOR EACH ROW EXECUTE FUNCTION orchestration_v2.guard_versioned_definition();

CREATE OR REPLACE FUNCTION orchestration_v2.reject_execution_event_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'task execution events are append-only';
END;
$$;

CREATE TRIGGER trg_orchestration_v2_execution_event_append_only
BEFORE UPDATE OR DELETE ON orchestration_v2.task_execution_event
FOR EACH ROW EXECUTE FUNCTION orchestration_v2.reject_execution_event_mutation();

COMMENT ON SCHEMA orchestration_v2 IS
    'Independent V2 task control plane; not the active engine until an audited deployment switch.';
COMMENT ON TABLE orchestration_v2.task_definition IS
    'One immutable row per logical task version; drafts are editable and at most one version per task can be active.';
COMMENT ON TABLE orchestration_v2.acquisition_endpoint IS
    'Versioned declarative endpoint contract. handler_key resolves only through the application allow-list; executable code is never stored here.';
COMMENT ON TABLE orchestration_v2.task_execution IS
    'Current state and frozen scope for one logical run. Pagination and partitions remain within its node execution.';
COMMENT ON TABLE orchestration_v2.task_execution_event IS
    'Append-only execution facts, node attempts, checkpoints, validation evidence and outbox events.';
COMMENT ON TABLE orchestration_v2.dataset_state IS
    'Authoritative data readiness by observation period and scope; independent of task success.';
