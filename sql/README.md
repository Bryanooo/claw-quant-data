# claw-quant-data 数据库建表脚本

所有建表语句统一存放于此，方便 review 和系统迁移。

## 文件组织

- `init_schema.sql`：系统配置和股票基础资料
- `init_daily.sql`：A 股日线行情
- `init_tushare_raw.sql`：契约驱动通用采集器的幂等 JSONB 原始记录
- `init_tushare_checkpoint.sql`：通用采集器分页进度与断点恢复状态
- `init_data_coverage.sql`：日期覆盖审计队列、审计结果和分区状态
- 其他 `init_*.sql`：按财务、指数、资金流、板块等领域拆分的业务表
- `migrations/`：已有数据卷的有序增量迁移

`init_collector_run.sql`、`init_collection_job.sql` 和旧版覆盖外键仅用于让全新数据库
依次重放不可变的历史迁移；迁移 `077_drop_legacy_v1_control_plane.sql` 会在任何服务
启动前删除这些临时兼容对象。生产运行时、REST、Scheduler、Worker 和最终数据库均不
依赖 V1。历史迁移文件不可删除或改写，否则已有安装将无法校验和升级。

## 用法

```bash
# 全量初始化；脚本彼此独立，可按文件名顺序执行
for file in sql/init_*.sql; do
  psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$file"
done
python scripts/migrate.py
```

使用 `docker compose up` 时，PostgreSQL 会在首次创建数据卷时自动运行以上
所有脚本；随后一次性 `migrate` 服务会在 API、Scheduler、两个 V2 Worker、Auditor
启动前自动补齐已有数据卷的增量迁移。

## 迁移注意事项

- `init_*.sql` 只定义新数据库的最终结构
- 已有数据卷必须通过 `scripts/migrate.py` 升级
- 迁移按三位数字前缀排序，并记录版本、SHA-256 校验和和应用时间
- 已应用迁移不得修改；结构变更必须新增迁移文件
- `migrations/checksums.sha256` 固化所有已发布迁移的文件校验和；迁移程序会在
  连接数据库前校验文件集合和内容，CI 也会阻止漏登记、新增后未更新清单或
  格式化工具改写历史文件
- 新增迁移后必须执行
  `shasum -a 256 sql/migrations/[0-9][0-9][0-9]_*.sql > sql/migrations/checksums.sha256`
  并一并提交；不要对已有迁移执行去尾空白、换行符转换等批量格式化
- 迁移在单事务和 PostgreSQL advisory lock 内执行
- 主键/唯一约束确保幂等性（配合 UPSERT 写入）
- `tushare_norm_*` 保留所有不同 payload 版本；经过接口契约复核的数据集通过
  `tushare_current_*` 只读视图提供当前版本，身份字段不完整的行保持逐行可见
- `orchestration_v2.task_definition` 同时保存草稿、历史版本和唯一生效版本。
- `orchestration_v2.task_execution` 保存不可变范围、节点游标、租约、重试预算和最终错误。
- `orchestration_v2.task_execution_event` 保存节点与状态变更审计轨迹。
- `orchestration_v2.dataset_state` 保存数据日期/报告期的严格审计结果，供数据日历展示。
- `orchestration_v2.acquisition_endpoint` 保存采集端点元数据与处理器引用，不保存或动态
  执行任意代码。
- `sys_data_coverage_*` 是 V2 初始化、历史诊断和修复验收复用的独立严格审计队列。
- REST Dataset Registry 与覆盖审计使用的核心分区日期统一为 `DATE`；尚未进入
  数据服务的历史扩展表会随规范化建模逐步迁移，时区相关字段使用
  `TIMESTAMP WITH TIME ZONE`
