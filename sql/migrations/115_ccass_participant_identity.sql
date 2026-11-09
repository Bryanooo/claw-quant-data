-- Some real CCASS rows identify the participant by name, with no provider ID.
SET LOCAL lock_timeout = '3s';
ALTER TABLE ccass_hold_detail ADD COLUMN participant_key text;
UPDATE ccass_hold_detail SET participant_key='id:' || col_participant_id;
ALTER TABLE ccass_hold_detail DROP CONSTRAINT ccass_hold_detail_pkey;
ALTER TABLE ccass_hold_detail ALTER COLUMN col_participant_id DROP NOT NULL,
    ADD PRIMARY KEY(ts_code,trade_date,participant_key);
