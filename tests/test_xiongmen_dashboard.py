"""Execute chart renderers to catch null-to-zero scaling and daily-only regressions."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required for chart regression')
def test_xiongmen_chart_toggles_markers_and_missing_values():
    root = Path(__file__).resolve().parents[1]
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('service/dashboard/dashboard.js','utf8');
const svg={innerHTML:'',querySelector:()=>({})};
const ctx={state:{stock:{timeframe:'1d',overlays:new Set(['xiongmen']),drag:{}}},$:()=>svg,esc:String};
vm.createContext(ctx);
vm.runInContext(src.slice(src.indexOf('const stockLineDefinitions='),src.indexOf('function stockVolumeScale(')),ctx);
vm.runInContext(src.slice(src.indexOf('function stockPath('),src.indexOf('function stockLeaveCrosshair(')),ctx);
const points=[
 {trade_date:'2026-01-01',open:100,high:102,low:99,close:101,xiongmen_line:null},
 {trade_date:'2026-01-02',open:101,high:103,low:100,close:102,xiongmen_line:97,xiongmen_reduction_signal:'减二',xiongmen_marker_price:107.1}
];
ctx.renderStockPriceChart(points);
assert(svg.innerHTML.includes('减二'));
assert(!svg.innerHTML.includes('NaN'));
assert(ctx.state.stock.priceScale.min>90,'null must not become zero in price domain');
assert(ctx.state.stock.priceScale.max>107.1,'marker must fit chart');
assert(!ctx.stockActiveLines().includes('xiongmen_bear_entry_line'));
assert.equal(ctx.stockPath(points,'xiongmen_line',i=>i,v=>v),'M1.00,97.00');
ctx.state.stock.overlays.add('xiongmen_bear_entry_line');
assert(ctx.stockActiveLines().includes('xiongmen_bear_entry_line'));
ctx.state.stock.timeframe='1w';ctx.renderStockPriceChart(points);
assert.equal(ctx.stockActiveLines().length,0);
assert(!svg.innerHTML.includes('减二'));
ctx.state.stock.timeframe='1d';ctx.state.stock.overlays.clear();ctx.renderStockPriceChart(points);
assert(!svg.innerHTML.includes('减二'));
assert(ctx.xiongmenTooltip({xiongmen_bear_state:false,xiongmen_sample_count:0}).includes('—'));
vm.runInContext(src.slice(src.indexOf('const researchMA='),src.indexOf('function renderResearchVolume(')),ctx);
ctx.renderResearchCandles('marketPriceChart',points,{overlays:['xiongmen_line'],showXiongmen:true});
assert(svg.innerHTML.includes('减二'));
assert(!svg.innerHTML.includes('NaN'));
ctx.renderResearchCandles('marketPriceChart',points,{overlays:[],showXiongmen:false});
assert(!svg.innerHTML.includes('减二'));
'''
    subprocess.run(['node', '-e', script], cwd=root, check=True, capture_output=True, text=True)
