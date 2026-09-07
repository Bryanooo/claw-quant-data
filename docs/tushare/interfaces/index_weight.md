# `index_weight` — 指数成分和权重

- 分类：指数专题
- 功能：获取各类指数成分和权重， 月度数据 ，建议输入参数里开始日期和结束日分别输入当月第一天和最后一天的日期。 来源：指数公司网站公开数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 96](https://tushare.pro/document/2?doc_id=96)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `index_code` | str | Y | 指数代码，来源 指数基础信息接口 |
| `trade_date` | str | N | 交易日期（格式YYYYMMDD，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | None | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `index_code` | str | Y | 指数代码 |
| `con_code` | str | Y | 成分代码 |
| `trade_date` | str | Y | 交易日期 |
| `weight` | float | Y | 权重 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "index_weight",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "index_code": "000001.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#提取沪深300指数2018年9月成分和权重
df = pro.index_weight(index_code='399300.SZ', start_date='20180901', end_date='20180930')
```

## 实际返回示例（官方文档）

```text
index_code   con_code trade_date  weight
0    399300.SZ  000001.SZ   20180903  0.8656
1    399300.SZ  000002.SZ   20180903  1.1330
2    399300.SZ  000060.SZ   20180903  0.1125
3    399300.SZ  000063.SZ   20180903  0.4273
4    399300.SZ  000069.SZ   20180903  0.2010
5    399300.SZ  000157.SZ   20180903  0.1699
6    399300.SZ  000402.SZ   20180903  0.0816
7    399300.SZ  000413.SZ   20180903  0.2023
8    399300.SZ  000415.SZ   20180903  0.0648
9    399300.SZ  000423.SZ   20180903  0.2100
10   399300.SZ  000425.SZ   20180903  0.1884
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_index_weight`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/index_weight.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
