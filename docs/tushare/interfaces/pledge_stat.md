# `pledge_stat` — 股权质押统计数据

- 分类：股票数据/参考数据
- 功能：获取股票质押统计数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 110](https://tushare.pro/document/2?doc_id=110)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/reference/pledge_stat.py](../../../collectors/stock/reference/pledge_stat.py)、[collectors/stock/reference/pledge_stat.py:PledgeStatCollector](../../../collectors/stock/reference/pledge_stat.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `end_date` | str | N | 截止日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `end_date` | str | Y | 截止日期 |
| `pledge_count` | int | Y | 质押次数 |
| `unrest_pledge` | float | Y | 无限售股质押数量（万） |
| `rest_pledge` | float | Y | 限售股份质押数量（万） |
| `total_share` | float | Y | 总股本 |
| `pledge_ratio` | float | Y | 质押比例 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "pledge_stat",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()
#或者
#pro = ts.pro_api('your token')


df = pro.pledge_stat(ts_code='000014.SZ')
```

## 实际返回示例（官方文档）

```text
ts_code  end_date  pledge_count  unrest_pledge  rest_pledge  \
0    000014.SZ  20180928            23          63.16          0.0
1    000014.SZ  20180921            24          63.17          0.0
2    000014.SZ  20180914            24          63.17          0.0
3    000014.SZ  20180907            28          63.69          0.0
4    000014.SZ  20180831            28          63.69          0.0
5    000014.SZ  20180824            29          64.74          0.0
6    000014.SZ  20180817            29          64.74          0.0
7    000014.SZ  20180810            29          64.74          0.0
8    000014.SZ  20180803            29          64.74          0.0
9    000014.SZ  20180727            29          64.74          0.0
10   000014.SZ  20180720            29          64.74          0.0
11   000014.SZ  20180713            29          64.74          0.0
12   000014.SZ  20180706            30          64.77          0.0
13   000014.SZ  20180629            30          64.77          0.0
14   000014.SZ  20180622            30          64.77          0.0
15   000014.SZ  20180615            28          66.50          0.0
```

## claw-quant 存储契约

### 运行时分片契约

空参数全市场请求实测触及 3,000 行可疑上限，不能证明完整。系统仅允许
从 `stock_basic.ts_code` 白名单逐股扇出，每个子任务保存实际股票代码、行数和
完整性证据。批次未覆盖完整股票宇宙前状态保持 `incomplete`。

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
