# `stock_basic` — 股票基础信息

- 分类：股票数据/基础数据
- 功能：获取基础信息数据，包括股票代码、名称、上市日期、退市日期等
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分起，每分钟请求50次。此接口是基础信息，调取一次就可以拉取完，建议保存倒本地存储后使用
- 官方文档：[doc 25](https://tushare.pro/document/2?doc_id=25)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/stock_basic.py:StockBasicCollector](../../../collectors/stock/basic/stock_basic.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS股票代码( 格式说明 ) |
| `name` | str | N | 名称 |
| `market` | str | N | 市场类别 （主板/创业板/科创板/CDR/北交所） |
| `list_status` | str | N | 上市状态 L上市 D退市 P暂停上市 G 未交易 UN未上市，默认是L |
| `exchange` | str | N | 交易所 SSE上交所 SZSE深交所 BSE北交所 |
| `is_hs` | str | N | 是否沪深港通标的，N否 H沪股通 S深股通 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `symbol` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `area` | str | Y | 地域 |
| `industry` | str | Y | 所属行业 |
| `fullname` | str | N | 股票全称 |
| `enname` | str | N | 英文全称 |
| `cnspell` | str | Y | 拼音缩写 |
| `market` | str | Y | 市场类型（主板/创业板/科创板/CDR） |
| `exchange` | str | N | 交易所代码 |
| `curr_type` | str | N | 交易货币 |
| `list_status` | str | N | 上市状态 L上市 D退市 G过会未交易 P暂停上市 UN未上市 |
| `list_date` | str | Y | 上市日期 |
| `delist_date` | str | N | 退市日期 |
| `is_hs` | str | N | 是否沪深港通标的，N否 H沪股通 S深股通 |
| `act_name` | str | Y | 实控人名称 |
| `act_ent_type` | str | Y | 实控人企业性质 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stock_basic",
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

#查询当前所有正常上市交易的股票列表

data = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
```

## 实际返回示例（官方文档）

```text
ts_code     symbol     name     area industry    list_date
0     000001.SZ  000001  平安银行   深圳       银行  19910403
1     000002.SZ  000002   万科A   深圳     全国地产  19910129
2     000004.SZ  000004  国农科技   深圳     生物制药  19910114
3     000005.SZ  000005  世纪星源   深圳     房产服务  19901210
4     000006.SZ  000006  深振业A   深圳     区域地产  19920427
5     000007.SZ  000007   全新好   深圳     酒店餐饮  19920413
6     000008.SZ  000008  神州高铁   北京     运输设备  19920507
7     000009.SZ  000009  中国宝安   深圳      综合类  19910625
8     000010.SZ  000010  美丽生态   深圳     建筑施工  19951027
9     000011.SZ  000011  深物业A   深圳     区域地产  19920330
10    000012.SZ  000012   南玻A   深圳       玻璃  19920228
11    000014.SZ  000014  沙河股份   深圳     全国地产  19920602
12    000016.SZ  000016  深康佳A   深圳     家用电器  19920327
13    000017.SZ  000017  深中华A   深圳     文教休闲  19920331
14    000018.SZ  000018  神州长城   深圳     装修装饰  19920616
15    000019.SZ  000019  深深宝A   深圳      软饮料  19921012
16    000020.SZ  000020  深华发A   深圳      元器件  19920428
17    000021.SZ  000021   深科技   深圳     电脑设备  19940202
18    000022.SZ  000022  深赤湾A   深圳       港口  19930505
19    000023.SZ  000023  深天地A   深圳     其他建材  19930429
20    000025.SZ  000025   特力A   深圳     汽车服务  19930621
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
