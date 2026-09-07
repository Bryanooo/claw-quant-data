# `etf_sh_cons` — ETF每日持仓组合(沪市）

- 分类：ETF专题
- 功能：获取上交所场内所有ETF每日盘前披露的的一篮子组合信息,包括成分股票数量、申赎现金折溢价比例等数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要8000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 471](https://tushare.pro/document/2?doc_id=471)
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
| `sub_flag` | str | Y | 现金替代标志：允许/必须 |
| `cpr` | float | Y | 申购现金替代溢价比率（%） |
| `rdr` | float | Y | 赎回现金替代折价比率（%） |
| `sca` | float | Y | 替代金额(单位：人民币元) |
| `exchange` | str | Y | 交易所代码HK港交所 SH上交所 SZ深交所 OTH其他 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "etf_sh_cons",
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

# 获取517030易方达中证沪港深300ETF在2026年6月15日的持仓组合信息
df = pro.etf_sh_cons(trade_date='20260615', ts_code='517030.SH')
print(df)
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code   con_code con_name   qty sub_flag cpr rdr        sca exchange
0     20260615  517030.SH  000001.SZ     平安银行  1100       允许  15  60  12364.000       SZ
1     20260615  517030.SH   00001.HK       长和     0       必须   -   -      0.000       HK
2     20260615  517030.SH   00002.HK     中电控股     0       必须   -   -      0.000       HK
3     20260615  517030.SH   00003.HK   香港中华煤气  1000       允许  30   0   5928.350       HK
4     20260615  517030.SH   00005.HK     汇丰控股   800       允许  30   0  99304.260       HK
..         ...        ...        ...      ...   ...      ...  ..  ..        ...      ...
295   20260615  517030.SH  688256.SH      寒武纪     0       必须   -   -      0.000       SH
296   20260615  517030.SH  688271.SH     联影医疗     0       必须   -   -      0.000       SH
297   20260615  517030.SH  688506.SH     百利天恒     0       必须   -   -      0.000       SH
298   20260615  517030.SH  688521.SH     芯原股份     0       必须   -   -      0.000       SH
299   20260615  517030.SH  688981.SH     中芯国际   200       允许  73   0          -       SH
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_etf_sh_cons`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/etf_sh_cons.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
