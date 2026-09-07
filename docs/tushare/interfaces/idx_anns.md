# `idx_anns` — 指数公告

- 分类：ETF专题
- 功能：获取指数公司披露的相关公告信息，包括中证指数、国证指数、恒生指数和华证指数的及时与历史公告信息，跟踪指数最新信息和发展方向。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要6000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 460](https://tushare.pro/document/2?doc_id=460)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ann_date` | str | N | 公告日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |
| `src` | str | N | 信息来源（中证指数、国证指数、恒生指数、华证指数） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ann_date` | str | Y | 公告日期 |
| `title` | str | Y | 标题 |
| `url` | str | Y | 链接 |
| `source` | str | Y | 来源 |
| `type` | str | Y | 类型(指数发布、指数修订、指数更名、其他） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "idx_anns",
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
# 拉取接口(idx_anns)数据
# 示例：获取2026年4月16日指数公司发布的指数公告
df = pro.idx_anns(ann_date='20260416')

#示例：获取中证指数公司发布的指数公告
df = pro.idx_anns(src='中证指数')

#示例：获取国证指数公司2026年1月以来发布的指数公告，并指定输出字段
df = pro.idx_anns(src='国证指数', start_date='20260101', fields='ann_date,title,type')
```

## 实际返回示例（官方文档）

```text
ann_date                           title                                                url source   type
0  20260420                 关于发布华证HALO指数的公告  https://www.chindices.com/news_detail.html?id=777   华证指数
1  20260417              恒生中国高股息率指数年度指数检讨结果  https://www.hsi.com.hk/static/uploads/contents...   恒生指数     其他
2  20260416                  关于调整三板指数样本股的公告  https://www.csindex.com.cn/#/about/newsDetail?...   中证指数   指数调样
3  20260415                  关于调整三板指数样本股的公告  https://www.csindex.com.cn/#/about/newsDetail?...   中证指数   指数调样
4  20260414                 关于终止计算发布3条指数的公告  http://www.cnindex.com.cn/zh_information/notic...   国证指数
5  20260414                  关于调整三板成指样本股的公告  https://www.csindex.com.cn/#/about/newsDetail?...   中证指数   指数调样
6  20260410             关于发布上证AAA综合债指数系列的公告  https://www.csindex.com.cn/#/about/newsDetail?...   中证指数  新指数发布
7  20260410          关于发布中证交易所AAA综合债指数系列的公告  https://www.csindex.com.cn/#/about/newsDetail?...   中证指数  新指数发布
8  20260410  关于终止计算、维护与发布中证公共卫生主题指数等2条指数的公告  https://www.csindex.com.cn/#/about/newsDetail?...   中证指数     其他
9  20260409                  关于调整三板指数样本股的公告  https://www.csindex.com.cn/#/about/newsDetail?...   中证指数   指数调样
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_idx_anns`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/idx_anns.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
