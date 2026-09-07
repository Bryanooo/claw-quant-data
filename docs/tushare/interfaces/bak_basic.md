# `bak_basic` — 股票历史列表（历史每天股票列表）

- 分类：股票数据/基础数据
- 功能：获取备用基础列表，数据从2016年开始
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 262](https://tushare.pro/document/2?doc_id=262)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/bak_basic.py:BakBasicCollector](../../../collectors/stock/basic/bak_basic.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 |
| `ts_code` | str | N | 股票代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | TS股票代码 |
| `name` | str | Y | 股票名称 |
| `industry` | str | Y | 行业 |
| `area` | str | Y | 地域 |
| `pe` | float | Y | 市盈率（动） |
| `float_share` | float | Y | 流通股本（亿） |
| `total_share` | float | Y | 总股本（亿） |
| `total_assets` | float | Y | 总资产（亿） |
| `liquid_assets` | float | Y | 流动资产（亿） |
| `fixed_assets` | float | Y | 固定资产（亿） |
| `reserved` | float | Y | 公积金 |
| `reserved_pershare` | float | Y | 每股公积金 |
| `eps` | float | Y | 每股收益 |
| `bvps` | float | Y | 每股净资产 |
| `pb` | float | Y | 市净率 |
| `list_date` | str | Y | 上市日期 |
| `undp` | float | Y | 未分配利润 |
| `per_undp` | float | Y | 每股未分配利润 |
| `rev_yoy` | float | Y | 收入同比（%） |
| `profit_yoy` | float | Y | 利润同比（%） |
| `gpr` | float | Y | 毛利率（%） |
| `npr` | float | Y | 净利润率（%） |
| `holder_num` | int | Y | 股东人数 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "bak_basic",
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

df = pro.bak_basic(trade_date='20211012', fields='trade_date,ts_code,name,industry,pe')
```

## 实际返回示例（官方文档）

```text
trade_date    ts_code  name industry       pe
0      20211012  300605.SZ  恒锋信息     软件服务  56.4400
1      20211012  301017.SZ  漱玉平民     医药商业  58.7600
2      20211012  300755.SZ  华致酒行     其他商业  23.0000
3      20211012  300255.SZ  常山药业     生物制药  24.9900
4      20211012  688378.SH   奥来德     专用机械  24.9600
...         ...        ...   ...      ...      ...
4529   20211012  688257.SH  新锐股份     机械基件   0.0000
4530   20211012  688255.SH   凯尔达     机械基件   0.0000
4531   20211012  688211.SH  中科微至     专用机械   0.0000
4532   20211012  605567.SH  春雪食品       食品   0.0000
4533   20211012  605566.SH  福莱蒽特     染料涂料   0.0000
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
