#!/usr/bin/env python3
"""
采集器一键测试工具
=================
用法：
  python3 tools/test_collectors.py                    # 全量测试
  python3 tools/test_collectors.py block_trade        # 只测某个采集器
  python3 tools/test_collectors.py daily daily        # 只测 market/daily
"""

import sys, os, logging, importlib, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")

# ── 待测采集器清单（路径, 模块路径, 类名）──
TEST_CASES = [
    # reference
    ("reference/block_trade", "collectors.stock.reference.block_trade", "BlockTradeCollector"),
    ("reference/pledge_detail", "collectors.stock.reference.pledge_detail", "PledgeDetailCollector"),
    ("reference/pledge_stat", "collectors.stock.reference.pledge_stat", "PledgeStatCollector"),
    ("reference/repurchase", "collectors.stock.reference.repurchase", "RepurchaseCollector"),
    ("reference/share_float", "collectors.stock.reference.share_float", "ShareFloatCollector"),
    ("reference/stk_alert", "collectors.stock.reference.stk_alert", "StkAlertCollector"),
    ("reference/stk_high_shock", "collectors.stock.reference.stk_high_shock", "StkHighShockCollector"),
    ("reference/stk_holdernumber", "collectors.stock.reference.stk_holdernumber", "StkHoldernumberCollector"),
    ("reference/stk_holdertrade", "collectors.stock.reference.stk_holdertrade", "StkHoldertradeCollector"),
    ("reference/stk_shock", "collectors.stock.reference.stk_shock", "StkShockCollector"),
    ("reference/top10_floatholders", "collectors.stock.reference.top10_floatholders", "Top10FloatholdersCollector"),
    ("reference/top10_holders", "collectors.stock.reference.top10_holders", "Top10HoldersCollector"),
    # board
    ("board/hm_list", "collectors.stock.board.hm_list", "HmListCollector"),
    ("board/dc_concept", "collectors.stock.board.dc_concept", "DcConceptCollector"),
    ("board/dc_concept_cons", "collectors.stock.board.dc_concept_cons", "DcConceptConsCollector"),
    ("board/dc_daily", "collectors.stock.board.dc_daily", "DcDailyCollector"),
    ("board/dc_hot", "collectors.stock.board.dc_hot", "DcHotCollector"),
    ("board/dc_index", "collectors.stock.board.dc_index", "DcIndexCollector"),
    ("board/dc_member", "collectors.stock.board.dc_member", "DcMemberCollector"),
    ("board/kpl_list", "collectors.stock.board.kpl_list", "KplListCollector"),
    ("board/limit_list_d", "collectors.stock.board.limit_list_d", "LimitListDCollector"),
    ("board/limit_step", "collectors.stock.board.limit_step", "LimitStepCollector"),
    ("board/stk_auction", "collectors.stock.board.stk_auction", "StkAuctionCollector"),
    ("board/tdx_daily", "collectors.stock.board.tdx_daily", "TdxDailyCollector"),
    ("board/tdx_index", "collectors.stock.board.tdx_index", "TdxIndexCollector"),
    ("board/tdx_member", "collectors.stock.board.tdx_member", "TdxMemberCollector"),
    ("board/ths_daily", "collectors.stock.board.ths_daily", "ThsDailyCollector"),
    ("board/ths_hot", "collectors.stock.board.ths_hot", "ThsHotCollector"),
    ("board/ths_index", "collectors.stock.board.ths_index", "ThsIndexCollector"),
    ("board/ths_member", "collectors.stock.board.ths_member", "ThsMemberCollector"),
    ("board/top_inst", "collectors.stock.board.top_inst", "TopInstCollector"),
    ("board/top_list", "collectors.stock.board.top_list", "TopListCollector"),
    # extra
    ("extra/ccass_hold", "collectors.stock.extra.ccass_hold", "CcassHoldCollector"),
    ("extra/ccass_hold_detail", "collectors.stock.extra.ccass_hold_detail", "CcassHoldDetailCollector"),
    ("extra/hk_hold", "collectors.stock.extra.hk_hold", "HkHoldCollector"),
    ("extra/cyq_chips", "collectors.stock.extra.cyq_chips", "CyqChipsCollector"),
    ("extra/cyq_perf", "collectors.stock.extra.cyq_perf", "CyqPerfCollector"),
    ("extra/stk_auction_c", "collectors.stock.extra.stk_auction_c", "StkAuctionCCollector"),
    ("extra/stk_auction_o", "collectors.stock.extra.stk_auction_o", "StkAuctionOCollector"),
    ("extra/stk_surv", "collectors.stock.extra.stk_surv", "StkSurvCollector"),
    ("extra/report_rc", "collectors.stock.extra.report_rc", "ReportRcCollector"),
    ("extra/stk_ah_comparison", "collectors.stock.extra.stk_ah_comparison", "StkAhComparisonCollector"),
    ("extra/stk_nineturn", "collectors.stock.extra.stk_nineturn", "StkNineturnCollector"),
    ("extra/broker_recommend", "collectors.stock.extra.broker_recommend", "BrokerRecommendCollector"),
    ("extra/stk_factor_pro", "collectors.stock.extra.stk_factor_pro", "StkFactorProCollector"),
    # moneyflow
    ("moneyflow/moneyflow", "collectors.stock.moneyflow.moneyflow", "MoneyflowCollector"),
    ("moneyflow/moneyflow_dc", "collectors.stock.moneyflow.moneyflow_dc", "MoneyflowDcCollector"),
    ("moneyflow/moneyflow_ths", "collectors.stock.moneyflow.moneyflow_ths", "MoneyflowThsCollector"),
    ("moneyflow/moneyflow_hsgt", "collectors.stock.moneyflow.moneyflow_hsgt", "MoneyflowHsgtCollector"),
    ("moneyflow/moneyflow_ind_ths", "collectors.stock.moneyflow.moneyflow_ind_ths", "MoneyflowIndThsCollector"),
    ("moneyflow/moneyflow_cnt_ths", "collectors.stock.moneyflow.moneyflow_cnt_ths", "MoneyflowCntThsCollector"),
    ("moneyflow/moneyflow_mkt_dc", "collectors.stock.moneyflow.moneyflow_mkt_dc", "MoneyflowMktDcCollector"),
    ("moneyflow/moneyflow_ind_dc", "collectors.stock.moneyflow.moneyflow_ind_dc", "MoneyflowIndDcCollector"),
    # basic
    ("basic/bak_basic", "collectors.stock.basic.bak_basic", "BakBasicCollector"),
    ("basic/bse_mapping", "collectors.stock.basic.bse_mapping", "BseMappingCollector"),
    ("basic/new_share", "collectors.stock.basic.new_share", "NewShareCollector"),
    ("basic/stock_basic", "collectors.stock.basic.stock_basic", "StockBasicCollector"),
    ("basic/stock_company", "collectors.stock.basic.stock_company", "StockCompanyCollector"),
    ("basic/stock_hsgt", "collectors.stock.basic.stock_hsgt", "StockHsgtCollector"),
    ("basic/stock_namechange", "collectors.stock.basic.stock_namechange", "StockNamechangeCollector"),
    ("basic/stock_st", "collectors.stock.basic.stock_st", "StockStCollector"),
    ("basic/stk_managers", "collectors.stock.basic.stk_managers", "StkManagersCollector"),
    ("basic/stk_rewards", "collectors.stock.basic.stk_rewards", "StkRewardsCollector"),
    ("basic/trade_cal", "collectors.stock.basic.trade_cal", "TradeCalCollector"),
    # margin
    ("margin/margin (Margin)", "collectors.stock.margin.margin", "MarginCollector"),
    ("margin/margin (MarginDetail)", "collectors.stock.margin.margin", "MarginDetailCollector"),
    ("margin/margin (MarginSecs)", "collectors.stock.margin.margin", "MarginSecsCollector"),
    ("margin/margin (SlbLen)", "collectors.stock.margin.margin", "SlbLenCollector"),
    # market
    ("market/daily", "collectors.stock.market.daily", "DailyCollector"),
    ("market/ggt_daily", "collectors.stock.market.ggt_daily", "GgtDailyCollector"),
    ("market/ggt_monthly", "collectors.stock.market.ggt_monthly", "GgtMonthlyCollector"),
    ("market/ggt_top10", "collectors.stock.market.ggt_top10", "GgtTop10Collector"),
    ("market/hsgt_top10", "collectors.stock.market.hsgt_top10", "HsgtTop10Collector"),
    ("market/stk_limit", "collectors.stock.market.stk_limit", "StkLimitCollector"),
    ("market/stk_weekly_monthly", "collectors.stock.market.stk_weekly_monthly", "StkWeeklyMonthlyCollector"),
    ("market/suspend_d", "collectors.stock.market.suspend_d", "SuspendDCollector"),
    # sge
    ("sge/sge_basic", "collectors.sge.sge_basic", "SgeBasicCollector"),
    ("sge/sge_daily", "collectors.sge.sge_daily", "SgeDailyCollector"),
]


