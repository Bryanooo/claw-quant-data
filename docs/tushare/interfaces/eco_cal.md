# `eco_cal` — 财经日历

- 分类：债券专题
- 功能：获取全球财经日历、包括经济事件数据更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分可调取
- 官方文档：[doc 233](https://tushare.pro/document/2?doc_id=233)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `date` | str | N | 日期（YYYYMMDD格式） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `currency` | str | N | 货币代码 |
| `country` | str | N | 国家（比如：中国、美国） |
| `event` | str | N | 事件 （支持模糊匹配： *非农*） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `date` | str | Y | 日期 |
| `time` | str | Y | 时间 |
| `currency` | str | Y | 货币代码 |
| `country` | str | Y | 国家 |
| `event` | str | Y | 经济事件 |
| `value` | str | Y | 今值 |
| `pre_value` | str | Y | 前值 |
| `fore_value` | str | Y | 预测值 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "eco_cal",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "start_date": "20260730",
    "end_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()


#获取指定日期全球经济日历
df = pro.eco_cal(date='20200403')


#获取中国经济事件
df = pro.eco_cal(country='中国')

#获取美国非农数据
df = pro.eco_cal(event='美国季调后非农*', fields='date,time,country,event,value,pre_value,fore_value')
```

## 实际返回示例（官方文档）

```text
date      time    country                   event         value pre_value fore_value
0   20200410  09:30      中国      中国PPI年率(%)(年度)(三月)           -0.4%      -1.1%
1   20200410  09:30      中国      中国CPI月率(%)(月度)(三月)            0.8%      -0.7%
2   20200410  09:30      中国      中国CPI年率(%)(年度)(三月)            5.2%       4.9%
3   20200407  15:00      中国              中国外汇储备(美元)          3.107T
4   20200403  09:45      中国          中国财新服务业PMI(三月)  43.0      26.5
..       ...    ...     ...                     ...   ...       ...        ...
95  20200229  09:00      中国         中国官方非制造业PMI(二月)  29.6      54.1
96  20200229  09:00      中国          中国官方制造业PMI(二月)  35.7      50.0       46.0
97  20200229  09:00      中国           中国官方综合PMI(二月)  28.9      53.0
98  20200308  00:17      中国           中国贸易帐(美元)(二月)          47.21B     12.75B
99  20200308  00:17      中国  中国进口年率-美元计价(%)(年度)(二月)           16.5%      -9.0%
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_eco_cal`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/eco_cal.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
