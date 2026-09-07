# `slb_sec_detail` — 转融券交易明细

- 分类：股票数据/两融及转融通
- 功能：转融券交易明细
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分每分钟请求200次，5000积分500次请求
- 官方文档：[doc 333](https://tushare.pro/document/2?doc_id=333)
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
| `tenor` | str | Y | 期 限(天) |
| `fee_rate` | float | Y | 融出费率(%) |
| `lent_qnt` | float | Y | 转融券融出数量(万股) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "slb_sec_detail",
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

df = pro.slb_sec_detail(trade_date='20240620')
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code   name     tenor fee_rate lent_qnt
0     20240620  000001.SZ   平安银行    14     2.20     1.43
1     20240620  000002.SZ    万科Ａ    14     4.60     2.27
2     20240620  000009.SZ   中国宝安    14     7.10     0.66
3     20240620  000016.SZ   深康佳Ａ    14     1.40     9.68
4     20240620  000031.SZ    大悦城    14     3.80     0.22
..         ...        ...    ...   ...      ...      ...
932   20240620  688789.SH   宏华数科    14     1.40     0.84
933   20240620  688798.SH  XD艾为电    14     1.40     1.32
934   20240620  688819.SH   天能股份    14     2.10     0.74
935   20240620  688981.SH   中芯国际    14     3.10     0.10
936   20240620  689009.SH   九号公司    14     1.40     5.72
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_slb_sec_detail`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/slb_sec_detail.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
