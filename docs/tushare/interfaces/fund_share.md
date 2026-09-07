# `fund_share` — 基金规模数据

- 分类：公募基金
- 功能：获取基金规模数据，包含上海和深圳ETF基金
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分可以调取，5000积分以上频次较高，具体请参阅 积分获取办法
- 官方文档：[doc 207](https://tushare.pro/document/2?doc_id=207)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS基金代码 |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `market` | str | N | 市场代码（SH上交所 ，SZ深交所） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 基金代码，支持多只基金同时提取，用逗号分隔 |
| `trade_date` | str | Y | 交易（变动）日期，格式YYYYMMDD |
| `fd_share` | float | Y | 基金份额（万） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_share",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#初始接口
pro = ts.pro_api()

#单只基金
df = pro.fund_share(ts_code='150018.SZ')

#多只基金
df = pro.fund_share(ts_code='150018.SZ,150008.SZ')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date  fd_share
0     150018.SZ   20200214  206733.2898
1     150018.SZ   20200213  209274.0911
2     150018.SZ   20200212  211859.8666
3     150018.SZ   20200211  215224.2959
4     150018.SZ   20200210  216739.3881
...         ...        ...          ...
1995  150018.SZ   20111129  319525.0658
1996  150018.SZ   20111128  317324.2829
1997  150018.SZ   20111125  317324.2131
1998  150018.SZ   20111124  316113.2233
1999  150018.SZ   20111123  314305.3576
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_share`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_share.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

完整采集按标准 `limit`/`offset` 分页到响应不足一页，并持久化 checkpoint。虽然
官方参数表未列出分页字段，实测同一交易日可连续返回多个 2000 行页面，因此单页
2000 行不能判为完成。2026-06-30 的恢复验证共耗尽 26 页、25,998 行。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
