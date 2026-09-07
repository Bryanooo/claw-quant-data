# `etf_index` — ETF基准指数列表

- 分类：ETF专题
- 功能：获取ETF基准指数列表信息
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累8000积分可调取，具体请参阅 积分获取办法
- 官方文档：[doc 386](https://tushare.pro/document/2?doc_id=386)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 指数代码 |
| `pub_date` | str | N | 发布日期（格式：YYYYMMDD） |
| `base_date` | str | N | 指数基期（格式：YYYYMMDD） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `indx_name` | str | Y | 指数全称 |
| `indx_csname` | str | Y | 指数简称 |
| `pub_party_name` | str | Y | 指数发布机构 |
| `pub_date` | str | Y | 指数发布日期 |
| `base_date` | str | Y | 指数基日 |
| `bp` | float | Y | 指数基点(点) |
| `adj_circle` | str | Y | 指数成份证券调整周期 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "etf_index",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "510300.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取当前ETF跟踪的基准指数列表
df = pro.etf_index(fields='ts_code,indx_name,pub_date,bp')
```

## 实际返回示例（官方文档）

```text
ts_code        indx_name         pub_date           bp
0        000068.SH         上证自然资源指数  20100528  1000.000000
1        000001.SH           上证综合指数  19910715   100.000000
2        000989.SH       中证全指可选消费指数  20110802  1000.000000
3       000990.CSI       中证全指主要消费指数  20110802  1000.000000
4        000043.SH         上证超级大盘指数  20090423  1000.000000
...            ...              ...       ...          ...
1458    932368.CSI     中证800自由现金流指数  20241211  1000.000000
1460     000680.SH        上证科创板综合指数  20250120  1000.000000
1461     000681.SH      上证科创板综合价格指数  20250120  1000.000000
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_etf_index`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/etf_index.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
