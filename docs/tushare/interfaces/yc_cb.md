# `yc_cb` — 国债收益率曲线

- 分类：债券专题
- 功能：获取中债收益率曲线，目前可获取中债国债收益率曲线即期和到期收益率曲线数据
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：属于单独的权限接口，请在群里联系群主或管理员
- 官方文档：[doc 201](https://tushare.pro/document/2?doc_id=201)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 收益率曲线编码：1001.CB-国债收益率曲线 |
| `curve_type` | str | N | 曲线类型：0-到期，1-即期 |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 查询起始日期 |
| `end_date` | str | N | 查询结束日期 |
| `curve_term` | float | N | 期限 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 曲线编码 |
| `curve_name` | str | Y | 曲线名称 |
| `curve_type` | str | Y | 曲线类型：0-到期，1-即期 |
| `curve_term` | float | Y | 期限(年) |
| `yield` | float | Y | 收益率(%) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "yc_cb",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api(your token)
#获取中债收益率曲线
df = pro.yc_cb(ts_code='1001.CB',curve_type='0',trade_date='20200203')
```

## 实际返回示例（官方文档）

```text
trade_date ts_code curve_name curve_type curve_term     yield
0      20200203        101  中债国债收益率曲线          0     0.0000  1.697300
1      20200203        101  中债国债收益率曲线          0     0.0800  1.770000
2      20200203        101  中债国债收益率曲线          0     0.1000  1.770100
3      20200203        101  中债国债收益率曲线          0     0.1700  1.770300
4      20200203        101  中债国债收益率曲线          0     0.2000  1.772300
...         ...        ...        ...        ...        ...       ...
1001   20200203        101  中债国债收益率曲线          1    49.6000  3.774100
1002   20200203        101  中债国债收益率曲线          1    49.7000  3.774700
1003   20200203        101  中债国债收益率曲线          1    49.8000  3.775400
1004   20200203        101  中债国债收益率曲线          1    49.9000  3.776100
1005   20200203        101  中债国债收益率曲线          1    50.0000  3.776800
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
