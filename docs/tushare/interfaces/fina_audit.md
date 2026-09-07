# `fina_audit` — 财务审计意见

- 分类：股票数据/财务数据
- 功能：获取上市公司定期财务审计意见数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 80](https://tushare.pro/document/2?doc_id=80)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `ann_date` | str | N | 公告日期 |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |
| `period` | str | N | 报告期(每个季度最后一天的日期,比如20171231表示年报) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | TS股票代码 |  |
| `ann_date` | str | 公告日期 |  |
| `end_date` | str | 报告期 |  |
| `audit_result` | str | 审计结果 |  |
| `audit_fees` | float | 审计总费用（元） |  |
| `audit_agency` | str | 会计事务所 |  |
| `audit_sign` | str | 签字会计师 |  |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fina_audit",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.fina_audit(ts_code='600000.SH', start_date='20100101', end_date='20180808')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date  end_date        audit_result  audit_agency                audit_sign
0  600000.SH  20180428  20171231      标准无保留意见  普华永道中天会计师事务所      周章,张武
1  600000.SH  20170401  20161231      标准无保留意见  普华永道中天会计师事务所      周章,张武
2  600000.SH  20160407  20151231      标准无保留意见  普华永道中天会计师事务所      胡亮,张武
3  600000.SH  20150319  20141231      标准无保留意见  普华永道中天会计师事务所      胡亮,张武
4  600000.SH  20140320  20131231      标准无保留意见  普华永道中天会计师事务所      胡亮,周章
5  600000.SH  20130314  20121231      标准无保留意见  普华永道中天会计师事务所      胡亮,周章
6  600000.SH  20120316  20111231      标准无保留意见  普华永道中天会计师事务所      胡亮,周章
7  600000.SH  20110330  20101231      标准无保留意见    安永华明会计师事务所    严盛炜,周明骏
8  600000.SH  20100830  20100630      标准无保留意见    安永华明会计师事务所    严盛炜,周明骏
9  600000.SH  20100407  20091231      标准无保留意见    安永华明会计师事务所    严盛炜,周明骏
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fina_audit`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fina_audit.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
