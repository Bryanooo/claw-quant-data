# claw-quant-data 数据库建表脚本

所有建表语句统一存放于此，方便 review 和系统迁移。

## 文件组织

- `init_schema.sql`：系统配置和股票基础资料
- `init_daily.sql`：A 股日线行情
- `init_collector_run.sql`：采集任务运行记录
- `init_tushare_raw.sql`：契约驱动通用采集器的幂等 JSONB 原始记录
- `init_tushare_checkpoint.sql`：通用采集器分页进度与断点恢复状态
- `init_collection_job.sql`：持久化采集任务队列、Worker 租约和专项计划派发游标
- `init_data_coverage.sql`：日期覆盖审计队列、审计结果和分区状态
- 其他 `init_*.sql`：按财务、指数、资金流、板块等领域拆分的业务表
- `init_zz_specialized_contract_alignment.sql`：将新库对齐到最新专项接口字段契约
- `migrations/`：已有数据卷的有序增量迁移

## 用法

```bash
# 全量初始化；脚本彼此独立，可按文件名顺序执行
for file in sql/init_*.sql; do
  psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$file"
done
python scripts/migrate.py
```

使用 `docker compose up` 时，PostgreSQL 会在首次创建数据卷时自动运行以上
所有脚本；随后一次性 `migrate` 服务会在 API、Scheduler、三个 Worker、Auditor
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
- `sys_collection_job` 保存接口周期、获取/写入行数和 JSONB 完整性证据
- `sys_collection_job` 同时固化逻辑处理器与版本，并通过可续租的
  `lease_expires_at` 防止 Worker 崩溃后任务永久停在 `running`
- `sys_collection_job.recheck_*` 将延迟发布导致的空结果复查保存为独立任务链；
  唯一约束保证同一个空任务至多派生一个下一代复查，原始执行记录不会被覆盖
- `sys_collection_job.priority/resource_class` 同时提供池内优先级和硬资源路由；
  日常、周期扇出、初始化/回填由三个互斥 Worker 池消费
- `sys_collection_schedule_cursor` 保存专项计划最后一次成功派发时间，供 Scheduler
  重启后幂等补发
- `sys_data_coverage_*` 保存独立审计任务、日期/报告期覆盖和缺失分区；支持通过
  `collection_job_id` 将审计结果反写到原始采集任务
- `sys_collection_initialization*` 保存首次/重新初始化活动、阶段步骤和验收历史；
  `sys_collection_runtime_state` 是日常调度的单例运行模式门控
- `sys_collection_fanout_campaign*` 保存跨多个有界父子批次的全量活动、周期、
  已规划/已验证游标和分页证据；`sys_collection_fanout_campaign_entity` 保存不可变
  有序依赖宇宙快照，Scheduler 可在进程重启或实时清单变化后继续同一份计划
- 全历史初始化按数据集可靠起点和每轮 500 个步骤分批规划，避免数万历史任务在
  单次 Scheduler 调用中同时建表记录
- REST Dataset Registry 与覆盖审计使用的核心分区日期统一为 `DATE`；尚未进入
  数据服务的历史扩展表会随规范化建模逐步迁移，时区相关字段使用
  `TIMESTAMP WITH TIME ZONE`
