# `ft_limit` — 期货合约涨跌停价格（盘前）

- 分类：期货数据
- 功能：获取所有期货合约每天的涨跌停价格及最低保证金率，数据开始于2005年。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积5000积分可调取，积分获取方法具体请参阅 积分获取办法
- 官方文档：[doc 368](https://tushare.pro/document/2?doc_id=368)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 合约代码 |
| `trade_date` | str | N | 交易日期（格式：YYYYMMDD） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `cont` | str | N | 合约代码（例如：cont='CU') |
| `exchange` | str | N | 交易所代码 （例如：exchange='DCE') |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | TS股票代码 |
| `name` | str | Y | 合约名称 |
| `up_limit` | float | Y | 涨停价 |
| `down_limit` | float | Y | 跌停价 |
| `m_ratio` | float | Y | 最低交易保证金率（%） |
| `cont` | str | Y | 合约代码 |
| `exchange` | str | Y | 交易所代码 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "ft_limit",
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

#获取单日全部期货合约涨跌停价格
df = pro.ft_limit(trade_date='20250213')

#获取单个品种所有合约涨跌停价格
df = pro.ft_limit(cont='CU')
```

## 实际返回示例（官方文档）

```text
trade_date     ts_code     name      up_limit down_limit m_ratio cont exchange
0     20250213   A2503.DCE  连豆一2503   4229.000   3751.000   7.000    A      DCE
1     20250213   A2505.DCE  连豆一2505   4249.000   3769.000   7.000    A      DCE
2     20250213   A2507.DCE  连豆一2507   4258.000   3776.000   7.000    A      DCE
3     20250213   A2509.DCE  连豆一2509   4268.000   3786.000   7.000    A      DCE
4     20250213   A2511.DCE  连豆一2511   4234.000   3756.000   7.000    A      DCE
..         ...         ...      ...        ...        ...     ...  ...      ...
783   20250213  ZN2509.SHF   沪锌2509  24890.000  21635.000   9.000   ZN     SHFE
784   20250213  ZN2510.SHF   沪锌2510  24885.000  21630.000   9.000   ZN     SHFE
785   20250213  ZN2511.SHF   沪锌2511  24780.000  21535.000   9.000   ZN     SHFE
786   20250213  ZN2512.SHF   沪锌2512  24700.000  21465.000   9.000   ZN     SHFE
787   20250213  ZN2601.SHF   沪锌2601  24710.000  21475.000   9.000   ZN     SHFE
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_ft_limit`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/ft_limit.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
