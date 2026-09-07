# `fund_nav` — 公募基金净值

- 分类：公募基金
- 功能：获取公募基金净值数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 119](https://tushare.pro/document/2?doc_id=119)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS基金代码 （二选一） |
| `nav_date` | str | N | 净值日期 （二选一） |
| `market` | str | N | E场内 O场外 |
| `start_date` | str | N | 净值开始日期 |
| `end_date` | str | N | 净值结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `ann_date` | str | Y | 公告日期 |
| `nav_date` | str | Y | 净值日期 |
| `unit_nav` | float | Y | 单位净值 |
| `accum_nav` | float | Y | 累计净值 |
| `accum_div` | float | Y | 累计分红 |
| `net_asset` | float | Y | 资产净值 |
| `total_netasset` | float | N | 合计资产净值 |
| `adj_nav` | float | Y | 复权单位净值 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_nav",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "510300.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.fund_nav(ts_code='165509.SZ')


#指定输出字段
df = pro.fund_nav(ts_code='165509.SZ', fields='ts_code,ann_date,total_netasset')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date  nav_date  unit_nav  accum_nav accum_div  \
0     165509.SZ  20181019  20181018     1.104      1.587      None
1     165509.SZ  20181018  20181017     1.110      1.587      None
2     165509.SZ  20181017  20181016     1.110      1.587      None
3     165509.SZ  20181016  20181015     1.110      1.587      None
4     165509.SZ  20181013  20181012     1.110      1.587      None
5     165509.SZ  20181012  20181011     1.110      1.587      None
6     165509.SZ  20181011  20181010     1.110      1.587      None
7     165509.SZ  20181010  20181009     1.110      1.587      None
8     165509.SZ  20181009  20181008     1.109      1.586      None
9     165509.SZ  20180929  20180928     1.109      1.586      None
10    165509.SZ  20180928  20180927     1.109      1.586      None
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_nav`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_nav.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
