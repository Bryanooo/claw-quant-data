-- Real upstream ranking explanations can exceed 512 characters. Preserve the
-- complete explanation instead of truncating or failing the collection task.
ALTER TABLE ths_hot
    ALTER COLUMN rank_reason TYPE TEXT
    USING rank_reason::text;
