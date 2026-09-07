# `kpl_list` — 开盘啦榜单数据

- 分类：股票数据/打板专题数据
- 功能：获取涨停、跌停、炸板等榜单数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：5000积分每分钟可以请求200次每天总量1万次，8000积分以上每分钟500次每天总量不限制，具体请参阅 积分获取办法
- 官方文档：[doc 347](https://tushare.pro/document/2?doc_id=347)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/kpl_list.py:KplListCollector](../../../collectors/stock/board/kpl_list.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期 |
| `tag` | str | N | 板单类型（涨停/炸板/跌停/自然涨停/竞价，默认为涨停) |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 代码 |
| `name` | str | Y | 名称 |
| `trade_date` | str | Y | 交易时间 |
| `lu_time` | str | Y | 涨停时间 |
| `ld_time` | str | Y | 跌停时间 |
| `open_time` | str | Y | 开板时间 |
| `last_time` | str | Y | 最后涨停时间 |
| `lu_desc` | str | Y | 涨停原因 |
| `tag` | str | Y | 标签 |
| `theme` | str | Y | 板块 |
| `net_change` | float | Y | 主力净额(元) |
| `bid_amount` | float | Y | 竞价成交额(元) |
| `status` | str | Y | 状态（N连板） |
| `bid_change` | float | Y | 竞价净额 |
| `bid_turnover` | float | Y | 竞价换手% |
| `lu_bid_vol` | float | Y | 涨停委买额 |
| `pct_chg` | float | Y | 涨跌幅% |
| `bid_pct_chg` | float | Y | 竞价涨幅% |
| `rt_pct_chg` | float | Y | 实时涨幅% |
| `limit_order` | float | Y | 封单 |
| `amount` | float | Y | 成交额 |
| `turnover_rate` | float | Y | 换手率% |
| `free_float` | float | Y | 实际流通 |
| `lu_limit_order` | float | Y | 最大封单 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "kpl_list",
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

df = pro.kpl_list(trade_date='20240927', tag='涨停', fields='ts_code,name,trade_date,tag,theme,status')
```

## 实际返回示例（官方文档）

```text
ts_code  name      trade_date tag         theme         status
0    000762.SZ  西藏矿业   20240927  涨停       锂矿、盐湖提锂     首板
1    300399.SZ  天利科技   20240927  涨停    互联网金融、金融概念     首板
2    002673.SZ  西部证券   20240927  涨停      证券、控参股基金     首板
3    002050.SZ  三花智控   20240927  涨停  汽车热管理、比亚迪产业链     首板
4    600801.SH  华新水泥   20240927  涨停        水泥、地产链     首板
..         ...   ...        ...  ..           ...    ...
126  600696.SH  岩石股份   20240927  涨停         白酒、酿酒    2连板
127  600606.SH  绿地控股   20240927  涨停       房地产、地产链    2连板
128  000882.SZ  华联股份   20240927  涨停      零售、互联网金融    2连板
129  000069.SZ  华侨城Ａ   20240927  涨停       房地产、地产链    2连板
130  002570.SZ   贝因美   20240927  涨停       多胎概念、乳业     首板
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。
`net_change`（主力净额）和 `bid_change`（竞价净额）按金额使用
`NUMERIC(18,2)`，百分比字段继续使用三位小数，避免把亿元级金额误建模为涨跌幅。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
