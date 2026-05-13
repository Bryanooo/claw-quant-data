# claw-quant-data 数据库建表脚本

所有建表语句统一存放于此，方便 review 和系统迁移。

## 文件列表

| 文件 | 用途 | 包含的表 |
|---|---|---|
| `init_schema.sql` | 业务表建表 | sys_config, stock_basic, trade_cal, stock_st, st_risk_warning, stock_hsgt, namechange, stock_company, stk_managers, stk_rewards, bse_mapping, new_share, bak_basic |
| `init_collector_run.sql` | 任务运行记录表 | sys_collector_run |
| `init_stk_limit.sql` | 每日涨跌停价格表 | stk_limit |
| `init_suspend_d.sql` | 每日停复牌信息表 | suspend_d |
| `init_connect.sql` | 沪深港通/港股通表 | hsgt_top10, ggt_top10, ggt_daily, ggt_monthly |
| `init_stk_weekly_monthly.sql` | 周/月线行情表 | stk_weekly_monthly |

## 用法

```bash
# 先建业务表
psql -h 127.0.0.1 -U tushare -d tushare_db -f sql/init_schema.sql

# 再建运行记录表
psql -h 127.0.0.1 -U tushare -d tushare_db -f sql/init_collector_run.sql
```

## 迁移注意事项

- 所有表使用 `IF NOT EXISTS`，可重复执行，不会覆盖已有数据
- 主键/唯一约束确保幂等性（配合 UPSERT 写入）
- 日期字段统一使用 `DATE` 类型（非 `VARCHAR`），时区相关使用 `TIMESTAMP WITH TIME ZONE`
