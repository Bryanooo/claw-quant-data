# `tdx_member` — TDX板块成分

- 分类：股票数据/打板专题数据
- 功能：获取各板块成分股信息
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累6000积分可调取，具体请参阅 积分获取办法
- 官方文档：[doc 377](https://tushare.pro/document/2?doc_id=377)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/tdx_member.py:TdxMemberCollector](../../../collectors/stock/board/tdx_member.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 板块代码：xxxxxx.TDX |
| `con_code` | str | N | 成分股票代码 |
| `trade_date` | str | N | 交易日期：（YYYYMMDD格式） |
| `start_date` | str | N | 开始日期：（YYYYMMDD格式） |
| `end_date` | str | N | 结束日期：（YYYYMMDD格式） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 板块代码 |
| `trade_date` | str | Y | 交易日期 |
| `con_code` | str | Y | 成分股票代码 |
| `con_name` | str | Y | 成分股票名称 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "tdx_member",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取通达信板块2025年5月13日的航运概念板块成分股
df = pro.tdx_member(trade_date='20250513', ts_code='880728.TDX')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date   con_code     con_name
0   880728.TDX   20250513  000039.SZ     中集集团
1   880728.TDX   20250513  000088.SZ    盐 田 港
2   880728.TDX   20250513  000507.SZ      珠海港
3   880728.TDX   20250513  000520.SZ     凤凰航运
4   880728.TDX   20250513  000582.SZ     北部湾港
..         ...        ...        ...      ...
59  880728.TDX   20250513  603869.SH     ST智知
60  880728.TDX   20250513  603967.SH     中创物流
61  880728.TDX   20250513  605090.SH     九丰能源
62  880728.TDX   20250513  833171.BJ     国航远洋
63  880728.TDX   20250513  872351.BJ     华光源海
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
