-- A provider comparison cannot fail before the provider has published the
-- reference partition.  Keep that operational state distinct from a genuine
-- formula mismatch or an insufficient overlap sample.
SET LOCAL lock_timeout='5s';

ALTER TABLE local_factor_validation
    DROP CONSTRAINT ck_local_factor_validation_status;

ALTER TABLE local_factor_validation
    ADD CONSTRAINT ck_local_factor_validation_status CHECK (
        validation_status IN (
            'matched', 'correlated', 'review_required', 'not_comparable',
            'provider_pending'
        )
    );

COMMENT ON COLUMN local_factor_validation.validation_status IS
    'provider_pending means local calculation completed before the independent provider reference partition was published';
