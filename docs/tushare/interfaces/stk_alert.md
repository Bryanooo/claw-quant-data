# `stk_alert` — 交易所重点提示证券

- 分类：股票数据/参考数据
- 功能：根据证券交易所交易规则的有关规定，交易所每日发布重点提示证券
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要6000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 453](https://tushare.pro/document/2?doc_id=453)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/reference/stk_alert.py](../../../collectors/stock/reference/stk_alert.py)、[collectors/stock/reference/stk_alert.py:StkAlertCollector](../../../collectors/stock/reference/stk_alert.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码（可以通过stock_basic获取）示例:000001.SZ |
| `trade_date` | str | N | 交易所重点提示起始日期（YYYYMMDD格式）示例:20260312 |
| `start_date` | str | N | 开始日期（YYYYMMDD格式）示例:20260312 |
| `end_date` | str | N | 结束日期（YYYYMMDD格式）示例:20260312 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `start_date` | str | Y | 交易所重点提示起始日期 |
| `end_date` | str | Y | 交易所重点提示参考截至日期 |
| `type` | str | Y | 提示类型 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_alert",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 导入sdk包
import tushare as ts

# 配置凭据token
ts.set_token('<--your-token-->')

# 初始化接口实例
pro = ts.pro_api()

#获取2026年3月11日的当日所有重点提示证券
df = pro.stk_alert(trade_date='20260311')

#获取股票”豫能控股“2025年以来每个交易日的重点提示
df = pro.stk_alert(ts_code='001896.SZ', start_date='20250101', end_date='20251231')
```

## 实际返回示例（官方文档）

```text
ts_code            name  start_date    end_date       type
0  513310.SH            中韩芯片  2026-03-16  2026-03-27  交易所重点提示证券
1  001896.SZ            豫能控股  2026-03-16  2026-03-27  交易所重点提示证券
2  600599.SH           *ST熊猫  2026-03-13  2026-03-26  交易所重点提示证券
3  301373.SZ            凌玮科技  2026-03-11  2026-03-24  交易所重点提示证券
4  600599.SH           *ST熊猫  2026-03-11  2026-03-24  交易所重点提示证券
5  002969.SZ            嘉美包装  2026-03-11  2026-03-24  交易所重点提示证券
6  600355.SH           *ST精伦  2026-03-09  2026-03-20  交易所重点提示证券
7  600696.SH           *ST岩石  2026-03-09  2026-03-20  交易所重点提示证券
8  000711.SZ            ST京蓝  2026-03-04  2026-03-17  交易所重点提示证券
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
