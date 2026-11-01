-- Widen the interface registry key constraint to admit route-style keys.
--
-- Financial Data interfaces use HTTP route paths (``/api/v1/...``) as their
-- key, which the original ``^[A-Za-z]`` prefix rejected.  Keys may now start
-- with a slash while still forbidding control characters and whitespace.

ALTER TABLE orchestration_v2.interface_registry
    DROP CONSTRAINT IF EXISTS ck_orchestration_v2_interface_registry_key;

ALTER TABLE orchestration_v2.interface_registry
    ADD CONSTRAINT ck_orchestration_v2_interface_registry_key CHECK (
        interface_key ~ '^[A-Za-z0-9/:_.-]{1,128}$'
    );
