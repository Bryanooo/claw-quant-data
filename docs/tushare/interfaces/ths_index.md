# `ths_index` — 概念和行业指数

- 分类：股票数据/打板专题数据
- 功能：获取板块指数，包括概念、行业、特色指数。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：本接口需有6000积分，单次最大返回5000行数据，一次可提取全部数据，请勿循环提取。
- 官方文档：[doc 259](https://tushare.pro/document/2?doc_id=259)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/ths_index.py:ThsIndexCollector](../../../collectors/stock/board/ths_index.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 指数代码 |
| `exchange` | str | N | 市场类型A-a股 HK-港股 US-美股 |
| `type` | str | N | 指数类型 N-概念指数 I-行业指数 R-地域指数 S-特色指数 ST-风格指数 TH-主题指数 BB-宽基指数 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 代码 |
| `name` | str | Y | 名称 |
| `count` | int | Y | 成分个数 |
| `exchange` | str | Y | 交易所 |
| `list_date` | str | Y | 上市日期 |
| `type` | str | Y | N概念指数S特色指数 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "ths_index",
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

df = pro.ths_index()
```

## 实际返回示例（官方文档）

```text
ts_code     name       count exchange list_date type
0    885835.TI     参股银行    126        A  20190416    N
1    885472.TI    上海自贸区     51        A  20130813    N
2    885788.TI     网络直播     63        A  20180312    N
3    885881.TI      云办公     29        A  20200203    N
4    885785.TI     小米概念     91        A  20180306    N
..         ...      ...    ...      ...       ...  ...
266  885566.TI      大飞机     58        A  20140519    N
267  885841.TI  草地贪夜蛾防治     18        A  20190517    N
268  885760.TI    装配式建筑     50        A  20170918    N
269  885909.TI     辅助生殖     15        A  20201023    N
270  885883.TI   医疗废物处理     25        A  20200207    N
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
