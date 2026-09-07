-- Allow a bounded, resumable all-history initialization profile.
ALTER TABLE sys_collection_initialization
    DROP CONSTRAINT ck_collection_initialization_profile;

ALTER TABLE sys_collection_initialization
    ADD CONSTRAINT ck_collection_initialization_profile
    CHECK (profile IN ('quick', 'standard', 'research', 'full'));
