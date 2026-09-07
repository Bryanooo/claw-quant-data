# `index_basic` — 指数基本信息

- 分类：指数专题
- 功能：获取指数基础信息，数据起始时间1990-01-01，每天18点更新，2000积分起，单次返回8000行。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 94](https://tushare.pro/document/2?doc_id=94)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/index/basic.py:IndexBasicCollector](../../../collectors/index/basic.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS指数代码 |
| `symbol` | str | N | 指数代码，支持多值输入，如000300,000001 |
| `name` | str | N | 指数简称 |
| `market` | str | N | 交易所或服务商(默认SSE，详见下方说明) |
| `publisher` | str | N | 发布商 |
| `category` | str | N | 指数类别 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `name` | str | Y | 简称 |
| `fullname` | str | N | 指数全称 |
| `market` | str | Y | 市场 |
| `publisher` | str | Y | 发布方 |
| `index_type` | str | N | 指数风格 |
| `category` | str | Y | 指数类别 |
| `base_date` | str | Y | 基期 |
| `base_point` | float | Y | 基点 |
| `list_date` | str | Y | 发布日期 |
| `weight_rule` | str | N | 加权方式 |
| `desc` | str | N | 描述 |
| `exp_date` | str | N | 终止日期 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "index_basic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.index_basic(market='SW')
```

## 实际返回示例（官方文档）

```text
ts_code    name              market     publisher   category     base_date  base_point  \
5    801010.SI    农林牧渔             SW      申万   一级行业指数  19991230      1000.0
6    801011.SI    林业Ⅱ               SW     申万  二级行业指数  19991230      1000.0
7    801012.SI    农产品加工           SW      申万   二级行业指数  19991230      1000.0
8    801013.SI    农业综合Ⅱ           SW      申万  二级行业指数  19991230      1000.0
9    801014.SI    饲料Ⅱ               SW     申万  二级行业指数  19991230      1000.0
10   801015.SI    渔业                 SW      申万   二级行业指数  19991230      1000.0
11   801016.SI    种植业               SW      申万   二级行业指数  19991230      1000.0
12   801017.SI    畜禽养殖Ⅱ           SW      申万  二级行业指数  20111010      1000.0
13   801018.SI    动物保健Ⅱ           SW      申万研  二级行业指数  19991230      1000.0
14   801020.SI    采掘                 SW      申万   一级行业指数  19991230      1000.0
15   801021.SI    煤炭开采Ⅱ           SW      申万  二级行业指数  19991230      1000.0
16   801022.SI    其他采掘Ⅱ           SW      申万  二级行业指数  19991230      1000.0
17   801023.SI    石油开采Ⅱ           SW      申万  二级行业指数  19991230      1000.0
18   801024.SI    采掘服务Ⅱ           SW      申万  二级行业指数  19991230      1000.0
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
