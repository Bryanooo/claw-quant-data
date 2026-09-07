-- kpl_list.net_change and bid_change are monetary amounts, not percentages.

ALTER TABLE kpl_list
    ALTER COLUMN net_change TYPE NUMERIC(18,2),
    ALTER COLUMN bid_change TYPE NUMERIC(18,2);

COMMENT ON COLUMN kpl_list.net_change IS '主力净额(元)';
COMMENT ON COLUMN kpl_list.bid_change IS '竞价净额(元)';
