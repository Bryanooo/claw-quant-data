# `research_report` — 券商研究报告

- 分类：大模型语料
- 功能：获取券商研究报告-个股、行业等，历史数据从20170101开始提供，增量每天两次更新
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
- 官方文档：[doc 415](https://tushare.pro/document/2?doc_id=415)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 研报日期（格式：YYYYMMDD，下同） |
| `start_date` | str | N | 研报开始日期 |
| `end_date` | str | N | 研报结束日期 |
| `report_type` | str | N | 研报类别：个股研报/行业研报 |
| `ts_code` | str | N | 股票代码 |
| `inst_csname` | str | N | 券商名称 |
| `ind_name` | str | N | 行业名称 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 研报发布时间 |
| `abstr` | str | Y | 研报摘要 |
| `title` | str | Y | 研报标题 |
| `report_type` | str | Y | 研报类别 |
| `author` | str | Y | 作者 |
| `name` | str | Y | 股票名称 |
| `ts_code` | str | Y | 股票代码 |
| `inst_csname` | str | Y | 机构简称 |
| `ind_name` | str | Y | 行业名称 |
| `url` | str | Y | 下载链接 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "research_report",
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

#获取2026年1月21日券商研报数据
df = pro.research_report(trade_date='20260121', fields='trade_date,file_name,author,inst_csname')
```

## 实际返回示例（官方文档）

```text
trade_date                                          file_name       author inst_csname
0    20260121  东吴证券_2025年业绩预增点评：α与β共振，验证金融信息服务龙头高弹性_20260121.pdf   孙婷,张良卫,武欣姝        东吴证券
1    20260121     世纪证券_TMT行业周报（1月第2周）：阿里巴巴举办千问产品发布会_20260121.pdf       李时樟,罗晴        世纪证券
2    20260121    中银证券_收购DFS大中华区业务，携手LVMH，全面深化国际业务布局_20260121.pdf      李小民,宋环翔        中银证券
3    20260121             国金证券_收购DFS大中华区业务，战略合作LVMH_20260121.pdf       于健,谷亦清        国金证券
4    20260121           太平洋_东星医疗：微创外科平台型小巨人，多元布局促发展_20260121.pdf      谭紫媚,李啸岩         太平洋
..        ...                                                ...          ...         ...
80   20260121             中国银河_商业航天系列报告之一：仰望星空，向天突围_20260121.pdf       李良,胡浩淼        中国银河
81   20260121  腾景数研_2025年全球清洁电器发展报告：市场成长长期向好 行业进化值得期待_2026012...           马佳        腾景数研
82   20260121                太平洋_农业周报：猪价旺季反弹，产能持续去化_20260121.pdf          程晓东         太平洋
83   20260121   东吴证券_2025年业绩预告点评：负极盈利拐点已现，多业务板块持续向好_20260121.pdf  曾朵红,阮巧燕,岳斯瑶        东吴证券
84   20260121       中国银河_携手DFS+LVMH，高端复苏+国货出海平台逻辑强化_20260121.pdf          顾熹闽        中国银河

[85 rows x 4 columns]
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
