# `cb_factor_pro` 标准化表契约

- 功能：获取可转债每日技术面因子数据，用于跟踪可转债当前走势情况，数据由Tushare社区自产，覆盖全历史；输出参数_bfq表示不复权，_qfq表示前复权 _hfq表示后复权，描述中说明了因子的默认传参，如需要特殊参数或者更多因子可以联系管理员评估
- PostgreSQL 表：`tushare_norm_cb_factor_pro`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=cb_factor_pro`）
- REST：`GET /api/v1/datasets/cb_factor_pro/records`
- 接口 REST：`GET /api/v1/interfaces/cb_factor_pro/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | 转债代码 |
| `trade_date` | `str` | `DATE` | 交易日期 |
| `open` | `float` | `NUMERIC` | 开盘价 |
| `high` | `float` | `NUMERIC` | 最高价 |
| `low` | `float` | `NUMERIC` | 最低价 |
| `close` | `float` | `NUMERIC` | 收盘价 |
| `pre_close` | `float` | `NUMERIC` | 昨收价 |
| `change` | `float` | `NUMERIC` | 涨跌额 |
| `pct_change` | `float` | `NUMERIC` | 涨跌幅 （未复权，如果是复权请用 通用行情接口 ） |
| `vol` | `float` | `NUMERIC` | 成交量 （手） |
| `amount` | `float` | `NUMERIC` | 成交金额(万元) |
| `asi_bfq` | `float` | `NUMERIC` | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| `asit_bfq` | `float` | `NUMERIC` | 振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10 |
| `atr_bfq` | `float` | `NUMERIC` | 真实波动N日平均值-CLOSE, HIGH, LOW, N=20 |
| `bbi_bfq` | `float` | `NUMERIC` | BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20 |
| `bias1_bfq` | `float` | `NUMERIC` | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| `bias2_bfq` | `float` | `NUMERIC` | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| `bias3_bfq` | `float` | `NUMERIC` | BIAS乖离率-CLOSE, L1=6, L2=12, L3=24 |
| `boll_lower_bfq` | `float` | `NUMERIC` | BOLL指标，布林带-CLOSE, N=20, P=2 |
| `boll_mid_bfq` | `float` | `NUMERIC` | BOLL指标，布林带-CLOSE, N=20, P=2 |
| `boll_upper_bfq` | `float` | `NUMERIC` | BOLL指标，布林带-CLOSE, N=20, P=2 |
| `brar_ar_bfq` | `float` | `NUMERIC` | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| `brar_br_bfq` | `float` | `NUMERIC` | BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26 |
| `cci_bfq` | `float` | `NUMERIC` | 顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14 |
| `cr_bfq` | `float` | `NUMERIC` | CR价格动量指标-CLOSE, HIGH, LOW, N=20 |
| `dfma_dif_bfq` | `float` | `NUMERIC` | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| `dfma_difma_bfq` | `float` | `NUMERIC` | 平行线差指标-CLOSE, N1=10, N2=50, M=10 |
| `dmi_adx_bfq` | `float` | `NUMERIC` | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| `dmi_adxr_bfq` | `float` | `NUMERIC` | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| `dmi_mdi_bfq` | `float` | `NUMERIC` | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| `dmi_pdi_bfq` | `float` | `NUMERIC` | 动向指标-CLOSE, HIGH, LOW, M1=14, M2=6 |
| `downdays` | `float` | `NUMERIC` | 连跌天数 |
| `updays` | `float` | `NUMERIC` | 连涨天数 |
| `dpo_bfq` | `float` | `NUMERIC` | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| `madpo_bfq` | `float` | `NUMERIC` | 区间震荡线-CLOSE, M1=20, M2=10, M3=6 |
| `ema_bfq_10` | `float` | `NUMERIC` | 指数移动平均-N=10 |
| `ema_bfq_20` | `float` | `NUMERIC` | 指数移动平均-N=20 |
| `ema_bfq_250` | `float` | `NUMERIC` | 指数移动平均-N=250 |
| `ema_bfq_30` | `float` | `NUMERIC` | 指数移动平均-N=30 |
| `ema_bfq_5` | `float` | `NUMERIC` | 指数移动平均-N=5 |
| `ema_bfq_60` | `float` | `NUMERIC` | 指数移动平均-N=60 |
| `ema_bfq_90` | `float` | `NUMERIC` | 指数移动平均-N=90 |
| `emv_bfq` | `float` | `NUMERIC` | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| `maemv_bfq` | `float` | `NUMERIC` | 简易波动指标-HIGH, LOW, VOL, N=14, M=9 |
| `expma_12_bfq` | `float` | `NUMERIC` | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| `expma_50_bfq` | `float` | `NUMERIC` | EMA指数平均数指标-CLOSE, N1=12, N2=50 |
| `kdj_bfq` | `float` | `NUMERIC` | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| `kdj_d_bfq` | `float` | `NUMERIC` | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| `kdj_k_bfq` | `float` | `NUMERIC` | KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3 |
| `ktn_down_bfq` | `float` | `NUMERIC` | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| `ktn_mid_bfq` | `float` | `NUMERIC` | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| `ktn_upper_bfq` | `float` | `NUMERIC` | 肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10 |
| `lowdays` | `float` | `NUMERIC` | LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值 |
| `topdays` | `float` | `NUMERIC` | TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值 |
| `ma_bfq_10` | `float` | `NUMERIC` | 简单移动平均-N=10 |
| `ma_bfq_20` | `float` | `NUMERIC` | 简单移动平均-N=20 |
| `ma_bfq_250` | `float` | `NUMERIC` | 简单移动平均-N=250 |
| `ma_bfq_30` | `float` | `NUMERIC` | 简单移动平均-N=30 |
| `ma_bfq_5` | `float` | `NUMERIC` | 简单移动平均-N=5 |
| `ma_bfq_60` | `float` | `NUMERIC` | 简单移动平均-N=60 |
| `ma_bfq_90` | `float` | `NUMERIC` | 简单移动平均-N=90 |
| `macd_bfq` | `float` | `NUMERIC` | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| `macd_dea_bfq` | `float` | `NUMERIC` | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| `macd_dif_bfq` | `float` | `NUMERIC` | MACD指标-CLOSE, SHORT=12, LONG=26, M=9 |
| `mass_bfq` | `float` | `NUMERIC` | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| `ma_mass_bfq` | `float` | `NUMERIC` | 梅斯线-HIGH, LOW, N1=9, N2=25, M=6 |
| `mfi_bfq` | `float` | `NUMERIC` | MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14 |
| `mtm_bfq` | `float` | `NUMERIC` | 动量指标-CLOSE, N=12, M=6 |
| `mtmma_bfq` | `float` | `NUMERIC` | 动量指标-CLOSE, N=12, M=6 |
| `obv_bfq` | `float` | `NUMERIC` | 能量潮指标-CLOSE, VOL |
| `psy_bfq` | `float` | `NUMERIC` | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| `psyma_bfq` | `float` | `NUMERIC` | 投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6 |
| `roc_bfq` | `float` | `NUMERIC` | 变动率指标-CLOSE, N=12, M=6 |
| `maroc_bfq` | `float` | `NUMERIC` | 变动率指标-CLOSE, N=12, M=6 |
| `rsi_bfq_12` | `float` | `NUMERIC` | RSI指标-CLOSE, N=12 |
| `rsi_bfq_24` | `float` | `NUMERIC` | RSI指标-CLOSE, N=24 |
| `rsi_bfq_6` | `float` | `NUMERIC` | RSI指标-CLOSE, N=6 |
| `taq_down_bfq` | `float` | `NUMERIC` | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| `taq_mid_bfq` | `float` | `NUMERIC` | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| `taq_up_bfq` | `float` | `NUMERIC` | 唐安奇通道(海龟)交易指标-HIGH, LOW, 20 |
| `trix_bfq` | `float` | `NUMERIC` | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| `trma_bfq` | `float` | `NUMERIC` | 三重指数平滑平均线-CLOSE, M1=12, M2=20 |
| `vr_bfq` | `float` | `NUMERIC` | VR容量比率-CLOSE, VOL, M1=26 |
| `wr_bfq` | `float` | `NUMERIC` | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| `wr1_bfq` | `float` | `NUMERIC` | W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6 |
| `xsii_td1_bfq` | `float` | `NUMERIC` | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| `xsii_td2_bfq` | `float` | `NUMERIC` | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| `xsii_td3_bfq` | `float` | `NUMERIC` | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |
| `xsii_td4_bfq` | `float` | `NUMERIC` | 薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7 |

