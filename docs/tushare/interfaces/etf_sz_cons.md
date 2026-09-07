# `etf_sz_cons` — ETF每日持仓组合(深市）

- 分类：ETF专题
- 功能：获取深交所场内所有ETF每日盘前披露的一篮子组合信息,包括成分股票数量、申赎现金折溢价比例等数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要8000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 472](https://tushare.pro/document/2?doc_id=472)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 板块代码 |
| `trade_date` | str | N | 交易日期(YYYYMMDD) |
| `con_code` | str | N | 成分股票代码 |
| `start_date` | str | N | 开始日期(YYYYMMDD) |
| `end_date` | str | N | 结束日期(YYYYMMDD) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | ETF代码 |
| `con_code` | str | Y | 成分代码 |
| `con_name` | str | Y | 成分名称 |
| `qty` | int | Y | 股票数量(股) |
| `sub_flag` | str | Y | 现金替代标志 |
| `cpr` | float | Y | 申购现金替代保证金率（%） |
| `rdr` | float | Y | 赎回现金替代保证金率（%） |
| `sub_cc` | float | Y | 申购替代金额(单位：人民币元) |
| `red_cc` | float | Y | 赎回替代金额(单位：人民币元) |
| `exchange` | str | Y | 交易所代码HK港交所 SH上交所 SZ深交所 OTH其他 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "etf_sz_cons",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 获取接口实例
pro = ts.pro_api()

# 拉取159051.SZ易方达中证全指医疗器械ETF在2026年6月25日的持仓组合数据
df = pro.etf_sz_cons(ts_code='159051.SZ', trade_date='20260625')
print(df)
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code   con_code con_name   qty sub_flag    cpr   rdr       sub_cc       red_cc exchange
0   20260625  159051.SZ  159900.SZ     申赎现金     0       必须   0.00  0.00  512407.5000  141173.9000       SZ
1   20260625  159051.SZ  000710.SZ     贝瑞基因   400       允许  34.00  0.00       0.0000       0.0000       SZ
2   20260625  159051.SZ  002022.SZ     科华生物   800       允许  34.00  0.00       0.0000       0.0000       SZ
3   20260625  159051.SZ  002030.SZ     达安基因  1500       允许  34.00  0.00       0.0000       0.0000       SZ
4   20260625  159051.SZ  002223.SZ     鱼跃医疗   900       允许  34.00  0.00       0.0000       0.0000       SZ
5   20260625  159051.SZ  002382.SZ     蓝帆医疗  1200       允许  34.00  0.00       0.0000       0.0000       SZ
6   20260625  159051.SZ  002432.SZ     九安医疗   500       允许  34.00  0.00       0.0000       0.0000       SZ
7   20260625  159051.SZ  002551.SZ     尚荣医疗   900       允许  34.00  0.00       0.0000       0.0000       SZ
8   20260625  159051.SZ  002901.SZ     大博医疗   100       允许  34.00  0.00       0.0000       0.0000       SZ
9   20260625  159051.SZ  002950.SZ     奥美医疗   400       允许  34.00  0.00       0.0000       0.0000       SZ
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_etf_sz_cons`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/etf_sz_cons.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
