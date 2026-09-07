-- The coordinator has seven phases (0..6). Migration 032 introduced the
-- fan-out phase but accidentally capped the state machine at phase 5, making
-- the final independent coverage verification unreachable.
ALTER TABLE sys_collection_initialization
    DROP CONSTRAINT ck_collection_initialization_phase;

ALTER TABLE sys_collection_initialization
    ADD CONSTRAINT ck_collection_initialization_phase
    CHECK (current_phase BETWEEN 0 AND 6);

COMMENT ON COLUMN sys_collection_initialization.current_phase IS
    'Initialization phase index: 0 foundation through 6 coverage verification';
