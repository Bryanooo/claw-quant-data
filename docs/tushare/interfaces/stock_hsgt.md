# `stock_hsgt` — 沪深港通股票列表

- 分类：股票数据/基础数据
- 功能：获取沪深港通股票列表
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：3000积分起 提示：每天上午9:20更新，单次请求最大返回2000行数据，可根据类型循环提取,本接口数据从20250812开始
- 官方文档：[doc 398](https://tushare.pro/document/2?doc_id=398)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stock_hsgt.py:StockHsgtCollector](../../../collectors/stock/basic/stock_hsgt.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期（格式：YYYYMMDD） |
| `type` | str | Y | 类型（参考下表） |
| `start_date` | str | N | 开始时间 |
| `end_date` | str | N | 结束时间 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `type` | str | Y | 类型 |
| `name` | str | Y | 股票名称 |
| `type_name` | str | Y | 类型名称 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stock_hsgt",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "type": "1"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取20250813日深股通的股票列表
df = pro.stock_hsgt(trade_date='20250813',type='HK_SZ')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date   type     name type_name
0    001258.SZ   20250813  HK_SZ     立新能源  深股通(港>深)
1     00019.HK   20250813  SZ_HK  太古股份公司A  港股通(深>港)
2    000513.SZ   20250813  HK_SZ     丽珠集团  深股通(港>深)
3    002044.SZ   20250813  HK_SZ     美年健康  深股通(港>深)
4    000338.SZ   20250813  HK_SZ     潍柴动力  深股通(港>深)
..         ...        ...    ...      ...       ...
995  300206.SZ   20250813  HK_SZ     理邦仪器  深股通(港>深)
996   02331.HK   20250813  SH_HK       李宁  港股通(沪>港)
997   01855.HK   20250813  SH_HK     中庆股份  港股通(沪>港)
998  300726.SZ   20250813  HK_SZ     宏达电子  深股通(港>深)
999   06127.HK   20250813  SH_HK     昭衍新药  港股通(沪>港)
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
