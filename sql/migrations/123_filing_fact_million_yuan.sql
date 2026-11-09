-- Preserve the printed reporting unit on large issuers' consolidated reports.
SET LOCAL lock_timeout = '5s';
ALTER TABLE financial_filing_fact DROP CONSTRAINT financial_filing_fact_original_unit_check,
    ADD CONSTRAINT financial_filing_fact_original_unit_check
        CHECK (original_unit IN ('人民币元','人民币千元','人民币万元','人民币百万元'));
