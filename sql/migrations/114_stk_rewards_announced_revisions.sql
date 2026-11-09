-- Preserve rather than overwrite later announcements of the same report.
SET LOCAL lock_timeout = '3s';
ALTER TABLE public.stk_rewards DROP CONSTRAINT stk_rewards_pkey,
    ADD PRIMARY KEY (ts_code, name, end_date, ann_date);