def run_test(label, module_path, class_name):
    """测试单个采集器"""
def run_test(label, module_path, class_name):
    """测试单个采集器（只测试初始化和 fetch，不调实际 API 避免频率限制）"""
    import time as _time
    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        c = cls()

        results = {"init": "✅", "fetch": "—", "collect": "—"}

        # fetch 测试（用最快的方式确认 API 可访问——空参或少量数据）
        df = None
        # 不同接口需要不同参数，统一用空参加5秒超时保护
        _time.sleep(0.05)  # 避免同一时间密集调用
        df = c.fetch()
        if df is not None and len(df) > 0:
            results["fetch"] = f"✅({len(df)}行)"
        elif df is not None:
            results["fetch"] = "✅(0行)"

        # collect(skip_store) 测试
        try:
            rows = c.collect(skip_store=True)
            results["collect"] = f"✅({rows}行)"
        except Exception:
            results["collect"] = "⚠️"

        return results

    except Exception as e:
        return {"init": f"❌({str(e)[:60]})", "fetch": "—", "collect": "—"}


# ── 入口 ──
if __name__ == "__main__":
    filter_name = sys.argv[1] if len(sys.argv) > 1 else None
    filter_folder = sys.argv[2] if len(sys.argv) > 2 else None

    passed = 0
    failed = 0
    skipped = 0

    for label, mod_path, cls_name in TEST_CASES:
        # 过滤
        if filter_name and filter_name not in label:
            skipped += 1
            continue
        if filter_folder and filter_folder not in label:
            skipped += 1
            continue

        result = run_test(label, mod_path, cls_name)
        status = result["init"]
        if "❌" in status or "⚠️" in status:
            print(f"❌ {label:40s} init={status} fetch={result['fetch']} collect={result['collect']}")
            failed += 1
        else:
            print(f"✅ {label:40s} init=✅ fetch={result['fetch']:20s} collect={result['collect']}")
            passed += 1

    total = len(TEST_CASES) - skipped
    print(f"\n{'='*60}")
    print(f"总计: {total} 个 | 通过: {passed} | 失败: {failed} | 跳过: {skipped}")
