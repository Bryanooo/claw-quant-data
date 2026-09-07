# `fx_obasic` — 外汇基础信息（海外）

- 分类：外汇数据
- 功能：获取海外外汇基础信息，目前只有FXCM交易商的数据 数量：单次可提取全部数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 178](https://tushare.pro/document/2?doc_id=178)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/forex/fx_obasic.py:FxObasicCollector](../../../collectors/forex/fx_obasic.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `exchange` | str | N | 交易商 |
| `classify` | str | N | 分类 |
| `ts_code` | str | N | TS代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 外汇代码 |
| `name` | str | Y | 名称 |
| `classify` | str | Y | 分类 |
| `exchange` | str | Y | 交易商 |
| `min_unit` | float | Y | 最小交易单位 |
| `max_unit` | float | Y | 最大交易单位 |
| `pip` | float | Y | 点 |
| `pip_cost` | float | Y | 点值 |
| `traget_spread` | float | Y | 目标差价 |
| `min_stop_distance` | float | Y | 最小止损距离（点子） |
| `trading_hours` | str | Y | 交易时间 |
| `break_time` | str | Y | 休市时间 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fx_obasic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "EURUSD.FXCM"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取差价合约(CFD)中指数产的基础信息
df = pro.fx_obasic(exchange='FXCM', classify='INDEX', fields='ts_code,name,min_unit,max_unit,pip,pip_cost')
```

## 实际返回示例（官方文档）

```text
ts_code                  name     min_unit  max_unit  pip  pip_cost
0    AUS200.FXCM  澳大利亚标准普尔200指数       1.0    2000.0  1.0       0.1
1     CHN50.FXCM      富时中国A50指数       1.0     100.0  1.0       0.1
2     ESP35.FXCM    西班牙IBEX35指数       1.0    5000.0  1.0       0.1
3   EUSTX50.FXCM      欧洲斯托克50指数       1.0    5000.0  1.0       0.1
4     FRA40.FXCM      法国CAC40指数       1.0    5000.0  1.0       0.1
5     GER30.FXCM        德国DAX指数       1.0    1000.0  1.0       0.1
6     HKG33.FXCM         香港恒生指数       1.0     300.0  1.0       1.0
7    JPN225.FXCM        日经225指数      10.0    1000.0  1.0      10.0
8    NAS100.FXCM    美国纳斯达克100指数       1.0    5000.0  1.0       0.1
9    SPX500.FXCM      美国标普500指数       1.0    5000.0  0.1       0.1
10    UK100.FXCM      英国富时100指数       1.0    4000.0  1.0       0.1
11     US30.FXCM      道琼斯工业平均指数       1.0    4000.0  1.0       0.1
12   US2000.FXCM     美国罗素2000指数       1.0    5000.0  0.1       0.1
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
