# `dc_hot` — DC热榜

- 分类：股票数据/打板专题数据
- 功能：获取热榜数据，包括A股市场、ETF基金、港股市场、美股市场等等，每日盘中提取4次，收盘后4次，最晚22点提取一次。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积8000积分可调取使用，积分获取办法请参阅 积分获取办法
- 官方文档：[doc 321](https://tushare.pro/document/2?doc_id=321)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/dc_hot.py:DcHotCollector](../../../collectors/stock/board/dc_hot.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 |
| `ts_code` | str | N | TS代码 |
| `market` | str | N | 类型(A股市场、ETF基金、港股市场、美股市场) |
| `hot_type` | str | N | 热点类型(人气榜、飙升榜) |
| `is_new` | str | N | 是否最新（默认Y，如果为N则为盘中和盘后阶段采集，具体时间可参考rank_time字段，状态N每2小时更新一次，状态Y更新时间为22：30） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `data_type` | str | Y | 数据类型 |
| `ts_code` | str | Y | 股票代码 |
| `ts_name` | str | Y | 股票名称 |
| `rank` | int | Y | 排行或者热度 |
| `pct_change` | float | Y | 涨跌幅% |
| `current_price` | float | Y | 当前价 |
| `rank_time` | str | Y | 排行榜获取时间 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "dc_hot",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取查询月份券商金股
df = pro.dc_hot(trade_date='20240415', market='A股市场',hot_type='人气榜',  fields='ts_code,ts_name,rank')
```

## 实际返回示例（官方文档）

```text
ts_code   ts_name  rank
0   601099.SH     太平洋     1
1   601995.SH    中金公司     2
2   002235.SZ    安妮股份     3
3   601136.SH    首创证券     4
4   600127.SH    金健米业     5
..        ...     ...   ...
95  300675.SZ     建科院    96
96  601900.SH    南方传媒    97
97  600280.SH    中央商场    98
98  300898.SZ    熊猫乳品    99
99  600519.SH    贵州茅台   100
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
