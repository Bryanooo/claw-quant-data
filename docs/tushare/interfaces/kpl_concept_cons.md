# `kpl_concept_cons` — 开盘啦题材成分

- 分类：股票数据/打板专题数据
- 功能：获取概念题材的成分股
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：5000积分可提取数据，具体请参阅 积分获取办法
- 官方文档：[doc 351](https://tushare.pro/document/2?doc_id=351)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/kpl_concept_cons.py:KplConceptConsCollector](../../../collectors/stock/board/kpl_concept_cons.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期（YYYYMMDD格式） |
| `ts_code` | str | N | 题材代码（xxxxxx.KP格式） |
| `con_code` | str | N | 成分代码（xxxxxx.SH格式） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 题材ID |
| `name` | str | Y | 题材名称 |
| `con_name` | str | Y | 股票名称 |
| `con_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `desc` | str | Y | 描述 |
| `hot_num` | int | Y | 人气值 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "kpl_concept_cons",
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

df = pro.kpl_concept_cons(trade_date='20241014')
```

## 实际返回示例（官方文档）

```text
ts_code      name     ts_name con_code trade_date
0     000111.KP  化债概念    信达地产  600657.SH   20241014
1     000111.KP  化债概念    银宝山新  002786.SZ   20241014
2     000111.KP  化债概念    摩恩电气  002451.SZ   20241014
3     000111.KP  化债概念    光大嘉宝  600622.SH   20241014
4     000111.KP  化债概念    海德股份  000567.SZ   20241014
...         ...   ...     ...        ...        ...
2995  000229.KP    电力    特变电工  600089.SH   20241014
2996  000229.KP    电力    中国西电  601179.SH   20241014
2997  000229.KP    电力    金盘科技  688676.SH   20241014
2998  000229.KP    电力    思源电气  002028.SZ   20241014
2999  000229.KP    电力    明阳电气  301291.SZ   20241014
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
