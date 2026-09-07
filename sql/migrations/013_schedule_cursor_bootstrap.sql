-- Allow a cursor to be seeded at deployment without replaying unknown work.

ALTER TABLE sys_collection_schedule_cursor
    ALTER COLUMN last_job_id DROP NOT NULL;

COMMENT ON COLUMN sys_collection_schedule_cursor.last_job_id IS
    'Latest durable job, or NULL when the cursor was safely bootstrapped';
