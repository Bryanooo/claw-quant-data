# `etf_share_size` — ETF份额规模

- 分类：ETF专题
- 功能：获取沪深ETF每日份额和规模数据，能体现规模份额的变化，掌握ETF资金动向，同时提供每日净值和收盘价；数据指标是分批入库，交易所于次日早8点30左右更新上一交易日的数据；另外，涉及海外的ETF数据更新会晚一些属于正常情况。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要8000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 408](https://tushare.pro/document/2?doc_id=408)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 基金代码 （可从ETF基础信息接口提取） |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `exchange` | str | N | 交易所（SSE上交所 SZSE深交所） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | ETF代码 |
| `etf_name` | str | Y | 基金名称 |
| `total_share` | float | Y | 总份额（万份） |
| `total_size` | float | Y | 总规模（万元） |
| `nav` | float | N | 基金份额净值(元) |
| `close` | float | N | 收盘价（元） |
| `exchange` | str | Y | 交易所（SSE上交所 SZSE深交所 BSE北交所） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "etf_share_size",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取”沪深300ETF华夏”ETF2025年以来每个交易日的份额和规模情况
df = pro.etf_share_size(ts_code='510330.SH', start_date='20250101', end_date='20251224')

#获取2025年12月24日上交所的所有ETF份额和规模情况
df = pro.etf_share_size(trade_date='20251224', exchange='SSE')
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code       etf_name  total_share    total_size exchange
0     20251224  510330.SH  沪深300ETF华夏   4741854.98  2.287898e+07      SSE
1     20251222  510330.SH  沪深300ETF华夏   4746894.98  2.279127e+07      SSE
2     20251219  510330.SH  沪深300ETF华夏   4756974.98  2.262512e+07      SSE
3     20251218  510330.SH  沪深300ETF华夏   4757514.98  2.253778e+07      SSE
4     20251217  510330.SH  沪深300ETF华夏   4756884.98  2.266418e+07      SSE
..         ...        ...         ...          ...           ...      ...
232   20250108  510330.SH  沪深300ETF华夏   4032384.98  1.599808e+07      SSE
233   20250107  510330.SH  沪深300ETF华夏   4009164.98  1.592962e+07      SSE
234   20250106  510330.SH  沪深300ETF华夏   3999084.98  1.577239e+07      SSE
235   20250103  510330.SH  沪深300ETF华夏   3994674.98  1.578176e+07      SSE
236   20250102  510330.SH  沪深300ETF华夏   3986754.98  1.593905e+07      SSE
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_etf_share_size`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/etf_share_size.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
