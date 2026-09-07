#!/usr/bin/env python3
import json
import os

import tushare as ts

token = os.getenv("TUSHARE_TOKEN", "").strip()
if not token:
    raise SystemExit("TUSHARE_TOKEN is required")

ts.set_token(token)
pro = ts.pro_api()

# API to query with field definitions
apis = {
    'index_basic': lambda: pro.index_basic(),
    'index_daily': lambda: pro.index_daily(ts_code='000001.SH', trade_date='20260514'),
    'index_weekly': lambda: pro.index_weekly(ts_code='000001.SH', trade_date='20260508'),
    'index_monthly': lambda: pro.index_monthly(ts_code='000001.SH', trade_date='20260514'),
    'index_dailybasic': lambda: pro.index_dailybasic(ts_code='000001.SH', trade_date='20260514'),
    'index_global': lambda: pro.index_global(ts_code='DJI', trade_date='20260514'),
}

for name, func in apis.items():
    print(f"\n{'='*80}")
    print(f"API: {name}")
    print(f"{'='*80}")
    try:
        df = func()
        print(f"Columns ({len(df.columns)}): {list(df.columns)}")
        print(f"Dtypes: {dict(df.dtypes)}")
        if len(df) > 0:
            print(f"Sample data (first row):")
            print(df.head(1).to_string())
        else:
            print("No data returned (empty DataFrame)")
    except Exception as e:
        print(f"ERROR: {e}")
