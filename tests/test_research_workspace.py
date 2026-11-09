"""Research navigation, independent panels and calculation reuse regressions."""

from datetime import date, timedelta
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="Node required")
def test_workspace_panels_refresh_and_stale_selection():
    script = r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const source=fs.readFileSync('service/dashboard/dashboard.js','utf8');
const extract=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b));
let notices=[],renders=0,requests=[],overviewCalls=0,stockCalls=0;
const nodes={};
const context={state:{activeView:'stock'},document:{hidden:false},
 $:id=>nodes[id]||(nodes[id]={innerHTML:'',classList:{toggle(){}}}),
 notice:s=>notices.push(s),loadOverview:async()=>overviewCalls++,
 fetchStockResearch:async()=>stockCalls++,
 api:path=>new Promise((resolve,reject)=>requests.push({path,resolve,reject}))};
vm.createContext(context);
vm.runInContext(extract('function pagePath(', 'function pageFromURL('),context);
vm.runInContext(extract('const workspaces=','renderWorkspaceNav("overview");'),context);
vm.runInContext(extract('async function loadResearchPanels(','async function selectMarketIndex('),context);
vm.runInContext(extract('async function refresh(','// ===== 盘中观察'),context);
(async()=>{
 context.renderWorkspaceNav('calendar');
 assert(nodes.primaryNavigation.innerHTML.includes('href="/dashboard/calendar"'));
 assert(nodes.primaryNavigation.innerHTML.includes('aria-current="page"'));
 assert(nodes.workspaceNavigation.innerHTML.includes('覆盖审计'));
 await context.refresh();assert.equal(stockCalls,1);assert.equal(overviewCalls,0);
 await context.refresh({background:true});assert.equal(stockCalls,1);
 let view={};
 const first=context.loadResearchPanels(view,{response:'chart',valuation:'valuation'},()=>renders++,'test');
 requests[0].resolve({code:'old'});await new Promise(setImmediate);
 assert.equal(renders,1); // Chart renders before optional panel completes.
 requests[1].reject(new Error('offline'));await first;
 assert.equal(view.response.code,'old');assert(notices.some(s=>s.includes('估值')));
 const old=context.loadResearchPanels(view,{response:'old'},()=>renders++,'test');
 const latest=context.loadResearchPanels(view,{response:'latest'},()=>renders++,'test');
 requests[3].resolve({code:'latest'});await latest;
 requests[2].resolve({code:'stale'});await old;
 assert.equal(view.response.code,'latest');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parents[1], check=True)


def test_reused_daily_indicator_packs_are_numerically_identical():
    from service.research.service import (
        _timeframe_analysis, _common_indicator_pack, _parameterized_indicator_pack,
    )
    rows = [dict(trade_date=date(2024, 1, 1) + timedelta(days=i),
                 open=10+i*.03, high=11+i*.03, low=9+i*.03,
                 close=10.5+i*.03, vol=1000+i, amount=10000+i)
            for i in range(270)]
    o,h,l,c,v = ([row[key] for row in rows] for key in ("open","high","low","close","vol"))
    expected = _timeframe_analysis(rows, timeframe="1d", chart_points=120)
    actual = _timeframe_analysis(
        rows, timeframe="1d", chart_points=120,
        common_indicators=_common_indicator_pack(h,l,c,v),
        parameterized_indicators=_parameterized_indicator_pack(o,h,l,c,v,timeframe="1d"),
    )
    assert actual == expected


def test_instrument_cache_separates_semantic_parameters():
    from service.api.routers.research import instrument_technicals, _INSTRUMENT_TECHNICALS_CACHE
    class Service:
        calls = 0
        def instrument_technicals(self, *args, **kwargs):
            self.calls += 1
            return {"call":self.calls}
    service = Service()
    _INSTRUMENT_TECHNICALS_CACHE.clear()
    args = dict(asset_type="index",code="000001.SH",service=service,
                lookback_days=1200,chart_points=180,benchmark=None,provider=None,as_of=date(2026,10,29))
    try:
        first=instrument_technicals(**args)
        assert instrument_technicals(**args)==first
        for change in ({"as_of":date(2026,10,30)},{"provider":"ths"},{"asset_type":"stock"},{"chart_points":250}):
            assert instrument_technicals(**(args|change))!=first
        assert service.calls==5
    finally:
        _INSTRUMENT_TECHNICALS_CACHE.clear()
