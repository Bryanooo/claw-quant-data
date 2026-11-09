-- Real provider names (including romanized names) exceed 32 characters.
-- Keep the original identity in the primary key; never truncate to fit.
SET LOCAL lock_timeout = '3s';
ALTER TABLE public.stk_rewards
    ALTER COLUMN name TYPE text,
    ALTER COLUMN title TYPE text;