## 系统字段

| 字段 | PostgreSQL 类型 | 说明 |
|---|---|---|
| `_record_hash` | `CHAR(64)` | 原始 payload 的 SHA-256 技术主键 |
| `_request_hash` | `CHAR(64)` | 去除分页参数后的请求 SHA-256 |
| `_source_doc_id` | `INTEGER` | Tushare 官方文档编号 |
| `_source_collected_at` | `TIMESTAMPTZ` | 原始数据采集时间 |
| `_first_seen_at` | `TIMESTAMPTZ` | 首次标准化时间 |
| `_last_seen_at` | `TIMESTAMPTZ` | 最近一次标准化时间 |
| `_schema_version` | `INTEGER` | 标准化契约版本 |
| `_extra_payload` | `JSONB` | 契约外字段，保留且触发 Schema Drift |

## 稳定性契约

- 原始记录先提交，标准化失败不会造成上游响应丢失。
- 同一 payload 使用 `_record_hash` 幂等 UPSERT，重复采集只更新最近观测时间。
- 契约外字段完整保存在 `_extra_payload` 并登记 Schema Drift。
- 类型转换失败的整行进入隔离表，修复契约后可以从原始层重放。
- 未经确认的业务键不会被猜测成唯一约束；当前主键是可验证的技术主键。
- `contract_reviewed` 接口的 REST 查询使用 `tushare_current_*` 视图；原始标准表仍保留全部版本。
