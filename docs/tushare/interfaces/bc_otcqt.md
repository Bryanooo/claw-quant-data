# `bc_otcqt` — 柜台流通式债券报价

- 分类：债券专题
- 功能：柜台流通式债券报价
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少500积分可以试用调取，2000积分以上频次相对较高，积分越多权限越大，具体请参阅 积分获取办法
- 官方文档：[doc 322](https://tushare.pro/document/2?doc_id=322)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期(YYYYMMDD格式，下同) |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `ts_code` | str | N | TS代码 |
| `bank` | str | N | 报价机构 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 报价日期 |
| `qt_time` | str | N | 报价时间 |
| `bank` | str | N | 报价机构 |
| `ts_code` | str | N | 债券编码 |
| `name` | str | N | 债券简称 |
| `maturity` | str | N | 期限 |
| `remain_maturity` | str | N | 剩余期限 |
| `bond_type` | str | N | 债券类型 |
| `coupon_rate` | float | N | 票面利率（%） |
| `buy_price` | float | N | 投资者买入全价 |
| `sell_price` | float | N | 投资者卖出全价 |
| `buy_yield` | float | N | 投资者买入到期收益率（%） |
| `sell_yield` | float | N | 投资者卖出到期收益率（%） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "bc_otcqt",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api(your token)
#柜台流通式债券报价
df = pro.bc_otcqt(start_date='20240325',end_date='20240329',ts_code='200013.BC',fields='trade_date,qt_time,bank,ts_code,name,remain_maturity,buy_yield,sell_yield')
```

## 实际返回示例（官方文档）

```text
trade_date   qt_time  bank    ts_code      name remain_maturity buy_yield sell_yield
0   20240329  08:11:02  浦发银行  200013.BC  20附息国债13          1年207天    1.9263     1.7977
1   20240329  09:05:28  招商银行  200013.BC  20附息国债13          1年207天    1.8950     1.8350
2   20240329  09:10:24  工商银行  200013.BC  20附息国债13          1年207天    1.8850     1.8528
3   20240329  09:14:48  建设银行  200013.BC  20附息国债13          1年207天    1.8837     1.8451
4   20240329  09:18:18  中国银行  200013.BC  20附息国债13          1年207天    1.9040     1.8200
5   20240329  10:40:09  北京银行  200013.BC  20附息国债13          1年207天    1.9043     1.8271
6   20240329  15:46:38  农业银行  200013.BC  20附息国债13          1年207天    1.8697     1.8054
7   20240329  18:36:29  交通银行  200013.BC  20附息国债13          1年207天    1.8464     1.8142
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_bc_otcqt`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/bc_otcqt.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
