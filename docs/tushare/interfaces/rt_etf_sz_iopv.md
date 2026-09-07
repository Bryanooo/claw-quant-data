# `rt_etf_sz_iopv` — ETF实时参考

- 分类：ETF专题
- 功能：ETF实时净值和申购赎回数据参考，目前只提供深市
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口为单独开权限的接口，跟积分多个无关。正式权限请参阅 权限说明
- 官方文档：[doc 454](https://tushare.pro/document/2?doc_id=454)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | ETF代码（默认为空，即一次全市场。支持单个和多个ETF过滤提取） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_time` | datetime | Y | 交易时间 |
| `ts_code` | str | Y | ETF代码 |
| `vol` | float | Y | 成交量（份） |
| `num` | int | Y | 成交笔数 |
| `amount` | float | Y | 成交金额（元） |
| `price` | float | Y | 最新价（元） |
| `iopv` | float | Y | 最近参考净值 |
| `pre_iopv` | float | Y | 前一日参考净值 |
| `buy_num` | int | Y | 申购笔数 |
| `buy_vol` | float | Y | 申购买量(份) |
| `sell_num` | int | Y | 赎回笔数 |
| `sell_vol` | float | Y | 赎回买量（份） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "rt_etf_sz_iopv",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "510300.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 导入sdk包
import tushare as ts

# 配置凭据，如果已全局配置了，可以忽略。
ts.set_token('<--your-token-->')

# 获取接口实例
pro = ts.pro_api()

# 示例： 获取单个ETF（159103.SZ）的最新参考
df = pro.rt_etf_sz_iopv(ts_code="159103.SZ")
print(df)

# 示例： 获取两个ETF的最新参考（159103.SZ,159105.SZ）
df = pro.rt_etf_sz_iopv(ts_code="159103.SZ,159105.SZ")
print(df)

# 示例：获取深市ETF全部实时参考指标
df = pro.rt_etf_sz_iopv()

#示例：获取深市ETF指定指标的实时参考
df = pro.rt_etf_sz_iopv(fields='trade_time,ts_code,iopv,buy_num,buy_vol,sell_num,sell_vol')
print(df)
```

## 实际返回示例（官方文档）

```text
trade_time    ts_code    iopv  buy_num   buy_vol  sell_num  sell_vol
0    2026-03-20 10:27:27  161039.SZ  0.0000        0    0.0000         0    0.0000
1    2026-03-20 10:28:45  159003.SZ  0.0000        7    1.1101        18    3.3692
2    2026-03-20 10:28:48  159005.SZ  0.0000       26    5.3240         4    0.5903
3    2026-03-20 10:29:03  159102.SZ  0.7776        0    0.0000         0    0.0000
4    2026-03-20 10:29:09  159108.SZ  0.9792        1  100.0000         0    0.0000
..                   ...        ...     ...      ...       ...       ...       ...
923  2026-03-20 10:28:00  180302.SZ  0.0000        0    0.0000         0    0.0000
924  2026-03-20 10:29:09  180402.SZ  0.0000        0    0.0000         0    0.0000
925  2026-03-20 10:29:06  180606.SZ  0.0000        0    0.0000         0    0.0000
926  2026-03-20 10:29:06  180701.SZ  0.0000        0    0.0000         0    0.0000
927  2026-03-20 10:29:00  180901.SZ  0.0000        0    0.0000         0    0.0000
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
