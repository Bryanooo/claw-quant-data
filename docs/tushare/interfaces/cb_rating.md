# `cb_rating` — 获取可转债评级历史记录

- 分类：债券专题
- 功能：获取可转债评级历史记录
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要2000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 458](https://tushare.pro/document/2?doc_id=458)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码，支持多值输入 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码 |
| `ann_date` | str | Y | 评级发布日期 |
| `rating_date` | str | Y | 评级日期 |
| `rating_com_name` | str | Y | 评级机构 |
| `rating_way` | str | Y | 评级方式 |
| `rating_type` | str | Y | 评级类别 |
| `rating` | str | Y | 信用等级 |
| `rating_outlook` | str | Y | 评级展望 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cb_rating",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "110000.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
# 请补充示例代码
pro = ts.pro_api()


#获取可转债行情
df = pro.cb_daily(ts_code='128119.SZ', fields='ts_code,ann_date, rating_date,rating_com_name,rating,rating_outlook')
```

## 实际返回示例（官方文档）

```text
ts_code   ann_date   rating_date  rating_com_name       rating     rating_outlook
0  128119.SZ  20260402    20260330    联合资信评估股份有限公司    BB+           None
1  128119.SZ  20260211    20260209    联合资信评估股份有限公司    BBB           None
2  128119.SZ  20251118    20251113    联合资信评估股份有限公司     A-           None
3  128119.SZ  20250627    20250626    联合资信评估股份有限公司     A+       列入评级观察名单
4  128119.SZ  20240620    20240614    联合资信评估股份有限公司     A+             稳定
5  128119.SZ  20230622    20230621    联合资信评估股份有限公司    AA-           None
6  128119.SZ  20220630    20220629    联合资信评估股份有限公司    AA-           None
7  128119.SZ  20210527    20210526    联合资信评估股份有限公司     AA           None
8  128119.SZ  20200919    20200916      联合信用评级有限公司     AA           None
9  128119.SZ  20200709    20190911      联合信用评级有限公司     AA           None
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_cb_rating`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/cb_rating.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
