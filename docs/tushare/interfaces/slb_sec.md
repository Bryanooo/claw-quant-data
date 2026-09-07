# `slb_sec` — 转融券交易汇总

- 分类：股票数据/两融及转融通
- 功能：转融通转融券交易汇总
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分每分钟请求200次，5000积分500次请求
- 官方文档：[doc 332](https://tushare.pro/document/2?doc_id=332)
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
| `lent_qnt` | float | Y | 转融券融出数量(万股) |
| `cls_inv` | float | Y | 期末余量(万股) |
| `end_bal` | float | Y | 期末余额(万元) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "slb_sec",
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

df = pro.slb_sec(trade_date='20240620')
```

## 实际返回示例（官方文档）

```text
trade_date   ts_code   name  ope_inv lent_qnt  cls_inv   end_bal
0      20240620  000001.SZ   平安银行   186.97     1.43   188.40   2004.70
1      20240620  000002.SZ    万科Ａ  3456.26     3.18  3376.80  24346.73
2      20240620  000006.SZ   深振业Ａ    17.08     None    17.08     64.56
3      20240620  000008.SZ   神州高铁    17.07     None    17.07     33.97
4      20240620  000009.SZ   中国宝安   315.61     0.66   310.56   2822.99
...         ...        ...    ...      ...      ...      ...       ...
2249   20240620  688798.SH  XD艾为电    65.35     1.32    63.40   3727.91
2250   20240620  688800.SH    瑞可达     6.49     None     6.36    191.18
2251   20240620  688819.SH   天能股份   108.34     1.05   108.44   2717.34
2252   20240620  688981.SH   中芯国际   303.00    22.45   315.30  15386.64
2253   20240620  689009.SH   九号公司   259.35     5.72   253.62  10583.56
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_slb_sec`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/slb_sec.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
