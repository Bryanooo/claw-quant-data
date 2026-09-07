# `cn_schedule` — 中国经济数据发布日程

- 分类：宏观经济/国内宏观
- 功能：获取国家统计局、中国人民银行等经济数据发布日程及对应tushare接口，持续更新中
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要2000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 461](https://tushare.pro/document/2?doc_id=461)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `m` | str | N | 月份（YYYYMM） |
| `title` | str | N | 发布数据 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `month` | str | Y | 月份YYYYMM |
| `publish_date` | str | Y | 发布日期 |
| `title` | str | Y | 发布数据 |
| `issuing_org` | str | Y | 发布单位 |
| `data_api` | str | Y | tushare对应接口 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cn_schedule",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
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

# 拉取接口(cn_schedule)数据
# <请写入示例参数的具体含义>。示例：获取2026年4月经济数据发布日程及对应tushare接口
df = pro.cn_schedule(m="202604")
print(df)
```

## 实际返回示例（官方文档）

```text
month publish_date               title                issuing_org      data_api
0  202604     20260404  流通领域重要生产资料市场价格变动情况       国家统计局      待上线
1  202604     20260410        居民消费价格指数月度报告       国家统计局   cn_cpi
2  202604     20260410       工业生产者价格指数月度报告       国家统计局   cn_ppi
3  202604     20260414  流通领域重要生产资料市场价格变动情况       国家统计局      待上线
4  202604     20260416        全国居民收支情况季度报告       国家统计局      待上线
5  202604     20260416       全国工业产能利用率季度报告       国家统计局      待上线
6  202604     20260416      商品住宅销售价格指数月度报告       国家统计局      待上线
7  202604     20260416    固定资产投资（不含农户）月度报告       国家统计局      待上线
8  202604     20260416            国民经济运行情况       国家统计局      待上线
9  202604     20260416      房地产开发和销售情况月度报告       国家统计局      待上线
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_cn_schedule`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/cn_schedule.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
