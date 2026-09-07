# `slb_len_mm` — 做市借券交易汇总

- 分类：股票数据/两融及转融通
- 功能：做市借券交易汇总
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分每分钟请求200次，5000积分500次请求
- 官方文档：[doc 334](https://tushare.pro/document/2?doc_id=334)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `ts_code` | str | N | 股票代码 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期（YYYYMMDD） |
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `ope_inv` | float | Y | 期初余量(万股) |
| `lent_qnt` | float | Y | 融出数量(万股) |
| `cls_inv` | float | Y | 期末余量(万股) |
| `end_bal` | float | Y | 期末余额(万元) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "slb_len_mm",
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

df = pro.slb_len_mm(trade_date='20240620')
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code   name     ope_inv lent_qnt cls_inv  end_bal
0     20240620  688002.SH   睿创微纳   18.49     None   18.49   558.21
1     20240620  688005.SH   容百科技   12.24     None   12.24   309.06
2     20240620  688006.SH   杭可科技    6.92     None    6.92   129.89
3     20240620  688007.SH   光峰科技    9.66     None    9.66   167.99
4     20240620  688008.SH   澜起科技   38.13     None   38.13  2138.33
..         ...        ...    ...     ...      ...     ...      ...
126   20240620  688789.SH   宏华数科    1.49     None    1.49   155.14
127   20240620  688798.SH  XD艾为电    3.41     None    3.41   200.54
128   20240620  688819.SH   天能股份   15.77     None   15.77   395.51
129   20240620  688981.SH   中芯国际   57.08     None   57.08  2785.50
130   20240620  689009.SH   九号公司   12.84     None   12.84   535.81
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_slb_len_mm`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/slb_len_mm.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
