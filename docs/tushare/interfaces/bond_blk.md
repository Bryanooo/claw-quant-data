# `bond_blk` — 债券大宗交易

- 分类：债券专题
- 功能：获取沪深交易所债券大宗交易数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户满5000积分有数据权限，单次最大1000条，可根据日期循环提取，总量不限制
- 官方文档：[doc 271](https://tushare.pro/document/2?doc_id=271)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 债券代码 |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 债券代码 |
| `name` | str | Y | 债券名称 |
| `price` | float | Y | 成交价（元） |
| `vol` | float | Y | 累计成交数量（万股/万份/万张/万手） |
| `amount` | float | Y | 累计成交金额（万元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "bond_blk",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.bond_blk(start_date='20210701', end_date='20210930')
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code    name     price    vol    amount
0     20210930  152497.SH   20黔西南   75.00  35.00  2625.00
1     20210930  152497.SH   20黔西南   75.00  20.00  1500.00
2     20210930  152497.SH   20黔西南   75.00  19.20  1440.00
3     20210930  152497.SH   20黔西南   75.00  18.00  1350.00
4     20210930  152497.SH   20黔西南   75.00  17.00  1275.00
..         ...        ...     ...     ...    ...      ...
995   20210917  136225.SZ   21奥创A   99.98   6.50   649.90
996   20210917  133073.SZ  21经开02   99.34  10.00   993.40
997   20210917  133068.SZ  21九江01  100.18  50.00  5009.05
998   20210917  133063.SZ  21新沂04  100.56   6.47   650.63
999   20210917  133050.SZ  21江滨01  100.25  50.00  5012.50
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_bond_blk`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/bond_blk.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
