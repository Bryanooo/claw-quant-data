# `news` — 新闻快讯

- 分类：大模型语料
- 功能：获取主流新闻网站的快讯新闻数据,提供超过6年以上历史新闻。
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口需单独开权限（跟积分没关系），具体请参阅 权限说明
- 官方文档：[doc 143](https://tushare.pro/document/2?doc_id=143)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `start_date` | datetime | Y | 开始日期(格式：2018-11-20 09:00:00） |
| `end_date` | datetime | Y | 结束日期 |
| `src` | str | Y | 新闻来源 见下表 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `datetime` | str | Y | 新闻时间 |
| `content` | str | Y | 内容 |
| `title` | str | Y | 标题 |
| `channels` | str | N | 分类 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "news",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "start_date": "20260730",
    "end_date": "20260829",
    "src": "sina"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.news(src='sina', start_date='2018-11-21 09:00:00', end_date='2018-11-22 10:10:00')
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
