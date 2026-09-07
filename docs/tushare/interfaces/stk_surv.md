# `stk_surv` — 机构调研表

- 分类：股票数据/特色数据
- 功能：获取上市公司机构调研记录数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积5000积分可使用
- 官方文档：[doc 275](https://tushare.pro/document/2?doc_id=275)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/stk_surv.py:StkSurvCollector](../../../collectors/stock/extra/stk_surv.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 调研日期 |
| `start_date` | str | N | 调研开始日期 |
| `end_date` | str | N | 调研结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `surv_date` | str | Y | 调研日期 |
| `fund_visitors` | str | Y | 机构参与人员 |
| `rece_place` | str | Y | 接待地点 |
| `rece_mode` | str | Y | 接待方式 |
| `rece_org` | str | Y | 接待的公司 |
| `org_type` | str | Y | 接待公司类型 |
| `comp_rece` | str | Y | 上市公司接待人员 |
| `content` | None | N | 调研内容 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_surv",
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

df = pro.stk_surv(ts_code='002223.SZ', trade_date='20211024', fields='ts_code,name,surv_date,fund_visitors,rece_place,rece_mode,rece_org')
```

## 实际返回示例（官方文档）

```text
ts_code  name  surv_date fund_visitors rece_place      rece_mode                          rece_org
1   002223.SZ  鱼跃医疗  20211024            郝淼       电话会议    特定对象调研                              宝盈基金
2   002223.SZ  鱼跃医疗  20211024           秦瑶函       电话会议    特定对象调研                           贝莱德资产管理
3   002223.SZ  鱼跃医疗  20211024            谭飞       电话会议    特定对象调研                              博远基金
4   002223.SZ  鱼跃医疗  20211024            李晗       电话会议    特定对象调研                            创金合信基金
..        ...   ...       ...           ...        ...       ...                               ...
77  002223.SZ  鱼跃医疗  20211024           李虹达       电话会议    特定对象调研                              中信建投
78  002223.SZ  鱼跃医疗  20211024           李明蔚       电话会议    特定对象调研                              中银国际
79  002223.SZ  鱼跃医疗  20211024            王俊       电话会议    特定对象调研                            重庆穿石投资
80  002223.SZ  鱼跃医疗  20211024            李扬       电话会议    特定对象调研                              朱雀基金
81  002223.SZ  鱼跃医疗  20211024           徐烨程       电话会议    特定对象调研                            逐流资产管理
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
