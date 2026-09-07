-- limit_cpt_list.up_stat contains values such as “12天7板”.  VARCHAR(4)
-- accepted many ordinary days but rejected valid multi-digit durations.
ALTER TABLE limit_cpt_list
    ALTER COLUMN up_stat TYPE VARCHAR(32);
