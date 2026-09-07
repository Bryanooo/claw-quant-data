# `stock_company` — 上市公司基本信息

- 分类：股票数据/基础数据
- 功能：获取上市公司基础信息，单次提取4500条，可以根据交易所分批提取
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少120积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 112](https://tushare.pro/document/2?doc_id=112)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stock_company.py:StockCompanyCollector](../../../collectors/stock/basic/stock_company.py)

## 输入契约

当前官方目录没有可提取的输入参数表；调用时仍由 Tushare 服务端完成最终校验。

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `exchange` | str | N | 交易所代码 ，SSE上交所 SZSE深交所 BSE北交所 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stock_company",
  "token": "${TUSHARE_TOKEN}",
  "params": {},
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#或者
#pro = ts.pro_api('your token')

df = pro.stock_company(exchange='SZSE', fields='ts_code,chairman,manager,secretary,reg_capital,setup_date,province')
```

## 实际返回示例（官方文档）

```text
ts_code chairman manager secretary   reg_capital setup_date province  \
0     000001.SZ      谢永林     胡跃飞        周强  1.717041e+06   19871222       广东
1     000002.SZ       郁亮     祝九胜        朱旭  1.103915e+06   19840530       广东
2     000003.SZ      马钟鸿     马钟鸿        安汪  3.334336e+04   19880208       广东
3     000004.SZ      李林琳     李林琳       徐文苏  8.397668e+03   19860505       广东
4     000005.SZ       丁芃     郑列列       罗晓春  1.058537e+05   19870730       广东
5     000006.SZ      赵宏伟     朱新宏        杜汛  1.349995e+05   19850525       广东
6     000007.SZ      智德宇     智德宇       陈伟彬  3.464480e+04   19830311       广东
7     000008.SZ      王志全      钟岩       王志刚  2.818330e+05   19891011       北京
8     000009.SZ      陈政立     陈政立       郭山清  2.149345e+05   19830706       广东
9     000010.SZ       曾嵘     李德友       金小刚  8.198547e+04   19881231       广东
10    000011.SZ      刘声向     王航军       范维平  5.959791e+04   19830117       广东
11    000012.SZ       陈琳      王健       杨昕宇  2.863277e+05   19840910       广东
12    000013.SZ      厉怒江     阮克竖       刘渝敏  3.033550e+04   19920114       广东
13    000014.SZ       陈勇      温毅        王凡  2.017052e+04   19870727       广东
14    000015.SZ      宿南南      马骧       蒋孝安  1.598761e+05   19880408       广东
15    000016.SZ      刘凤喜      周彬       吴勇军  2.407945e+05   19801001       广东
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
