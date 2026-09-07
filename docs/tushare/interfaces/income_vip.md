# `income_vip` — 当前官方目录未列出

- 分类：项目扩展接口
- 功能：claw-quant 代码中存在直接实现
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：当前官方目录未列出
- 官方文档：当前官方目录未提供
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/finance/income.py:IncomeCollector](../../../collectors/stock/finance/income.py)

## 输入契约

当前官方目录没有可提取的输入参数表；调用时仍由 Tushare 服务端完成最终校验。

## 输出契约

当前官方目录没有可提取的输出字段表。

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "income_vip",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
