# `cb_price_chg` — 可转债转股价变动

- 分类：债券专题
- 功能：获取可转债转股价变动
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口需单独开权限（跟积分没关系），具体请参阅 积分获取办法
- 官方文档：[doc 246](https://tushare.pro/document/2?doc_id=246)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码，支持多值输入 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码 |
| `bond_short_name` | str | Y | 转债简称 |
| `publish_date` | str | Y | 公告日期 |
| `change_date` | str | Y | 变动日期 |
| `convert_price_initial` | float | Y | 初始转股价格 |
| `convertprice_bef` | float | Y | 修正前转股价格 |
| `convertprice_aft` | float | Y | 修正后转股价格 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cb_price_chg",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "110000.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api(your token)
#获取可转债转股价变动
df = pro.cb_price_chg(ts_code="113556.SH,128114.SZ,128110.SZ",fields="ts_code,bond_short_name,change_date,convert_price_initial,convertprice_bef,convertprice_aft")
```

## 实际返回示例（官方文档）

```text
ts_code bond_short_name change_date convert_price_initial convertprice_bef convertprice_aft
0  113556.SH    至纯转债    20191220           29.4700             None             None
1  113556.SH    至纯转债    20200629           29.4700          29.4700          29.3800
2  128110.SZ    永兴转债    20200609           17.1600             None             None
3  128114.SZ    正邦转债    20200617           16.0900             None             None
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
