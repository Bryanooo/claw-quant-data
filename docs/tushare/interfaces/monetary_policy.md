# `monetary_policy` — 央行货币政策执行报告

- 分类：大模型语料
- 功能：获取央行季度更新的货币政策执行报告，历史数据开始于2001年每年四篇，提供原始PDF下载链接，可用于分析过去20多年央行货币政策的动向、宏观以及金融市场的情况。
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口为单独权限（跟积分没关系），具体请参阅 权限对应列表
- 官方文档：[doc 465](https://tushare.pro/document/2?doc_id=465)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `start_date` | str | N | 发布开始日期（YYYYMMDD格式）示例:20260312 |
| `end_date` | str | N | 发布结束日期（YYYYMMDD格式）示例:20260312 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `pub_date` | str | Y | 发布日期 |
| `title` | str | Y | 标题 |
| `url` | str | Y | 原文链接 |
| `pdf_url` | str | Y | pdf链接 |
| `content_html` | str | Y | 带标签的正文内容 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "monetary_policy",
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
# 导入sdk包
import tushare as ts

# 配置凭据，如果已全局配置了，可以忽略。
ts.set_token('<--your-token-->')

# 获取接口实例
pro = ts.pro_api()

# 一次拉取全部央行货币政策执行报告原始数据
df = pro.monetary_policy()
print(df)

# 指定输出字段拉取央行货币政策执行报告原始数据
df = pro.monetary_policy(start_date='20250101', end_date='20251231', fields='pub_date,title,url')
print(df)
```

## 实际返回示例（官方文档）

```text
pub_date                title                                                url
0  20251111  2025年第三季度中国货币政策执行报告  http://www.pbc.gov.cn/zhengcehuobisi/125207/12...
1  20250815  2025年第二季度中国货币政策执行报告  http://www.pbc.gov.cn/zhengcehuobisi/125207/12...
2  20250509  2025年第一季度中国货币政策执行报告  http://www.pbc.gov.cn/zhengcehuobisi/125207/12...
3  20250213  2024年第四季度中国货币政策执行报告  http://www.pbc.gov.cn/zhengcehuobisi/125207/12...
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
