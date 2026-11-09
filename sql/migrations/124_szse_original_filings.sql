-- Original exchange disclosures archived for point-in-time financial evidence.
INSERT INTO sys_data_source
    (source_id, display_name, source_kind, acquisition_modes, base_url, timezone)
VALUES ('szse', '深圳证券交易所上市公司公告', 'website', ARRAY['web_snapshot'],
        'https://www.szse.cn/disclosure/listed/notice/', 'Asia/Shanghai')
ON CONFLICT (source_id) DO NOTHING;
