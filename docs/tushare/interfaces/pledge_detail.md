# `pledge_detail` — 股权质押明细

- 分类：股票数据/参考数据
- 功能：获取股票质押明细数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 111](https://tushare.pro/document/2?doc_id=111)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/reference/pledge_detail.py](../../../collectors/stock/reference/pledge_detail.py)、[collectors/stock/reference/pledge_detail.py:PledgeDetailCollector](../../../collectors/stock/reference/pledge_detail.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `ann_date` | str | N | 公告日期 |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS股票代码 |
| `ann_date` | str | Y | 公告日期 |
| `holder_name` | str | Y | 股东名称 |
| `pledge_amount` | float | Y | 质押数量（万股） |
| `start_date` | str | Y | 质押开始日期 |
| `end_date` | str | Y | 质押结束日期 |
| `is_release` | str | Y | 是否已解押 |
| `release_date` | str | Y | 解押日期 |
| `pledgor` | str | Y | 质押方 |
| `holding_amount` | float | Y | 持股总数（万股） |
| `pledged_amount` | float | Y | 质押总数（万股） |
| `p_total_ratio` | float | Y | 本次质押占总股本比例 |
| `h_total_ratio` | float | Y | 持股总数占总股本比例 |
| `is_buyback` | str | Y | 是否回购（0否 1是） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "pledge_detail",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()
#或者
#pro = ts.pro_api('your token')


df = pro.pledge_detail(ts_code='000014.SZ')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date         holder_name          pledge_amount start_date  \
0  000014.SZ  20180106  中科汇通(深圳)股权投资基金有限公司       500.0000   20171114
1  000014.SZ  20180106  中科汇通(深圳)股权投资基金有限公司       922.0055   20171114
2  000014.SZ  20171221  中科汇通(深圳)股权投资基金有限公司       600.0000   20171114
3  000014.SZ  20171216  中科汇通(深圳)股权投资基金有限公司       300.0000   20171114
4  000014.SZ  20171111  中科汇通(深圳)股权投资基金有限公司       2321.9955   20151127
5  000014.SZ  20170616  中科汇通(深圳)股权投资基金有限公司       0.0100   20151127
6  000014.SZ  20060927  深圳市沙河实业(集团)有限公司             1936.3698   20050119
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
