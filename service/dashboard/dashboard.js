const $ = (id) => document.getElementById(id);
const state = { factors: null, execution: { page: 1, size: 50, before: null, history: [], next: null, total: 0 }, tasks: { page: 1, size: 30, items: null }, today: { page: 1, size: 20, items: [] }, calendar: { page: 1, size: 20, items: [], issues: new Map(), day: null }, services: { page: 1, size: 20, items: null }, interfaces: { page: 1, size: 50, items: null, runtimeAvailable: true, viewMode: "table", expanded: null, detailCache: new Map(), lineage: null, lineagePage: 1, lineageSize: 15 }, derivations: { items: null, runtimeAvailable: true, coverageAvailable: true, summary: null, expanded: null, page: 1, size: 20, ondemand: null, ondemandPage: 1, ondemandSize: 20 }, stock: { selected: null, response: null, timeframe: "1d", overlays: new Set(["ma_20","ma_60","cost_20","cost_60","niumen_line","niumen_confirmation_line"]), viewport: { timeframe: null, total: 0, start: 0, count: 0 }, selectedTradeDate: null, hoverIndex: null, subCharts: ["volume","macd"], _view: null, priceScale: null, searchTimer: null, watchlist: [], watchlistLoaded: false, watchlistBusy: false, requestVersion: 0, module: "market", modules: {}, moduleBusy: {}, drag: { active: false, moved: false, startX: 0, startIndex: 0, pointerId: null } }, initId: null, research: { market: { selected: null, response: null, valuation: null, funds: null, tab: "valuation" }, etf: { items: null, selected: null, response: null, nav: null, tab: "quotes", sort: { key: "amount", dir: -1 }, flow: { loaded: false, series: [], basket: [], signals: [], meta: {}, selectedCodes: null, window: 60, selectedDate: null, _view: null } }, sector: { source: "ths", items: null, selected: null, response: null, members: null, sort: { key: "pct_change", dir: -1 } }, macro: { tab: "regime", loaded: {}, data: {} } } };
state.intraday={response:null,busy:false};
const labels = {queued:"排队",scheduled:"已预约",running:"运行",retrying:"重试",validating:"校验",publishing:"发布",success:"成功",attention:"需处理",historical_attention:"历史失败",superseded:"已被后续成功替代",cancelled:"已取消",not_dispatched:"未派发",not_due:"尚未到调度或发布时间",not_expected:"非交易日无需执行",complete:"完整",empty_verified:"已验证为空",gaps:"缺失",partial:"不完整",indeterminate:"待确认",ready:"严格就绪",ready_after_repair:"补采恢复",active:"进行中",waiting_upstream:"等待上游",operator_action_required:"需要处理",present:"审计通过",observed_only:"已有数据",missing:"缺失",pending:"待核验",acquisition:"原生采集",transformation:"派生计算",draft:"草稿",retired:"已停用"};
const fmt = (v) => Number(v || 0).toLocaleString();
const esc = (v) => String(v ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pill = (v) => `<span class="pill ${esc(v)}">${esc(labels[v] || v)}</span>`;
const isoDate = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const monthValue = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;

async function api(path, options={}) {
  const controller = new AbortController();
  const timeout = setTimeout(()=>controller.abort(), 90000);
  try {
    const response = await fetch(path, {...options, signal:options.signal||controller.signal});
    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try { const body = await response.json(); message = body.error?.message || body.detail || message; } catch (_) {}
      throw new Error(message);
    }
    const result=await response.json();
    if((state.activeView||"overview")!=="overview")$("updatedAt").textContent=`最近响应 ${new Date().toLocaleTimeString("zh-CN")}`;
    return result;
  }catch(error) { throw new Error(error.name==="AbortError" ? "请求超过 90 秒，请稍后点击刷新重试" : error instanceof TypeError ? "连接中断或服务暂不可用，请点击刷新重试" : error.message); }
  finally { clearTimeout(timeout); }
}

// Chart redraws are expensive (three SVGs, up to 1500 bars).  Pan, zoom and
// wheel events can fire dozens of times per second, so collapse them into one
// paint per animation frame.
const rafSchedule=(()=>{const pending=new Map();return (key,fn)=>{if(pending.has(key))return;pending.set(key,requestAnimationFrame(()=>{pending.delete(key);fn();}));};})();
function scheduleStockRender(){
  rafSchedule("stock",()=>{if(state.stock.response)renderStockResearch();});
}
function notice(message) { $("notice").textContent=message; $("notice").classList.toggle("hidden",!message); }
const workspaces=[
  {title:"运营总览",icon:"⌂",views:[["overview","运营总览"]]},
  {title:"研究工作台",icon:"⌁",views:[["stock","个股"],["market","大盘"],["etf","ETF"],["sector","板块"],["macro","宏观"],["intraday","盘中观察"],["factors","量化因子"]]},
  {title:"投资日历",icon:"☆",views:[["investment","投资日历"]]},
  {title:"数据健康",icon:"✓",views:[["today","今日交付"],["calendar","数据日历"],["coverage","覆盖审计"]],hint:"以数据日期与校验结果为准，任务成功不等于数据完整。"},
  {title:"任务中心",icon:"⌘",views:[["tasks","任务定义"],["executions","执行实例"],["derivations","派生加工"]],hint:"查看执行方式、节点和实例状态；数据是否就绪请查看数据健康。"},
  {title:"数据服务",icon:"◇",views:[["services","对外服务"],["sources","来源与依赖"]]},
  {title:"审计中心",icon:"◎",views:[["usage","供应商调用审计"]]},
];
function renderWorkspaceNav(name){
  const group=workspaces.find(g=>g.views.some(([key])=>key===name));
  const mainLink=g=>`<a class="nav ${g===group?"active":""}" href="${pagePath(g.views[0][0])}" title="${g.title}"><span>${g.icon}</span><b>${g.title}</b></a>`;
  $("primaryNavigation").innerHTML=workspaces.map(g=>g.views.length===1?mainLink(g):`<details class="nav-tree" ${g===group?"open":""}><summary class="nav" title="${g.title}"><span>${g.icon}</span><b>${g.title}</b></summary><div class="nav-children">${g.views.map(([k,label])=>`<a href="${pagePath(k)}" title="${label}" ${k===name?'aria-current="page"':""}>${label}</a>`).join("")}</div></details>`).join("");
  const secondary=$("workspaceNavigation");
  secondary.classList.toggle("hidden",!group||group.views.length<2);
  secondary.innerHTML=group?`<div class="workspace-tabs">${group.views.map(([key,label])=>`<button data-view-target="${key}" class="${name===key?"active":""}" ${name===key?'aria-current="page"':""}>${label}</button>`).join("")}</div>${group.hint?`<p>${group.hint}</p>`:""}`:"";
}
renderWorkspaceNav("overview");
$("stockHistory").onchange=()=>fetchStockResearch();
$("stockPoints").onchange=()=>{state.stock.viewport.count=0;scheduleStockRender();};
$("taskSource").onchange=()=>{state.tasks.page=1;renderTaskRows();};
$("taskAssetClass").onchange=()=>{state.tasks.page=1;renderTaskRows();};
function pagePath(name){return name==="overview"?"/dashboard":"/dashboard/"+name;}
function pageFromURL(){return location.pathname.replace(/\/$/,"").split("/")[2]||"overview";}
window.addEventListener("popstate",()=>activate(pageFromURL(), false));
function activate(name, navigate=true) {
  if(navigate && location.pathname!==pagePath(name))history.pushState(null,"",pagePath(name));
  state.activeView=name;
  if(name==="overview")void refresh();
  renderWorkspaceNav(name);
  document.querySelectorAll("[data-panel]").forEach(x=>x.classList.toggle("hidden",x.dataset.panel!==name));
  const names={overview:"数据运营总览",today:"今日交付",intraday:"盘中观察",stock:"个股研究",market:"大盘研究",etf:"ETF 研究",sector:"板块研究",macro:"宏观研究",factors:"量化因子目录",tasks:"采集任务",executions:"执行历史",calendar:"数据日历",coverage:"覆盖审计",initialization:"数据初始化",usage:"供应商调用审计",sources:"数据依赖",derivations:"数据派生",services:"对外服务目录",investment:"投资日历"};
  $("pageTitle").textContent=names[name];
  ({today:loadToday,intraday:loadIntraday,stock:loadStockResearch,market:loadMarketResearch,etf:loadEtfResearch,sector:loadSectorResearch,macro:loadMacroResearch,factors:loadFactors,tasks:loadTasks,executions:loadExecutions,calendar:loadCalendar,coverage:loadCoverage,initialization:loadInitialization,usage:loadProviderUsage,sources:loadSources,derivations:loadDerivations,services:loadServices,investment:loadInvestment}[name]||(()=>{}))();
}

async function loadOverview(force=false) {
  const system = await api(`/api/v1/system/overview${force?"?refresh=true":""}`);
  const health = {status:system.runtime.status,summary:system.runtime.summary,issues:system.runtime.issues,generated_at:system.runtime.generated_at};
  const inventory=system.inventory;
  $("systemStatement").textContent=system.positioning.statement;
  $("systemContractVersion").textContent=system.schema_version.split("/").at(-1);
  $("systemTushareCount").textContent=fmt(inventory.tushare.collectable_contracts);
  $("systemDatasetCount").textContent=fmt(inventory.public_services.standard_datasets);
  $("systemResearchCount").textContent=fmt(inventory.public_services.research_endpoints);
  $("systemEvidenceCount").textContent=fmt(inventory.financial_data.research_evidence_routes);
  $("systemArchitecture").innerHTML=system.architecture.map(x=>`<article><span>${esc(x.order)}</span><div><strong>${esc(x.title)}</strong><p>${esc(x.description)}</p></div></article>`).join("");
  $("systemNumberDefinitions").innerHTML=system.number_definitions.map(x=>`<div><b>${fmt(x.value)}</b><span><strong>${esc(x.name)}</strong><small>${esc(x.meaning)}</small></span></div>`).join("");
  $("systemBoundaries").innerHTML=system.boundaries.map(x=>`<li>${esc(x)}</li>`).join("");
  const s=health.summary;
  const readyRate=s.latest_dataset_states?Math.round(s.ready_dataset_states*1000/s.latest_dataset_states)/10:100;
  $("metricActive").textContent=fmt(s.active_task_instances); $("metricAttention").textContent=fmt(s.open_issues);
  $("metricReady").textContent=`${fmt(s.ready_dataset_states)} / ${fmt(s.latest_dataset_states)}`; $("metricMissing").textContent=`${fmt(s.missing_partitions)} / ${fmt(s.partial_partitions)}`;
  $("metricReadyHint").textContent=s.not_expected_dataset_states?`另有 ${fmt(s.not_expected_dataset_states)} 个当前不应产出`:`只统计当前应产出的数据`;
  const banner=$("healthBanner"); banner.className=`health-banner ${health.status}`;
  const headline=health.status==="healthy"?"数据链路健康":s.operator_action_required?`${fmt(s.operator_action_required)} 个问题需要处理`:s.waiting_upstream?`数据主体可用，${fmt(s.waiting_upstream)} 个数据集等待上游`:s.active_task_instances?`数据主体可用，${fmt(s.active_task_instances)} 个任务处于自动执行队列`:"数据主体可用";
  $("healthKicker").textContent=health.status==="healthy"?"全部正常":s.operator_action_required?"需要处理":s.active_task_instances?"自动执行中":"数据已就绪";
  $("healthTitle").textContent=headline;
  $("healthSummary").textContent=`最新状态 ${s.ready_dataset_states}/${s.latest_dataset_states} 已就绪；当前 ${s.open_issues} 个问题，历史重试尝试 ${s.attention_attempts} 次。尝试次数不再当作问题数。`;
  $("readinessRate").textContent=`${readyRate}%`;
  $("flowExecution").textContent=s.operator_action_required?`${s.operator_action_required} 个需要处理`:s.active_task_instances?`${s.active_task_instances} 个活动范围`:"调度正常";
  $("flowExecutionHint").textContent=s.active_task_instances?`运行 ${fmt(s.running_task_instances)} · 排队 ${fmt(s.queued_task_instances)} · 延后/重试 ${fmt(s.retrying_task_instances)} · 等待依赖 ${fmt(s.waiting_dependency_task_instances)}`:`执行历史保留 ${fmt(s.attention_attempts)} 次异常尝试`;
  $("flowValidation").textContent=s.not_ready_dataset_states?`${s.not_ready_dataset_states} 个未通过`:`${s.latest_dataset_states} 个全部通过`;
  $("flowValidationHint").textContent=`历史累计缺失 ${fmt(s.missing_partitions)} · 不完整 ${fmt(s.partial_partitions)}`;
  $("flowDelivery").textContent=s.not_ready_dataset_states?"已限制未就绪数据":"服务数据已就绪";
  $("flowDeliveryHint").textContent=`${fmt(s.ready_dataset_states)} 个最新数据状态可供服务读取`;
  $("issueCount").textContent=fmt(s.open_issues);
  const external=health.issues.filter(x=>x.dataset?.startsWith("ant_")&&x.error_category==="rate_limited");
  const otherIssues=health.issues.filter(x=>!external.includes(x));
  const issueHtml=x=>{
    const ratio=x.completeness_ratio==null?"—":`${Math.round(x.completeness_ratio*1000)/10}%`;
    const quantityLabel=x.kind==="historical_coverage_gap"?"历史周期覆盖":"实体完整度";
    const progress=x.security_progress, following=x.following_scope;
    const quantity=(x.expected_count==null?"":`<span>${quantityLabel} ${fmt(x.actual_count)} / ${fmt(x.expected_count)}（${ratio}）</span>`) + (progress?.expected_pairs!=null && progress.dates_with_denominator===progress.audited_partial_dates
      ? `<span>未齐日期的证券日：已见 ${fmt(progress.observed_pairs)} / 应有 ${fmt(progress.expected_pairs)} · 尚缺 ${fmt(progress.expected_pairs-progress.observed_pairs)}；不代表价格档位完整</span><span>其中 ${fmt(progress.dates_without_active_window)} 个日期没有活动补采区间 · 最近审计 ${esc(new Date(progress.last_checked_at).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai"}))}</span>`:"")
      + (following?`<span>后续周期最早可领取：${esc(new Date(following.eligible_at).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai"}))}</span>`:"");
    const next=x.next_automatic_repair_at?`<span>下次自动复查 ${new Date(x.next_automatic_repair_at).toLocaleString("zh-CN",{hour12:false})}</span>`:"";
    const explanation=x.action||(x.resolution_state==="waiting_upstream"?"最近一次采集已成功，但上游尚未发布完整截面；系统会按限定范围自动复查。":"数据校验未通过，需要检查来源执行并做范围补采。");
    const coverageAction=x.kind==="historical_coverage_gap"?'<button data-view-target="coverage">查看覆盖审计</button>':"";
    const segments=(x.active_recovery_segments||[]).map(s=>`<div>正在恢复 ${esc(s.observation_start)} → ${esc(s.observation_end)} · ${pill(s.status)} ${s.task_execution_id?`<button data-execution="${s.task_execution_id}">查看补采 #${s.task_execution_id}</button>`:""}</div>`).join("");
    const inputs=(x.input_issues||[]).map(i=>`<li><code>${esc(i.factor)}</code>：${fmt(i.affected_securities)} 只证券 · ${esc(i.reason)}</li>`).join("");
    return `<div class="issue ${x.severity}"><div><div class="issue-title"><strong>${esc(x.dataset)}</strong>${pill(x.resolution_state)}<span>${esc(x.observation_key)}</span></div><div class="issue-meta"><span>${esc(explanation)}</span>${quantity}${next}${segments}</div>${inputs?`<details><summary>查看主要输入缺口（证券数不能相加）</summary><ul>${inputs}</ul></details>`:""}</div><div class="issue-actions">${x.source_execution_id?`<button data-execution="${x.source_execution_id}">查看最近尝试</button>`:""}${coverageAction}</div></div>`;
  };
  const providerIssue=external.length?`<details class="issue-group" open><summary>Financial Data 上游限流（HTTP 429） · 影响 ${external.length} 个数据集</summary><p>这些数据仍不可用，并非已修复。请核对提供方额度或限流政策；不要连续点击重试。下列实例保留各自的失败证据。</p>${external.map(issueHtml).join("")}</details>`:"";
  $("issueList").innerHTML=health.issues.length?otherIssues.map(issueHtml).join("")+providerIssue:'<div class="empty-state">最新交付没有问题；全历史覆盖义务以“覆盖审计”为准。</div>';
  const stamp = new Date(health.generated_at), expired = Date.now()-stamp.getTime()>120000;
  $("updatedAt").textContent=`运营数据截至 ${stamp.toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false})} 上海时间${expired?" · 已过期":""}`;
  if(expired){$("healthKicker").textContent="旧快照";$("healthSummary").textContent="以下为历史状态，请刷新后再作判断。";}
}

function renderTodayRows(){
  const status=$("todayStatus").value,query=$("todaySearch").value.trim().toLowerCase();
  const items=state.today.items.filter(x=>(!status||x.delivery_status===status)&&(!query||[x.task_key,...(x.output_datasets||[]),x.delivery_status,x.execution_status,x.current_node_key].join(" ").toLowerCase().includes(query)));
  const pages=Math.max(1,Math.ceil(items.length/state.today.size));state.today.page=Math.min(state.today.page,pages);const start=(state.today.page-1)*state.today.size,rows=items.slice(start,start+state.today.size);
  $("todayRows").innerHTML=rows.map(x=>{const displayStatus=x.not_due_reason==="non_trading_day"?"not_expected":(x.execution_status||x.status);const delivery=x.not_due_reason==="non_trading_day"?"not_expected":(x.delivery_status||"attention");const outputs=(x.output_datasets||[]).map(v=>`<span class="dataset-chip">${esc(v)}</span>`).join("");return `<tr><td><strong class="task-name">${esc(x.task_key)}</strong><small class="dataset-list"><b>产出</b>${outputs||"—"}</small></td><td>${esc(x.observation_key||$("todayDate").value)}</td><td>${pill(displayStatus)}</td><td>${esc(x.current_node_key)}</td><td>${pill(delivery)} · ${fmt(x.ready_datasets)} / ${fmt(x.datasets)}${x.problem_datasets?` · <b>${fmt(x.problem_datasets)} 异常</b>`:""}</td><td>${fmt(x.rows_written)} / ${fmt(x.rows_fetched)}</td><td>${x.task_execution_id?`<button data-execution="${x.task_execution_id}">详情</button>`:"—"}</td></tr>`;}).join("")||'<tr><td colspan="7" class="empty-row">没有匹配任务</td></tr>';
  $("todayResultCount").textContent=`${items.length} 个任务`;
  $("todayPage").textContent=`第 ${state.today.page} / ${pages} 页`;
  $("todayPrev").disabled=state.today.page===1;$("todayNext").disabled=state.today.page===pages;
}

async function loadToday() {
  const day=$("todayDate").value||isoDate(new Date());
  const view=await api(`/api/v1/ops/today?data_date=${day}`), s=view.summary;
  $("todayExpected").textContent=fmt(s.expected); $("todayReady").textContent=fmt(s.strictly_ready); $("todayActive").textContent=fmt(s.active); $("todayProblem").textContent=fmt(s.attention+s.not_dispatched);
  $("todaySummary").textContent=!view.trade_day?`${day} 为非交易日：日常交易任务不创建执行实例，因此这里为空；trade_calendar 等日历型数据可能已由此前快照覆盖，请在“数据日历”查看数据证据。系统共有 ${s.configured_daily_tasks||0} 个日频任务定义。`:`${day} 数据交付：严格就绪 ${s.strictly_ready}/${s.expected} 个已到期任务；${s.recovered||0} 个由后续补采恢复；${s.not_due||0} 个任务尚未到期或属于其他市场数据日期。任务行现在同时展示其输出数据集。`;
  state.today.items=view.items;state.today.page=1;renderTodayRows();
}

function renderTaskRows(){
  const query=$("taskSearch").value.trim().toLowerCase();
  const source=$("taskSource").value;
  const assetClass=$("taskAssetClass").value;
  const selected=new URLSearchParams(location.search).get("definition");
  const items=(state.tasks.items||[]).filter(x=>selected?String(x.task_definition_id)===selected:((!source||(source==="derived"?x.workflow_kind==="transformation":(x.source_ids||[]).includes(source)))&&(!assetClass||x.asset_class===assetClass)&&(!query||[x.task_key,...(x.source_ids||[]),...(x.input_datasets||[]),...(x.output_datasets||[])].join(" ").toLowerCase().includes(query))));
  const pages=Math.max(1,Math.ceil(items.length/state.tasks.size));state.tasks.page=Math.min(state.tasks.page,pages);const start=(state.tasks.page-1)*state.tasks.size,rows=items.slice(start,start+state.tasks.size);
  const chips=v=>{const a=v||[];return a.length?`${a.slice(0,4).map(x=>`<span class="dataset-chip">${esc(x)}</span>`).join("")}${a.length>4?`<span class="dataset-more">+${a.length-4}</span>`:""}`:"<span class=\"muted\">无</span>"};
  const lifecycleLabels={active:"定义已发布",draft:"草稿",retired:"定义已退役"};
  const cadenceLabels={daily:"每日",weekly:"每周",monthly:"每月",quarterly:"每季",dependency:"依赖触发",manual:"按需"};
  const assetClassLabels={stock:"股票",hk_stock:"港股",us_stock:"美股",fund:"基金",index_etf:"指数·ETF·板块",bond:"债券",derivatives:"期权·期货",forex:"外汇",macro:"宏观",altdata:"另类数据",info:"资讯·公告",chain:"产业链·关联",quote:"行情快照",factor:"因子库",other:"其他"};
  $("taskRows").innerHTML=rows.map(x=>`<tr><td><strong class="task-name">${esc(x.task_key)}</strong><small>${esc((x.source_ids||[]).join(" / ")||(x.workflow_kind==="transformation"?"本地派生":"来源待配置"))}${x.asset_class?` · <span class="muted">${esc(assetClassLabels[x.asset_class]||x.asset_class)}</span>`:""}</small><small><span class="pill ${esc(x.lifecycle_status)}">${esc(lifecycleLabels[x.lifecycle_status]||x.lifecycle_status)}</span></small></td><td><span class="cadence-pill">${esc(cadenceLabels[x.cadence]||x.cadence||"按需")}</span><small>${esc(x.automation?.label||"调度状态未核实")}</small></td><td>${pill(x.workflow_kind)}<small>版本 ${x.version}</small></td><td><div class="dataset-flow"><div><b>输入</b>${chips(x.input_datasets)}</div><span>→</span><div><b>输出</b>${(x.output_storage||[]).map(o=>`<small>${esc(o.dataset)} → <code>${esc(o.table||"未登记映射")}</code></small>`).join("")||"无"}</div></div></td><td><strong>${fmt(x.node_count)}</strong><small>个内部节点</small></td><td><button data-task="${x.task_definition_id}">来源 · 实例 · 验收</button></td></tr>`).join("")||'<tr><td colspan="6" class="empty-row">没有匹配任务</td></tr>';
  $("taskResultCount").innerHTML=`筛选结果 ${items.length} 个任务${selected?' · <a href="/dashboard/tasks">返回全部任务</a>':""}`;
  $("taskPage").textContent=`第 ${state.tasks.page} / ${pages} 页 · ${items.length} 个任务`;$("taskPrev").disabled=state.tasks.page===1;$("taskNext").disabled=state.tasks.page===pages;
}
async function loadTasks(reset=false){
  if(reset)state.tasks={page:1,size:30,items:null};
  const requestedState=state.tasks;
  if(!requestedState.items){
    const p=new URLSearchParams({limit:"200"}),items=[],seenCursors=new Set();
    if($("taskCadence").value)p.set("cadence",$("taskCadence").value);
    if($("taskKind").value)p.set("workflow_kind",$("taskKind").value);
    if($("taskLifecycle").value)p.set("lifecycle_status",$("taskLifecycle").value);
    while(true){
      const view=await api(`/api/v1/ops/tasks?${p}`);
      if(state.tasks!==requestedState)return;
      items.push(...view.items);
      const next=view.page?.next_cursor;
      if(!next)break;
      if(seenCursors.has(next))throw new Error("任务目录分页游标重复，请刷新重试");
      seenCursors.add(next);p.set("before_id",String(next));
    }
    requestedState.items=items;
  }
  renderTaskRows();
}

async function loadExecutions(reset=false) {
  if(reset) state.execution={page:1,size:50,before:null,history:[],next:null,total:0};
  const p=new URLSearchParams({limit:String(state.execution.size)}); if(state.execution.before)p.set("before_id",state.execution.before); if($("executionStatus").value)p.set("status",$("executionStatus").value); if($("executionTask").value.trim())p.set("task_key",$("executionTask").value.trim());
  const view=await api(`/api/v1/ops/executions?${p}`); state.execution.next=view.page.next_cursor;state.execution.total=Number(view.page.total||0);
  $("executionRows").innerHTML=view.items.map(x=>{const r=x.resolution||{},displayStatus=x.status==="attention"&&x.is_current_scope_execution===false?"historical_attention":r.resolution_state||x.status,latest=r.latest_execution_id?`<button data-execution="${r.latest_execution_id}">最新实例</button>`:"",definition=r.action==="fix_definition"?`<button data-task="${x.task_definition_id}">查看任务</button>`:"";return `<tr><td>#${x.task_execution_id}</td><td><strong>${esc(x.task_key)}</strong><small>版本 ${x.definition_version}</small></td><td>${esc(x.purpose)}</td><td>${esc(x.observation_key)}<small>${esc(x.observation_start)} → ${esc(x.observation_end)}</small></td><td>${pill(displayStatus)}<small>${esc(x.current_node_key)}</small></td><td>${fmt(x.attempt_count)}/${fmt(x.max_attempts)}</td><td>${fmt(x.rows_fetched)} / ${fmt(x.rows_written)}</td><td><strong>${esc(r.action==="wait_upstream"?"系统自动复查":x.final_error_category||"—")}</strong><small>${esc(r.guidance||"查看运行详情")}</small></td><td class="row-actions"><button data-execution="${x.task_execution_id}">详情</button>${latest}${definition}${r.retryable?`<button class="danger" data-retry="${x.task_execution_id}" data-task-key="${esc(x.task_key)}">重试</button>`:""}</td></tr>`}).join("")||'<tr><td colspan="9">没有匹配实例</td></tr>';
  const start=state.execution.total?((state.execution.page-1)*state.execution.size)+1:0,end=Math.min(state.execution.page*state.execution.size,state.execution.total);
  $("executionPage").textContent=`第 ${state.execution.page} 页 · ${fmt(start)}–${fmt(end)} / 共 ${fmt(state.execution.total)} 条`; $("executionPrev").disabled=state.execution.page===1; $("executionNext").disabled=!state.execution.next;
}
async function showExecution(id){const view=await api(`/api/v1/ops/executions/${id}`),x=view.execution,r=x.resolution||{};$("detailTitle").textContent=`执行实例 #${id}`;const eventLabels={"node.condition.completed":"执行条件已确认","node.scope_plan.completed":"采集范围已确定","node.acquire.started":"开始采集","node.acquire.request_completed":"上游请求已完成","node.acquire.completed":"数据采集已完成","node.validate.completed":"数据校验已完成","dataset.validation.completed":"完整性证据已保存","dataset.state.updated":"数据状态已发布"};const events=(view.events||[]).map(e=>`<li><b>${esc(eventLabels[e.event_type]||e.event_type)}</b><span>${esc(e.node_key||"")} · ${new Date(e.occurred_at).toLocaleString("zh-CN",{hour12:false})}</span></li>`).join("");const nodeOrder=["condition","scope_plan","acquire","transform","validate","publish"],nodes=Object.entries(x.node_status||{}).sort((a,b)=>nodeOrder.indexOf(a[0])-nodeOrder.indexOf(b[0])).map(([key,value],i)=>`<article><span>${i+1}</span><div><strong>${esc(key)}</strong><small>${pill(value)}</small></div></article>`).join("");const issueTitle=r.action==="wait_upstream"?"为何正在等待":"为什么需要处理",status=r.resolution_state||x.status,definition=r.action==="fix_definition"?`<button data-task="${x.task_definition_id}">查看任务定义与节点</button>`:"";$("detailBody").innerHTML=`<button data-task="${x.task_definition_id}">← 来源、任务定义与关联验收</button><div class="detail-grid"><article><small>任务</small><strong>${esc(x.task_key)} · 版本 ${x.definition_version}</strong></article><article><small>业务数据周期</small><strong>${esc(x.observation_start)} → ${esc(x.observation_end)}</strong></article><article><small>状态 / 当前节点</small><strong>${pill(status)} ${esc(x.current_node_key)}</strong></article><article><small>尝试</small><strong>${fmt(x.attempt_count)} / ${fmt(x.max_attempts)}</strong></article></div>${x.status==="attention"?`<div class="resolution"><strong>${issueTitle}</strong><p>${esc(x.final_error_message||x.final_error_category||"未记录明确错误")}</p><strong>下一步</strong><p>${esc(r.guidance)}</p>${definition}${r.retryable?`<button class="primary" data-retry="${id}" data-task-key="${esc(x.task_key)}">确认重试此实例</button>`:""}</div>`:""}<h3>本次执行节点</h3><div class="node-flow compact-flow">${nodes||"暂无节点状态"}</div><h3>证据时间线</h3><ol class="event-list">${events||"<li>暂无事件</li>"}</ol>`;$("detailDialog").showModal();}
async function showTask(id){
  try{
    const view=await api(`/api/v1/ops/tasks/${id}/relationships`),t=view.task,d=t.definition||{};
    $("detailTitle").textContent=`任务链路 · ${t.task_key} · v${t.version}`;
    const sources=(view.sources||[]).map(s=>`<button data-source-tasks="${esc(s.source_id)}">${esc(s.source_id)}</button><small>${esc(s.endpoint_key)} · ${esc(s.acquisition_mode)}</small>`).join("")||"本地派生：不直接请求上游";
    const rows=(view.recent_executions||[]).map(x=>{
      const states=(view.published_states||[]).filter(s=>s.source_execution_id===x.task_execution_id);
      return `<tr><td><button data-execution="${x.task_execution_id}">#${x.task_execution_id}</button><small>v${x.definition_version} · ${esc(x.purpose)}</small></td><td>${esc(x.observation_start)} → ${esc(x.observation_end)}</td><td>${pill(x.status)}<small>${esc(x.current_node_key)}</small></td><td>${states.length?states.map(s=>`<div>${esc(s.dataset_name)} · ${esc(s.observation_key)} ${pill(s.data_status)}<small>${s.ready?"本实例该范围验收通过":"本实例该范围未就绪"}</small></div>`).join(""):"尚无本实例发布证据，不能推断数据就绪"}</td></tr>`;
    }).join("");
    $("detailBody").innerHTML=`<p class="muted">来源 → 任务定义 → 执行实例 → 数据验收。任务运行状态不代替数据完整性。</p>
      <div class="detail-grid"><article><small>数据来源 / 采集接口</small>${sources}</article>
      <article><small>输入数据集</small>${esc((d.input_datasets||[]).join("、")||"无")}</article>
      <article><small>输出数据集 → 目标数据库表</small>${(view.output_storage||[]).map(o=>`<div>${esc(o.dataset)} → <code>${esc(o.table||"未登记映射")}</code></div>`).join("")||"无"}</article>
      <article><small>调度 / 生命周期</small>${esc(d.schedule?.expression||d.schedule?.mode||"—")} · ${esc(t.lifecycle_status)}</article></div>
      <h3>执行节点</h3><div class="node-flow">${(d.nodes||[]).map((n,i)=>`<article><span>${i+1}</span><div><strong>${esc(n.key)}</strong><small>${esc(n.handler_key)}</small></div></article>`).join("")}</div>
      <h3>最近实例与验收证据</h3><p class="muted">${esc(view.semantics)}${view.states_truncated?" · 验收证据仅展示前200条，未展示不等于缺失。":""}</p>
      <button data-task-name="${esc(t.task_key)}">查看此任务全部实例</button>
      <div class="table-wrap"><table><thead><tr><th>实例 / 版本</th><th>数据范围</th><th>执行状态</th><th>数据验收</th></tr></thead><tbody>${rows||'<tr><td colspan="4">尚无执行实例</td></tr>'}</tbody></table></div>`;
    if(!$("detailDialog").open)$("detailDialog").showModal();
  }catch(error){notice(`任务链路加载失败：${error.message}`);}
}
async function retryExecution(id,taskKey){if(!confirm(`确认重试任务 ${taskKey||""} 的执行实例 #${id}？系统会保留原错误证据并从持久队列重新执行。`))return;await api(`/api/v1/ops/executions/${id}/retry`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason:"operator confirmed retry from dashboard"})});notice(`实例 #${id} 已进入重试队列。`);$("detailDialog").close();loadExecutions(true);loadOverview();}

function renderMonth(gridId, month, rows, detail) {
  const [y,m]=month.split("-").map(Number), first=new Date(y,m-1,1), last=new Date(y,m,0), offset=(first.getDay()+6)%7, byDay=new Map(rows.map(x=>[String(x.data_date||x.event_date).slice(0,10),x])),today=isoDate(new Date()); let html="";
  for(let i=0;i<offset;i++)html+='<div class="day outside"></div>';
  for(let d=1;d<=last.getDate();d++){const key=`${y}-${String(m).padStart(2,"0")}-${String(d).padStart(2,"0")}`,x=byDay.get(key),isToday=key===today;let cls="none",text="暂无审计记录";if(x){if(Number(x.problems)>0){cls="problem";text=`${x.problems} 个问题 · ${x.ready||0} 通过`;}else if(Number(x.active)>0){cls="active";text=`${x.active} 进行中`;}else{cls="complete";text=`${x.ready}/${x.dataset_states} 通过`;}}html+=`<button class="day ${cls}${isToday?" today":""}" data-date="${key}"${isToday?' aria-current="date"':""}><b>${d}${isToday?'<em>今天</em>':""}</b><small>${esc(detail?detail(x):text)}</small></button>`;}
  $(gridId).innerHTML=html;
}
async function loadCalendar(){const month=$("calendarMonth").value||monthValue(),[y,m]=month.split("-").map(Number),start=`${month}-01`,end=isoDate(new Date(y,m,0));const view=await api(`/api/v1/ops/coverage/calendar?start_date=${start}&end_date=${end}`);renderMonth("calendarGrid",month,view.days);$("calendarGrid").onclick=e=>{const b=e.target.closest("[data-date]");if(b)loadCalendarDay(b.dataset.date);};}
function renderCalendarDetail(){const status=$("calendarDetailStatus").value,query=$("calendarDetailSearch").value.trim().toLowerCase();let items=state.calendar.items.filter(x=>(!status||(status==="problem"?["missing","partial"].includes(x.status):x.status===status))&&(!query||x.dataset_name.toLowerCase().includes(query)));const pages=Math.max(1,Math.ceil(items.length/state.calendar.size));state.calendar.page=Math.min(state.calendar.page,pages);const start=(state.calendar.page-1)*state.calendar.size,rows=items.slice(start,start+state.calendar.size);$("calendarDetailRows").innerHTML=rows.map(x=>{const issue=state.calendar.issues.get(`${x.dataset_name}:${state.calendar.day}`),ratio=x.entity_coverage_ratio==null?"":` · ${Math.round(Number(x.entity_coverage_ratio)*1000)/10}%`,volume=x.expected_entity_count==null?`${fmt(x.row_count)} 行`:`${fmt(x.entity_count)} / ${fmt(x.expected_entity_count)} 实体${ratio}`;const guidance=issue?(issue.resolution_state==="waiting_upstream"?"上游尚未发布完整截面，系统将自动复查":"需要检查采集与校验证据"):(x.status==="pending"?"核验尚未完成":"无需处理");return `<tr><td><strong>${esc(x.dataset_name)}</strong></td><td>${pill(issue?.resolution_state||x.status)}</td><td>${volume}</td><td>${esc(guidance)}</td><td>${new Date(x.checked_at).toLocaleString("zh-CN",{hour12:false})}</td><td>${issue?.source_execution_id?`<button data-execution="${issue.source_execution_id}">查看采集证据</button>`:"—"}</td></tr>`;}).join("")||'<tr><td colspan="6">没有匹配的数据集</td></tr>';$("calendarDetailPage").textContent=`第 ${state.calendar.page} / ${pages} 页 · ${items.length} 个数据集`;$("calendarDetailPrev").disabled=state.calendar.page===1;$("calendarDetailNext").disabled=state.calendar.page===pages;}
async function loadCalendarDay(day){const [view,health]=await Promise.all([api(`/api/v1/ops/coverage/calendar/${day}`),api("/api/v1/ops/data-health")]),s=view.summary;state.calendar={...state.calendar,page:1,items:view.datasets,day,issues:new Map((health.issues||[]).map(x=>[`${x.dataset}:${x.observation_key}`,x]))};$("calendarDetail").classList.remove("hidden");$("calendarDetailTitle").textContent=`${day} 数据明细`;$("calendarDetailSummary").textContent=`共 ${s.datasets} 个已审计数据集：${s.ready} 个严格通过，${s.observed||0} 个仅已有数据（其中 ${s.not_due||0} 个尚未到期），${s.problems} 个缺失/不完整，${s.active} 个待核验。状态来自数据证据而不是任务结果。`;renderCalendarDetail();$("calendarDetail").scrollIntoView({behavior:"smooth",block:"nearest"});}

async function loadCoverage(){const view=await api("/api/v1/ops/coverage");const s=view.summary;$("coverageSummary").textContent=`${s.audited}/${s.auditable} 已审计 · ${s.with_gaps} 个数据集有缺口 · 缺失 ${fmt(s.missing_partitions)} 个周期`;$("coverageRows").innerHTML=view.datasets.map(x=>{const a=x.latest||{};return `<tr><td><strong>${esc(x.dataset)}</strong></td><td>${esc(x.strategy)}</td><td>${pill(a.status||"unaudited")}</td><td>${esc(a.start_date)} → ${esc(a.end_date)}</td><td>${fmt(a.missing_partitions)}</td><td>${fmt(a.partial_partitions)}</td><td>${x.repairable?"可自动补采":"仅诊断"}</td></tr>`}).join("");}
async function auditAll(){await api("/api/v1/ops/coverage/audits",{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":`dashboard-audit-${Date.now()}`},body:JSON.stringify({datasets:null,all_datasets:true,start_date:null,end_date:null})});notice("已提交全部数据集严格审计；确认的缺口会进入安全修复链路。");loadCoverage();}

async function loadInitialization(){const view=await api("/api/v1/ops/initialization");const c=view.latest;state.initId=c?.initialization_id||null;$("initializationState").innerHTML=c?`<strong>#${c.initialization_id} · ${esc(c.status)}</strong><p>阶段：${esc(c.phase_name)} · 完成 ${fmt(c.completed_steps)}/${fmt(c.planned_steps)} · 失败 ${fmt(c.failed_steps)}</p>`:"尚未运行初始化";if(!c){$("initializationRows").innerHTML="";return;}const rows=await api(`/api/v1/ops/initialization/${c.initialization_id}/steps?limit=500`);$("initializationRows").innerHTML=rows.map(x=>`<tr><td>${esc(x.resource_type)}</td><td>${esc(x.task_key||x.dataset_name)}</td><td>${esc(x.observation_key||x.start_date)} → ${esc(x.observation_end||x.end_date)}</td><td>${pill(x.status)}</td><td>${fmt(x.attempt)}/${fmt(x.max_attempts)}</td><td>${esc(x.failure_category||x.error_message||"")}</td></tr>`).join("");}
async function startInitialization(){if(!confirm("确认对全部业务数据做严格审计，并只补采确认缺失的周期？"))return;const body={profile:$("initProfile").value,history_start:$("initStart").value||null,history_end:$("initEnd").value||null,auto_activate:true};await api("/api/v1/ops/initialization",{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":`dashboard-init-${body.profile}-${body.history_start}-${body.history_end}`},body:JSON.stringify(body)});notice("初始化已启动。");loadInitialization();}

const interfaceStatusLabels={active:"接口已接入",paused:"停采·存量",no_permission:"无权限",not_scheduled:"未接入调度",realtime_required:"在用·实时",ant_primary:"在用·主供",adapter_pending:"未启用",public_registered:"登记能力"};
const interfaceStatusClass={active:"ready",paused:"pending",no_permission:"attention",not_scheduled:"pending",realtime_required:"ant",ant_primary:"ant",adapter_pending:"pending",public_registered:"info"};
const interfaceSourceLabels={tushare:"Tushare",financial_data:"蚂蚁",chinamoney:"中国货币网",cninfo:"巨潮互动易",sse:"上证e互动",sina:"新浪财经",chinabond:"中债",pboc:"人民银行"};
const assetClassLabels={stock:"股票·A股",hk_stock:"港股",us_stock:"美股",fund:"基金",index_etf:"指数·ETF·板块",bond:"债券",derivatives:"期权·期货",forex:"外汇",macro:"宏观",altdata:"另类数据",info:"资讯·公告",chain:"产业链·关联",quote:"行情快照",factor:"因子库",other:"其他"};
const interfaceCadenceLabels={daily:"每日",weekly:"每周",monthly:"每月",quarterly:"每季",hourly:"每小时",dependency:"依赖触发",manual:"按需",realtime:"实时",on_demand:"按需",on_demand_fallback:"按需回退"};
const equivalenceLabels={tushare_direct:"Tushare 直接等价",tushare_derived:"Tushare 确定性派生",tushare_announcement_parse:"Tushare 公告解析",financial_data_only:"蚂蚁必需"};
const acquisitionLabels={scheduled:"定时采集",realtime:"实时获取",on_demand:"按需获取",none:"不采集"};
async function loadAntUsage(){
  const usage=await api("/api/v1/data/sources/ant_data/usage?limit=20").catch(()=>null);
  if(usage){const u=usage.summary||{},failed=Number(u.failed||0),latestFailed=u.latest_status==="failed";$("financialRequestCount").textContent=fmt(u.requests);$("financialSuccessCount").textContent=fmt(u.successful);$("financialFailureCount").textContent=fmt(failed);$("financialResearchCount").textContent=fmt(usage.research_integration?.route_count);$("financialUsageState").className=`pill ${latestFailed?"attention":"ready"}`;$("financialUsageState").textContent=latestFailed?"最近调用失败":u.latest_status?"最近调用正常":"尚无调用";$("financialUsageSummary").textContent=`${fmt(u.rows)} 行供应商结果 · 24 小时失败 ${fmt(u.failed_last_24h)} 批 · 最近真实请求 ${u.last_requested_at?new Date(u.last_requested_at).toLocaleString("zh-CN",{hour12:false}):"尚无"} · 仅保存请求元数据，不保存原始响应`;$("financialUsageRows").innerHTML=(usage.routes||[]).map(x=>`<tr><td><code class="route-code" title="${esc(x.route)}">${esc(shortRoute(x.route))}</code></td><td>${fmt(x.batches)}</td><td>${fmt(x.completed_batches)}</td><td>${fmt(x.failed_batches)}</td><td>${x.last_requested_at?new Date(x.last_requested_at).toLocaleString("zh-CN",{hour12:false}):"—"}</td></tr>`).join("")||'<tr><td colspan="5" class="empty-row">尚无真实上游请求</td></tr>';}else{$("financialUsageState").className="pill attention";$("financialUsageState").textContent="审计不可用";$("financialUsageSummary").textContent="无法读取蚂蚁请求审计；其他数据源信息不受影响。";$("financialUsageRows").innerHTML='<tr><td colspan="5" class="empty-row">请求审计暂不可用</td></tr>';}
  if(usage?.budget){const b=usage.budget;$("financialUsageSummary").textContent=`滚动7天实际发送预占 ${fmt(b.used)} / ${fmt(b.limit)} 个子请求 · 当前用途上限729 · 盘中扩容专用储备 ${fmt(b.reserved_for_intraday_expansion)}（禁止自动借用） · 缓存命中不扣额，失败不退额。历史批次审计与此计量口径不同。`;if(Number(b.remaining_hard_limit)===0){$("financialUsageState").className="pill attention";$("financialUsageState").textContent="等待额度恢复";}}
}
async function loadTushareUsage(){
  const days=$("tsUsageDays").value;
  try{
    const d=await api("/api/v1/data/sources/tushare/usage?days="+days);
    if(days!==$("tsUsageDays").value)return;
    const s=d.summary;
    $("tsUsageSummary").textContent=`共 ${fmt(s.requests)} 条请求记录 · ${fmt(d.interfaces.length)} 个接口 · 空返回 ${fmt(s.empty)} · 失败 ${fmt(s.failed)}`;
    $("tsUsageRows").innerHTML=d.interfaces.map(x=>`<tr><td><code>${esc(x.api_name)}</code></td><td>${fmt(x.requests)}</td><td>${fmt(x.successful)}</td><td>${fmt(x.empty)}</td><td>${fmt(x.failed)}</td><td>${esc(new Date(x.latest_at).toLocaleString("zh-CN"))}</td></tr>`).join("")||'<tr><td colspan="6">该时段暂无请求记录</td></tr>';
  }catch{if(days===$("tsUsageDays").value){$("tsUsageSummary").textContent="审计不可用，不能判断请求次数";$("tsUsageRows").innerHTML="";}}
}
$("tsUsageDays").onchange=loadTushareUsage;
function loadProviderUsage(){return Promise.all([loadAntUsage(),loadTushareUsage()]);}

async function loadSources(reset=false){
  const summary=await api("/api/v1/data/dependencies/summary").catch(()=>null);
  if(summary){
    const bySource=summary.by_source||{},pubSources=Object.keys(bySource).filter(k=>!["tushare","financial_data"].includes(k));
    $("sourceOverviewSources").textContent=fmt(Object.keys(bySource).length);$("sourceOverviewInterfaces").textContent=fmt(summary.interfaces);$("sourceOverviewDatasets").textContent=fmt(summary.datasets);
    const ts=Number(bySource.tushare||0),ant=Number(bySource.financial_data||0),pub=pubSources.reduce((a,k)=>a+Number(bySource[k]||0),0);
    $("sourceStrip").innerHTML=`<button type="button" class="strip-tile ts" data-strip-source="tushare"><p>Tushare <span>定时落库</span></p><strong>${fmt(ts)} <small>契约 / ${fmt(summary.tasks)} 任务</small></strong></button><button type="button" class="strip-tile ant" data-strip-source="financial_data"><p>蚂蚁 <span>查询穿透</span></p><strong>${fmt(ant)} <small>路由 / 不落业务表</small></strong></button><button type="button" class="strip-tile pub" data-strip-source="public"><p>公开来源 ×${pubSources.length} <span>证据查询</span></p><strong>${fmt(pub)} <small>端点</small></strong></button>`;
  }
  // Provider usage is loaded exclusively on the audit page.
  if(reset){state.interfaces.page=1;state.interfaces.items=null;state.interfaces.expanded=null;state.interfaces.detailCache=new Map();}
  if(!state.interfaces.items){
    const pageSize=200;
    const first=await api(`/api/v1/data/dependencies/interfaces?page=1&page_size=${pageSize}`);let items=first.items||[];const total=Number(first.total||items.length);
    // 其余分页并发拉取，避免逐页串行等待
    const pages=[];for(let p=2;p<=Math.min(Math.ceil(total/pageSize),5);p++)pages.push(p);
    if(pages.length){
      const rest=await Promise.all(pages.map(p=>api(`/api/v1/data/dependencies/interfaces?page=${p}&page_size=${pageSize}`)));
      rest.forEach(view=>{items=items.concat(view.items||[]);});
    }
    state.interfaces.items=items;state.interfaces.runtimeAvailable=first.runtime_available;
    const categories=[...new Set(items.map(x=>x.category).filter(Boolean))].sort();const categorySelect=$("interfaceCategory");categorySelect.innerHTML='<option value="">全部分类</option>'+categories.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join("");}
  renderInterfaceRows();
}

function interfaceSourceFilter(item){const value=$("interfaceSource").value;if(!value)return true;if(value==="public")return !["tushare","financial_data"].includes(item.source);return item.source===value;}

function updateStripActive(){
  const value=$("interfaceSource").value;
  document.querySelectorAll("[data-strip-source]").forEach(tile=>tile.classList.toggle("active",tile.dataset.stripSource===value));
}

function interfaceCadenceFilter(item){const value=$("interfaceCadence").value;if(!value)return true;if(value==="unscheduled")return !item.cadence;return item.cadence===value;}

function renderInterfaceRows(){
  const status=$("interfaceStatus").value,category=$("interfaceCategory").value,assetClass=$("interfaceAssetClass").value,query=$("interfaceSearch").value.trim().toLowerCase();
  let items=(state.interfaces.items||[]).filter(x=>interfaceSourceFilter(x)&&interfaceCadenceFilter(x)&&(!status||x.status===status||(status==="automatic"&&(x.automation||[]).some(a=>a.automatic===true))||(status==="no_automatic"&&(x.automation||[]).some(a=>a.automatic===false))||(status==="not_scheduled"&&x.status==="adapter_pending"))&&(!category||x.category===category)&&(!assetClass||(x.asset_class||"other")===assetClass)&&(!query||[x.key,shortRoute(x.key),x.title,x.category,...(x.datasets||[]),...(x.tables||[]),...((x.linked_tasks||[]).map(t=>t.task_key))].join(" ").toLowerCase().includes(query)));
  const pages=Math.max(1,Math.ceil(items.length/state.interfaces.size));state.interfaces.page=Math.min(state.interfaces.page,pages);const start=(state.interfaces.page-1)*state.interfaces.size,rows=items.slice(start,start+state.interfaces.size);
  $("interfaceResult").textContent=`当前筛选 ${items.length} / ${(state.interfaces.items||[]).length} 个接口`+(state.interfaces.runtimeAvailable?"":"（运行状态不可用，仅展示契约信息）");
  $("interfaceRows").innerHTML=rows.map(x=>{
    const key=esc(x.key), fields=(x.output_parameters||x.fields||[]).map(f=>f.name);
    if(!fields.length)fields.push(...Object.keys(x.response_parameters||{}));
    const tasks=x.linked_tasks==null?"关联状态未核实":x.linked_tasks.map(t=>`<a class="task-link" href="/dashboard/tasks?definition=${encodeURIComponent(t.definition_id)}">${esc(t.task_key)}</a>`).join(" ")||"无已发布关联任务";
    const expanded=state.interfaces.expanded===`${x.source}/${x.key}`;
    return `<tr class="interface-row" data-interface-source="${esc(x.source)}" data-interface-key="${key}"><td><code>${key}</code></td><td>${esc(x.title||x.description||"—")}</td><td><span class="asset-badge">${esc(assetClassLabels[x.asset_class]||x.category||"—")}</span></td><td>${esc(interfaceSourceLabels[x.source]||x.source)}</td><td>${esc(interfaceStatusLabels[x.status]||x.status)}<small>${esc(x.permission||"")}</small></td><td>${esc(fields.slice(0,3).join("、")||"—")}<small>${fmt(x.field_count??fields.length)} 个字段 · 展开查看</small></td><td>${tasks}</td></tr>${expanded?'<tr><td colspan="7" id="interfaceDetailCell">加载中…</td></tr>':""}`;
  }).join("")||'<tr><td colspan="7">没有匹配接口</td></tr>';
  $("interfaceTotalHint").textContent="点击接口展开字段；点击任务查看数据集和目标表";
  $("interfacePage").textContent=`第 ${state.interfaces.page} / ${pages} 页`;
  updateStripActive();
  $("interfacePrev").disabled=state.interfaces.page===1;$("interfaceNext").disabled=state.interfaces.page===pages;
  if(state.interfaces.expanded)void loadInterfaceDetail();
}
function xCadence(x){return interfaceCadenceLabels[x.cadence]||x.cadence||(x.acquisition_kind==="realtime"?"实时":"按需");}
function shortRoute(route){return String(route||"").replace(/^\/api\/v1\//,"*/");}

function interfaceDetailParts(detail){
  const x=detail;
  const parts=[];
  // Only direct endpoint evidence belongs with this contract.
  if(x.source==="tushare"){
    const evidence=x.collection_evidence, hit=evidence?.last_nonempty;
    parts.push(`<p class="detail-desc">同名接口最近非空采集：${hit?`${esc(hit.observed_at)} · ${fmt(hit.rows_fetched)} 行`:evidence?.available?"暂无留存证据":"证据暂不可用"}。此记录不代表当期数据完整或当前 token 权限。</p>`);
  }
  // The acquisition contract does not own task cadence or execution status.
  parts.push(`<p class="detail-title"><code class="route-code" title="${esc(x.key)}">${esc(shortRoute(x.key))}</code>${x.title?`<b>${esc(x.title)}</b>`:""}</p>`);
  if(x.description)parts.push(`<p class="detail-desc">${esc(x.description)}</p>`);
  const fieldTable=(fields,title)=>{const rows=(fields||[]).map(f=>`<tr><td style="font-family:var(--font-mono)">${esc(f.name)}</td><td>${esc(f.type||"—")}</td><td>${esc(f.description||"—")}</td></tr>`).join("");return `<div><small class="detail-label">${esc(title)}</small><div class="table-wrap detail-mini"><table><thead><tr><th>字段</th><th>类型</th><th>说明</th></tr></thead><tbody>${rows||'<tr><td colspan="3">无</td></tr>'}</tbody></table></div></div>`;};
  if(x.source==="tushare"){
    const input=(x.input_parameters||[]).map(f=>`<tr><td style="font-family:var(--font-mono)">${esc(f.name)}</td><td>${esc(f.type||"—")}</td><td>${esc(f.required||"—")}</td><td>${esc(f.description||"—")}</td></tr>`).join("");
    parts.push(`<div><small class="detail-label">输入参数</small><div class="table-wrap detail-mini"><table><thead><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr></thead><tbody>${input||'<tr><td colspan="4">无</td></tr>'}</tbody></table></div></div>`);
    parts.push(fieldTable(x.output_parameters,"可采集字段（输出）"));
    if(x.superseded_by)parts.push(`<p>替代接口：${esc(x.superseded_by)}</p>`);
  }else if(x.source==="financial_data"){
    parts.push(fieldTable(Object.entries(x.response_parameters||{}).map(([name,desc])=>({name,description:String(desc).split("|").pop()?.trim()||"",type:String(desc).split("|")[0]?.trim()||""})),"响应字段（供应商原生模型）"));
    // Task outputs and physical storage belong to the linked task definition.
  }else{
    parts.push(fieldTable(x.output_parameters,"可观测字段"));
    parts.push(`<div class="detail-facts"><small class="detail-label">供给策略</small><p>公开证据查询：响应不落业务表，缓存 ${fmt(x.cache_ttl_seconds||0)} 秒；Agent 通过研究层公开证据接口使用。</p></div>`);
  }
  return parts.join("");
}

async function loadInterfaceDetail(){
  const cell=$("interfaceDetailCell");if(!cell)return;
  const expanded=state.interfaces.expanded;if(!expanded)return;
  if(state.interfaces.detailCache.has(expanded)){cell.innerHTML=interfaceDetailParts(state.interfaces.detailCache.get(expanded));return;}
  const sourceIndex=expanded.indexOf("/");const source=expanded.slice(0,sourceIndex);const key=expanded.slice(sourceIndex+1);
  try{const view=await api(`/api/v1/data/dependencies/interfaces/${source}/detail?key=${encodeURIComponent(key)}`);state.interfaces.detailCache.set(expanded,view.interface);if(state.interfaces.expanded===expanded)cell.innerHTML=interfaceDetailParts(view.interface);}
  catch(error){if(state.interfaces.expanded===expanded)cell.innerHTML=`<p class="detail-desc">详情加载失败：${esc(error.message)}</p>`;}
}

function renderFieldLineage(){
  const query=$("lineageSearch").value.trim().toLowerCase();
  const titleOf=apiName=>{const item=(state.interfaces.items||[]).find(x=>x.source==="tushare"&&x.key===apiName);return item?.title||apiName;};
  let items=(state.interfaces.lineage||[]).filter(x=>!query||[x.table,...x.interfaces,...x.fields.map(f=>f.name)].join(" ").toLowerCase().includes(query));
  const pages=Math.max(1,Math.ceil(items.length/state.interfaces.lineageSize));state.interfaces.lineagePage=Math.min(state.interfaces.lineagePage,pages);const start=(state.interfaces.lineagePage-1)*state.interfaces.lineageSize,rows=items.slice(start,start+state.interfaces.lineageSize);
  $("lineageResult").textContent=`当前筛选 ${items.length} / ${(state.interfaces.lineage||[]).length} 张物理表（Tushare 落库表）`;
  $("lineageRows").innerHTML=rows.map(x=>`<tr><td><code class="table-code">${esc(x.table)}</code></td><td>${x.interfaces.map(v=>`<span class="dataset-chip" title="${esc(titleOf(v))}">${esc(titleOf(v))}</span>`).join("")}</td><td><div class="lineage-fields">${x.fields.slice(0,8).map(f=>`<span class="lineage-field"><b>${esc(f.name)}</b><small>${f.from_interfaces.map(v=>esc(titleOf(v))).join("、")}</small></span>`).join("")}${x.fields.length>8?`<span class="dataset-more">+${x.fields.length-8} 个字段</span>`:""}</div></td></tr>`).join("")||'<tr><td colspan="3" class="empty-row">没有匹配的表</td></tr>';
  $("lineagePage").textContent=`第 ${state.interfaces.lineagePage} / ${pages} 页 · ${items.length} 张表`;
  $("lineagePrev").disabled=state.interfaces.lineagePage===1;$("lineageNext").disabled=state.interfaces.lineagePage===pages;
}

const derivationStatusMeta={implemented:{cls:"ready",label:"已实现·自动派发"},planned:{cls:"pending",label:"规划中·蓝图已登记"}};
const derivationStatusMetaOverrides={ggt_monthly:{cls:"info",label:"采集运行时物化"}};

async function loadDerivations(){
  if(!state.derivations.items){
    const view=await api("/api/v1/data/derivations/tasks");
    state.derivations.items=view.items;state.derivations.summary=view.summary;state.derivations.runtimeAvailable=view.runtime_available;state.derivations.coverageAvailable=view.coverage_available;
    const s=view.summary;
    $("derivationTaskCount").textContent=fmt(s.tasks);
    $("derivationImplementedCount").textContent=fmt(s.by_status.implemented||0);
    $("derivationOndemandCount").textContent=fmt(s.on_demand_endpoints);
    $("derivationStrip").innerHTML=`<div class="strip-tile ts"><p>持久化派生 <span>依赖就绪自动物化</span></p><strong>${fmt(s.by_status.implemented||0)} <small>/ ${fmt(s.tasks)} 个任务已实现</small></strong></div><div class="strip-tile ant"><p>规划中 <span>蓝图已登记待固化</span></p><strong>${fmt(s.by_status.planned||0)} <small>个任务</small></strong></div><div class="strip-tile pub"><p>即时计算 <span>研究层 · 不落表</span></p><strong>${fmt(s.on_demand_endpoints)} <small>个按需指标</small></strong></div>`;
  }
  renderDerivationRows();
  if(!state.derivations.ondemand){
    const view=await api("/api/v1/data/derivations/ondemand");
    state.derivations.ondemand=view.items;
    renderOndemandRows();
  }
}

function renderDerivationRows(){
  const items=state.derivations.items||[];
  const pages=Math.max(1,Math.ceil(items.length/state.derivations.size));
  state.derivations.page=Math.min(state.derivations.page,pages);
  const start=(state.derivations.page-1)*state.derivations.size,rows=items.slice(start,start+state.derivations.size);
  $("derivationResult").textContent=`共 ${fmt(items.length)} 个派生任务`+(state.derivations.runtimeAvailable?"":"（运行状态不可用，仅展示契约信息）");
  $("derivationRows").innerHTML=rows.map(x=>{
    const meta=derivationStatusMetaOverrides[x.key]||derivationStatusMeta[x.status]||{cls:"pending",label:x.status};
    const statusPill=`<span class="pill ${meta.cls}">${esc(meta.label)}</span>`;
    const inputs=(x.inputs||[]).map(i=>`<span class="dataset-chip" title="${esc(i.table||i.name)}">${esc(i.title)}</span>`).join(" ");
    const coverage=x.coverage;
    const coverageCell=coverage?`<b>${fmt(coverage.days)}</b> 天<small class="cov-range">${esc(coverage.first_date)} → ${esc(coverage.latest_date)}</small>`:'<span class="muted">—</span>';
    const latest=x.runtime?.dataset_state?.observation_end||coverage?.latest_date||"";
    const latestCell=latest?`<b>${esc(latest)}</b>`:'<span class="muted">—</span>';
    const version=x.implementation_version||"—";
    return `<tr class="interface-row" data-derivation-key="${esc(x.key)}"><td><code class="route-code">${esc(x.key)}</code><small class="iface-name">${esc(x.title)}</small></td><td>${statusPill}</td><td>${inputs||'<span class="muted">—</span>'}</td><td><code class="table-code">${esc(version)}</code></td><td>${esc(x.frequency||"—")}</td><td>${coverageCell}</td><td>${latestCell}</td></tr>${state.derivations.expanded===x.key?'<tr class="interface-detail-row"><td colspan="7" id="derivationDetailCell">加载中…</td></tr>':""}`;
  }).join("")||'<tr><td colspan="7" class="empty-row">没有派生任务</td></tr>';
  $("derivationTotalHint").textContent=`共 ${fmt(items.length)} 条 · 每行可展开查看算法说明与运行状态`;
  $("derivationPage").textContent=`第 ${state.derivations.page} / ${pages} 页`;
  $("derivationPrev").disabled=state.derivations.page===1;$("derivationNext").disabled=state.derivations.page===pages;
  if(state.derivations.expanded)void loadDerivationDetail();
}

function renderDerivationDetail(x){
  const runtime=x.runtime||{};
  const exec=runtime.latest_execution;
  const dsState=runtime.dataset_state;
  const inputRows=(x.inputs||[]).map(i=>`<tr><td>${esc(i.title)}</td><td><code class="table-code">${esc(i.table||"—")}</code></td><td>${i.kind==="derived"?"上游派生":i.kind==="dataset"?"采集落库":"未知"}</td></tr>`).join("");
  const parts=[];
  if(x.description)parts.push(`<p class="detail-desc">${esc(x.description)}</p>`);
  parts.push(`<div class="detail-facts"><small class="detail-label">怎么算</small><p>${esc(x.algorithm||"—")}</p><p>算法版本：<code>${esc(x.implementation_version||"—")}</code> · 调度优先级 ${fmt(x.priority)}</p></div>`);
  parts.push(`<small class="detail-label">输入数据（用哪些数据算）</small><div class="table-wrap detail-mini"><table><thead><tr><th>数据</th><th>物理表</th><th>来源</th></tr></thead><tbody>${inputRows||'<tr><td colspan="3">无</td></tr>'}</tbody></table></div>`);
  parts.push(`<div class="detail-facts"><small class="detail-label">血缘与运行状态</small><p>输出数据集：${(x.output_datasets||[]).map(v=>`<span class="dataset-chip">${esc(v)}</span>`).join("")}${(x.tables||[]).length?` · 落表 ${(x.tables||[]).map(v=>`<code class="table-code">${esc(v)}</code>`).join("、")}`:""}</p><p>依赖任务：${(x.dependency_task_keys||[]).map(v=>`<button class="task-link" data-task-name="${esc(v)}">${esc(v)}</button>`).join("")||"—"}</p><p>${exec?`最近执行：${pill(exec.status)} · 业务周期 ${esc(exec.observation_start||"—")} → ${exec.observation_end?`<b>${esc(exec.observation_end)}</b>`:"—"}`:"最近执行：暂无实例"}</p><p>${dsState?`数据就绪：${dsState.ready?"已就绪":"未就绪"} · 最新观测 ${dsState.observation_end?`<b>${esc(dsState.observation_end)}</b>`:"—"}${dsState.actual_count!=null?` · 行数 ${fmt(dsState.actual_count)}`:""}`:"数据就绪状态：—"}</p>${x.coverage?`<p>已物化 <b>${fmt(x.coverage.days)}</b> 天（${esc(x.coverage.first_date)} → ${esc(x.coverage.latest_date)}）${x.key==="technical_factor_snapshot"?" · 该快照仅向前物化，不做历史回填":""}</p>`:""}</div>`);
  return parts.join("");
}

async function loadDerivationDetail(){
  const cell=$("derivationDetailCell");if(!cell)return;
  const key=state.derivations.expanded;if(!key)return;
  const item=(state.derivations.items||[]).find(x=>x.key===key);
  if(item)cell.innerHTML=renderDerivationDetail(item);
}

function renderOndemandRows(){
  const items=state.derivations.ondemand||[];
  const pages=Math.max(1,Math.ceil(items.length/state.derivations.ondemandSize));
  state.derivations.ondemandPage=Math.min(state.derivations.ondemandPage,pages);
  const start=(state.derivations.ondemandPage-1)*state.derivations.ondemandSize,rows=items.slice(start,start+state.derivations.ondemandSize);
  $("ondemandResult").textContent=`共 ${fmt(items.length)} 个研究层指标 · 按需计算、响应即返回、不落业务表`;
  $("ondemandRows").innerHTML=rows.map(x=>`<tr><td><b>${esc(x.title)}</b></td><td><span class="acquisition-tag">${esc(x.domain)}</span></td><td>${esc(x.description)}</td><td><span class="pill info">即时计算</span></td><td><code class="table-code">${esc(x.method)} ${esc(x.key)}</code></td></tr>`).join("")||'<tr><td colspan="5" class="empty-row">没有指标</td></tr>';
  $("ondemandTotalHint").textContent=`共 ${fmt(items.length)} 条`;
  $("ondemandPage").textContent=`第 ${state.derivations.ondemandPage} / ${pages} 页`;
  $("ondemandPrev").disabled=state.derivations.ondemandPage===1;$("ondemandNext").disabled=state.derivations.ondemandPage===pages;
}

function setInterfaceView(mode){
  state.interfaces.viewMode=mode;
  document.querySelectorAll("[data-interface-view]").forEach(button=>button.classList.toggle("active",button.dataset.interfaceView===mode));
  $("interfaceTableView").classList.toggle("hidden",mode!=="table");
  $("fieldLineageView").classList.toggle("hidden",mode!=="lineage");
  if(mode==="lineage"&&!state.interfaces.lineage)api("/api/v1/data/dependencies/field-lineage?page=1&page_size=500").then(view=>{state.interfaces.lineage=view.items;renderFieldLineage();}).catch(error=>notice(`字段血缘加载失败：${error.message}`));
}

async function loadServices(reset=false){
  if(reset){state.services.page=1;state.services.items=null;}
  if(!state.services.items){const view=await api("/api/v1/catalog");state.services.items=view.layers.flatMap(layer=>layer.endpoints.map(endpoint=>({...endpoint,layer_id:layer.id,layer_title:layer.title})));}
  renderServiceRows();
}
function renderServiceRows(){
  if(!state.services.items)return;
  const categories=[...new Set(state.services.items.map(x=>x.category).filter(Boolean))].sort();
  const catSelect=$("serviceCategory");const prevCategory=catSelect.value;
  catSelect.innerHTML='<option value="">全部业务分类</option>'+categories.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join("");
  if(prevCategory&&categories.includes(prevCategory))catSelect.value=prevCategory;
  const layer=$("serviceLayer").value,category=catSelect.value,query=$("serviceSearch").value.trim().toLowerCase();
  let items=state.services.items.filter(x=>(!layer||x.layer_id===layer)&&(!category||x.category===category)&&(!query||[x.name,x.path,...(x.local_datasets||[]),...(x.upstream_sources||[])].join(" ").toLowerCase().includes(query)));
  const pages=Math.max(1,Math.ceil(items.length/state.services.size));state.services.page=Math.min(state.services.page,pages);const start=(state.services.page-1)*state.services.size,rows=items.slice(start,start+state.services.size);
  $("serviceSummary").textContent=`共 ${items.length} 个匹配的对外 REST 入口；供应商、连接器和权限映射已从本目录移到“数据依赖”。`;
  $("serviceRows").innerHTML=rows.map(x=>{const datasets=(x.local_datasets||[]).length?`${x.local_datasets.slice(0,5).map(esc).join("、")}${x.local_datasets.length>5?` 等 ${x.local_datasets.length} 个`:""}`:`动态：${esc(x.dependency_scope)}`;const fields=(x.fields||[]).slice(0,20);const fieldsHtml=fields.length?`<small class="svc-fields">字段：${fields.map(f=>`<code>${esc(f.name)}</code>`).join(" ")}${x.fields.length>20?` … 共 ${x.fields.length} 个`:""}</small>`:"";return `<tr><td><strong>${esc(x.category||x.layer_title||"—")}</strong>${x.layer_id?`<small>${pill(x.layer_id)}</small>`:""}${esc(x.name)}</td><td><code>${esc(x.method)} ${esc(x.path)}</code></td><td>${datasets}${fieldsHtml}</td><td>${esc(x.data_origin)}${x.derivation?`<small>${esc(x.derivation)}</small>`:""}</td><td>${esc(x.read_strategy)}</td></tr>`}).join("")||'<tr><td colspan="5">没有匹配服务</td></tr>';
  $("servicePage").textContent=`第 ${state.services.page} / ${pages} 页`;$('servicePrev').disabled=state.services.page===1;$('serviceNext').disabled=state.services.page===pages;
}

async function loadInvestment(){const month=$("investmentMonth").value||monthValue(),[y,m]=month.split("-").map(Number),start=`${month}-01`,end=isoDate(new Date(y,m,0));const view=await api(`/api/v1/research/investment-calendar?start_date=${start}&end_date=${end}&importance=important`);const events=view.events||view.items||[];const groups={};events.forEach(x=>(groups[String(x.event_date||x.date).slice(0,10)]??=[]).push(x));const rows=Object.entries(groups).map(([event_date,items])=>({event_date,items}));renderMonth("investmentGrid",month,rows,x=>x?`${x.items.length} 个事件`:"无重要事件");$("investmentGrid").onclick=e=>{const b=e.target.closest("[data-date]");if(!b)return;const items=groups[b.dataset.date]||[];$("investmentEvents").innerHTML=items.map(x=>`<div class="issue"><div><strong>${esc(x.event_name||x.name||x.title)}</strong><small>${esc(x.country)} · ${esc(x.event_time||x.time)} · 实际 ${esc(x.actual)}</small></div></div>`).join("")||"<p>当日无重要事件</p>";};}

const stockLineDefinitions={
  ma_5:{label:"MA5",color:"#9b7bd4"},ma_10:{label:"MA10",color:"#d19b3f"},ma_20:{label:"MA20",color:"#348fcb"},ma_60:{label:"MA60",color:"#7b8794"},
  ma_120:{label:"MA120",color:"#4d8d7c"},ma_250:{label:"MA250",color:"#6a7480"},ema_12:{label:"EMA12",color:"#35a78a"},ema_26:{label:"EMA26",color:"#2f6f9f"},ema_20:{label:"EMA20",color:"#35a78a"},ema_50:{label:"EMA50",color:"#2f6f9f"},ema_200:{label:"EMA200",color:"#17666f"},bbi:{label:"BBI",color:"#945ca8"},
  cost_20:{label:"成本20",color:"#b96a93"},cost_60:{label:"成本60",color:"#8753a6"},niumen_line:{label:"牛门线",color:"#e07a35"},niumen_confirmation_line:{label:"确认线",color:"#c94848"},
  niumen_signal_ma_10:{label:"信号MA10",color:"#e7a85c"},bollinger_upper:{label:"BOLL上轨",color:"#8795a1"},bollinger_middle:{label:"BOLL中轨",color:"#a4afb8"},bollinger_lower:{label:"BOLL下轨",color:"#8795a1"},keltner_upper:{label:"KC上轨",color:"#4d91a8"},keltner_middle:{label:"KC中轨",color:"#71aabd"},keltner_lower:{label:"KC下轨",color:"#4d91a8"}
};
const XIONGMEN_MAIN_LINES=["xiongmen_line","xiongmen_foundation","xiongmen_floor_1","xiongmen_floor_2","xiongmen_floor_3","xiongmen_recovery_ma_60"];
Object.assign(stockLineDefinitions,{
  xiongmen_line:{label:"熊门线",color:"var(--xiongmen-line)"},
  xiongmen_foundation:{label:"地基",color:"#17855b"},
  xiongmen_floor_1:{label:"一楼",color:"#b58a00"},
  xiongmen_floor_2:{label:"二楼",color:"#bc59b5"},
  xiongmen_floor_3:{label:"三楼",color:"#d95252"},
  xiongmen_recovery_ma_60:{label:"解套线 MA60",color:"#28a6b6",dash:true},
  xiongmen_bear_entry_line:{label:"入熊线",color:"#8795a1",dash:true}
});
function xiongmenMarkers(points,x,y){
  return points.map((point,index)=>{
    const signal=point.xiongmen_reduction_signal,price=point.xiongmen_marker_price;
    if(!["减一","减二"].includes(signal)||price==null||!Number.isFinite(Number(price)))return "";
    const color=stockLineDefinitions[signal==="减二"?"xiongmen_floor_2":"xiongmen_floor_1"].color;
    return `<text class="xiongmen-marker" x="${x(index)}" y="${y(Number(price))}" text-anchor="middle" fill="${color}">${signal}</text>`;
  }).join("");
}
function xiongmenTooltip(point){
  if(point.xiongmen_bear_state==null)return '<span>熊门体系：不足250根日线</span>';
  const count=point.xiongmen_sample_count||0;
  return `<span>${point.xiongmen_bear_state?"处于入熊区间":"未处于入熊区间"}${point.xiongmen_reduction_signal?` · ${esc(point.xiongmen_reduction_signal)}`:""}</span><span>20日后收盘更低：${count?`${stockNumber(point.xiongmen_lower_rate_pct,1)}%`:"—"} · ${count}次已结算</span>`;
}
function xiongmenSummary(summary){
  if(summary?.status==="not_applicable")return {label:"仅日线提供",detail:"熊门体系按交易日计算"};
  if(summary?.status!=="ready")return {label:"历史不足",detail:"入熊判断需250根日线；参考线按各自窗口展示"};
  const stats=summary.statistics||{};
  return {label:summary.events?.reduction_signal||(summary.state==="bear_rebound_watch"?"处于入熊区间":"未处于入熊区间"),detail:`20日后收盘更低 ${stats.matured_samples?`${stockNumber(stats.lower_close_rate_pct,1)}%`:"—"} · ${stats.matured_samples||0}次已结算 · 当前查询历史`};
}
const stockNumber=(value,digits=2)=>value==null||Number.isNaN(Number(value))?"—":Number(value).toLocaleString("zh-CN",{minimumFractionDigits:digits,maximumFractionDigits:digits});
const stockPercent=value=>value==null||Number.isNaN(Number(value))?"—":`${Number(value)>=0?"+":""}${stockNumber(value,2)}%`;
const stockStateLabel=value=>({bullish:"多头",bearish:"空头",mixed:"震荡",above_niumen:"站上牛门线",confirmed_breakout:"确认突破",below_niumen:"牛门线下方",normal:"常态",expanding:"放量",contracting:"缩量",accumulation:"价量偏强",distribution:"价量偏弱",neutral:"中性"}[value]||value||"—");
const stockDailyOnlyLines=new Set(["cost_20","cost_60","niumen_line","niumen_confirmation_line","niumen_signal_ma_10"]);
XIONGMEN_MAIN_LINES.forEach(key=>stockDailyOnlyLines.add(key));
stockDailyOnlyLines.add("xiongmen_bear_entry_line");
function stockActiveLines(){return [...state.stock.overlays].flatMap(key=>key==="xiongmen"?XIONGMEN_MAIN_LINES:key==="bollinger"?["bollinger_upper","bollinger_middle","bollinger_lower"]:key==="keltner"?["keltner_upper","keltner_middle","keltner_lower"]:[key]).filter(key=>state.stock.timeframe==="1d"||!stockDailyOnlyLines.has(key));}
function stockVolumeScale(value){const number=Number(value)||0;if(Math.abs(number)>=100000000)return {value:number/100000000,unit:"亿手",digits:2};if(Math.abs(number)>=10000)return {value:number/10000,unit:"万手",digits:2};return {value:number,unit:"手",digits:0};}
function stockVolumeText(value,forcedUnit=null){const scale=forcedUnit==="亿手"?{value:(Number(value)||0)/100000000,unit:forcedUnit,digits:2}:forcedUnit==="万手"?{value:(Number(value)||0)/10000,unit:forcedUnit,digits:2}:forcedUnit==="手"?{value:Number(value)||0,unit:forcedUnit,digits:0}:stockVolumeScale(value);return `${stockNumber(scale.value,scale.digits)} ${scale.unit}`;}
function stockVisiblePoints(points){const viewport=state.stock.viewport;if(viewport.timeframe!==state.stock.timeframe||viewport.total!==points.length||!viewport.count){const preferred=Math.max(30,Number($("stockPoints").value)||180);viewport.timeframe=state.stock.timeframe;viewport.total=points.length;viewport.count=Math.min(preferred,points.length);viewport.start=Math.max(0,points.length-viewport.count);}viewport.count=Math.max(Math.min(viewport.count,points.length),Math.min(30,points.length));viewport.start=Math.max(0,Math.min(viewport.start,points.length-viewport.count));return points.slice(viewport.start,viewport.start+viewport.count);}
function updateStockViewportControls(points){const viewport=state.stock.viewport,pan=$("stockPan"),end=Math.min(viewport.start+viewport.count,points.length),maxStart=Math.max(0,points.length-viewport.count),first=points[viewport.start]?.trade_date,last=points[Math.max(viewport.start,end-1)]?.trade_date;pan.max=String(maxStart);pan.value=String(viewport.start);pan.disabled=viewport.count>=points.length;$("stockPanPrev").disabled=viewport.start<=0;$("stockPanNext").disabled=viewport.start>=maxStart;$("stockZoomStatus").textContent=points.length?`${first||"—"} → ${last||"—"} · ${viewport.start+1}–${end}/${points.length}`:"—";$("stockZoomIn").disabled=viewport.count<=Math.min(30,points.length);$("stockZoomOut").disabled=viewport.count>=points.length;$("stockZoomReset").disabled=viewport.start===maxStart&&viewport.count===Math.min(Math.max(30,Number($("stockPoints").value)||180),points.length);}
function zoomStockChart(direction,anchor=.5){const response=state.stock.response,data=response?.data||{},timeframe=data.timeframes?.[state.stock.timeframe];if(!timeframe)return;const points=timeframe.chart?.points||[],viewport=state.stock.viewport;stockVisiblePoints(points);const oldCount=viewport.count,newCount=direction>0?Math.max(30,Math.round(oldCount*.72)):Math.min(points.length,Math.round(oldCount/0.72));if(newCount===oldCount)return;const anchorIndex=viewport.start+oldCount*Math.max(0,Math.min(anchor,1));viewport.count=newCount;viewport.start=Math.round(anchorIndex-newCount*Math.max(0,Math.min(anchor,1)));viewport.start=Math.max(0,Math.min(viewport.start,points.length-newCount));state.stock.selectedTradeDate=null;scheduleStockRender();}
function panStockChart(direction){const viewport=state.stock.viewport;if(!viewport.count)return;const maxStart=Math.max(0,viewport.total-viewport.count),step=Math.max(1,Math.round(viewport.count*.55));viewport.start=Math.max(0,Math.min(maxStart,viewport.start+direction*step));state.stock.selectedTradeDate=null;scheduleStockRender();}

function stockEnsureMacd(points){
  const ema=(values,period)=>{const factor=2/(period+1),out=[];values.forEach((value,index)=>out.push(index?value*factor+out[index-1]*(1-factor):value));return out;};
  if(points.every(point=>point.macd!=null&&point.macd_signal!=null))return points;
  const closes=points.map(point=>Number(point.close)),fast=ema(closes,12),slow=ema(closes,26),dif=fast.map((value,index)=>value-slow[index]),dea=ema(dif,9);
  return points.map((point,index)=>({...point,macd:dif[index],macd_signal:dea[index],macd_histogram:dif[index]-dea[index]}));
}

function stockPath(points,key,x,y){
  let path="",drawing=false;
  points.forEach((point,index)=>{const value=Number(point[key]);if(point[key]==null||!Number.isFinite(value)){drawing=false;return;}path+=`${drawing?"L":"M"}${x(index).toFixed(2)},${y(value).toFixed(2)} `;drawing=true;});
  return path.trim();
}

const STOCK_SUB_MARGIN={left:12,right:72},STOCK_SUB_WIDTH=1200,STOCK_SUB_PLOT=STOCK_SUB_WIDTH-STOCK_SUB_MARGIN.left-STOCK_SUB_MARGIN.right;
const STOCK_SUB_INDICATORS={
  volume:{label:"成交量 VOL",height:128},turnover:{label:"换手率 TURN",height:110},macd:{label:"MACD (12,26,9)",height:150},kdj:{label:"KDJ (9,3,3)",height:130},rsi:{label:"RSI (6/12/24)",height:130},cci:{label:"CCI (14)",height:130},roc:{label:"ROC (20)",height:130},obv:{label:"OBV",height:130},
  bias:{label:"BIAS 乖离率 (6/12/24)",height:130},ppo:{label:"PPO (12,26,9)",height:150},trix:{label:"TRIX (12,9)",height:130},tsi:{label:"TSI (25,13)",height:130},percentb:{label:"布林 %B",height:130},bandwidth:{label:"布林带宽",height:130},natr:{label:"NATR (14)",height:130},squeeze:{label:"TTM 挤压动量",height:130},pvt:{label:"PVT 量价趋势",height:130},vroc:{label:"VROC (12/20)",height:130},force:{label:"强力指数 Force (13)",height:130}
};
function stockX(index,n){return STOCK_SUB_MARGIN.left+(index+.5)*STOCK_SUB_PLOT/Math.max(n,1);}
function stockHitIndex(event,svg,n){const rect=svg.getBoundingClientRect(),relative=(event.clientX-rect.left)/Math.max(rect.width,1)*STOCK_SUB_WIDTH;return Math.max(0,Math.min(n-1,Math.floor((relative-STOCK_SUB_MARGIN.left)/STOCK_SUB_PLOT*n)));}
function stockCurrentPoints(){return state.stock._view?.points||[];}

function renderStockPriceChart(points){
  const svg=$("stockPriceChart"),width=1200,height=430,margin={left:12,right:72,top:15,bottom:28},plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom;
  if(!points.length){svg.innerHTML='<text x="600" y="215" text-anchor="middle" class="axis-label">没有可展示的行情</text>';state.stock.priceScale=null;return;}
  const active=stockActiveLines(),showXiongmen=state.stock.timeframe==="1d"&&state.stock.overlays.has("xiongmen");
  const values=points.flatMap(point=>[point.high,point.low,...active.map(key=>point[key]),...(showXiongmen?[point.xiongmen_marker_price]:[])]).filter(value=>value!=null).map(Number).filter(Number.isFinite),rawMin=Math.min(...values),rawMax=Math.max(...values),padding=Math.max((rawMax-rawMin)*.06,rawMax*.005),min=rawMin-padding,max=rawMax+padding;
  const x=index=>stockX(index,points.length),y=value=>margin.top+(max-value)/(max-min)*plotHeight,step=plotWidth/points.length,bodyWidth=Math.max(1.5,Math.min(7,step*.64));
  let markup="";
  for(let tick=0;tick<=5;tick++){const value=max-(max-min)*tick/5,py=margin.top+plotHeight*tick/5;markup+=`<line class="grid-line" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/><text class="axis-label" x="${width-margin.right+8}" y="${py+3}">${stockNumber(value,2)}</text>`;}
  const dateTicks=Math.min(6,points.length);for(let tick=0;tick<dateTicks;tick++){const index=Math.round(tick*(points.length-1)/Math.max(dateTicks-1,1));markup+=`<text class="axis-label" text-anchor="middle" x="${x(index)}" y="${height-7}">${esc(String(points[index].trade_date).slice(5,10))}</text>`;}
  points.forEach((point,index)=>{const opened=Number(point.open),closed=Number(point.close),high=Number(point.high),low=Number(point.low),up=closed>=opened,top=y(Math.max(opened,closed)),bottom=y(Math.min(opened,closed)),bodyHeight=Math.max(1,bottom-top),className=up?"candle-up":"candle-down";markup+=`<line class="${className}" x1="${x(index)}" y1="${y(high)}" x2="${x(index)}" y2="${y(low)}"/><rect class="${className}" x="${x(index)-bodyWidth/2}" y="${top}" width="${bodyWidth}" height="${bodyHeight}"/>`;});
  active.forEach(key=>{const definition=stockLineDefinitions[key],dash=(key.startsWith("niumen")||definition.dash)?' stroke-dasharray="6 4"':"";markup+=`<path class="factor-line" d="${stockPath(points,key,x,y)}" stroke="${definition.color}"${dash}/>`;});
  if(showXiongmen)markup+=xiongmenMarkers(points,x,y);
  markup+=`<g id="stockCrosshair"></g><rect class="hit-area" x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${plotHeight}"/>`;
  svg.innerHTML=markup;
  state.stock.priceScale={min,max,plotHeight,margin,active,points};
  const hit=svg.querySelector(".hit-area");
  hit.onpointermove=event=>{if(!state.stock.drag.active)stockSyncCrosshair(stockHitIndex(event,svg,points.length),event,false);};
  hit.onclick=event=>{if(state.stock.drag.moved)return;const index=stockHitIndex(event,svg,points.length);state.stock.selectedTradeDate=points[index].trade_date;stockSyncCrosshair(index,event,true);};
  hit.onpointerleave=()=>stockLeaveCrosshair(points);
}

function stockLeaveCrosshair(points){
  const selected=points.findIndex(point=>point.trade_date===state.stock.selectedTradeDate);
  if(selected>=0)stockSyncCrosshair(selected,null,true);else stockClearCrosshair();
}
function stockSyncCrosshair(index,event,pinned){
  const points=stockCurrentPoints();if(!points.length||index<0||index>=points.length)return;
  state.stock.hoverIndex=index;
  stockPaintMainCrosshair(index,event,pinned);
  state.stock.subCharts.forEach((indicator,i)=>stockPaintSubCrosshair(i,indicator,index));
}
function stockPaintMainCrosshair(index,event,pinned){
  const ps=state.stock.priceScale;if(!ps)return;
  const point=ps.points[index],x=stockX(index,ps.points.length),y=value=>ps.margin.top+(ps.max-value)/(ps.max-ps.min)*ps.plotHeight,py=y(Number(point.close));
  const svg=$("stockPriceChart");svg.querySelector("#stockCrosshair").innerHTML=`<line class="crosshair" x1="${x}" y1="${ps.margin.top}" x2="${x}" y2="${ps.margin.top+ps.plotHeight}"/><line class="crosshair" x1="${ps.margin.left}" y1="${py}" x2="${STOCK_SUB_WIDTH-ps.margin.right}" y2="${py}"/>`;
  const active=ps.active;
  const factorRows=active.filter(key=>point[key]!=null).map(key=>{const definition=stockLineDefinitions[key];return `<span class="stock-tooltip-factor"><i style="--tip-color:${definition.color}"></i>${esc(definition.label)} ${stockNumber(point[key])}</span>`;}).join("");
  const pctChg=point.pct_chg!=null?`<span class="${Number(point.pct_chg)>=0?"up":"down"}">涨跌幅 ${stockPercent(point.pct_chg)}</span>`:"";
  const tip=$("stockTooltip"),rect=svg.getBoundingClientRect(),left=event?Math.min(rect.width-285,Math.max(6,event.clientX-rect.left+12)):8,top=event?Math.min(rect.height-Math.max(155,75+active.length*18),Math.max(6,event.clientY-rect.top-55)):8;
  tip.style.left=`${left}px`;tip.style.top=`${top}px`;
  tip.innerHTML=`<strong>${esc(point.trade_date)}${pinned?' <small>已选中</small>':''}</strong><div class="stock-tooltip-grid"><span>开 ${stockNumber(point.open)}</span><span>高 ${stockNumber(point.high)}</span><span>低 ${stockNumber(point.low)}</span><span>收 ${stockNumber(point.close)}</span><span>成交量 ${stockVolumeText(point.volume)}</span>${point.turnover_rate!=null?`<span>换手率 ${stockNumber(point.turnover_rate,2)}%</span>`:""}${pctChg}${factorRows}${state.stock.timeframe==="1d"&&state.stock.overlays.has("xiongmen")?xiongmenTooltip(point):""}</div>`;
  tip.classList.remove("hidden");
}
function stockClearCrosshair(){
  state.stock.hoverIndex=null;
  $("stockPriceChart").querySelector("#stockCrosshair")?.replaceChildren();
  $("stockTooltip").classList.add("hidden");
  const points=stockCurrentPoints(),last=points.at(-1);
  state.stock.subCharts.forEach((indicator,i)=>{
    $(`stockSubCross${i}`)?.replaceChildren();
    const v=$(`stockSubValues${i}`);if(v)v.textContent=subIndicatorValue(indicator,last);
  });
}
function stockPaintSubCrosshair(i,indicator,index){
  const points=stockCurrentPoints(),point=points[index];if(!point)return;
  const def=STOCK_SUB_INDICATORS[indicator],H=def.height,M={left:STOCK_SUB_MARGIN.left,right:STOCK_SUB_MARGIN.right,top:9,bottom:16};
  const x=stockX(index,points.length);
  $(`stockSubCross${i}`).innerHTML=`<line class="crosshair" x1="${x}" y1="${M.top}" x2="${x}" y2="${H-M.bottom}"/>`;
  const v=$(`stockSubValues${i}`);if(v)v.textContent=subIndicatorValue(indicator,point);
}
function subIndicatorValue(indicator,point){
  if(!point)return "—";
  switch(indicator){
    case "volume":return `VOL ${stockVolumeText(point.volume)}`;
    case "turnover":return point.turnover_rate!=null?`换手 ${stockNumber(point.turnover_rate,2)}%`:"换手 —";
    case "macd":return `DIF ${stockNumber(point.macd,3)} · DEA ${stockNumber(point.macd_signal,3)} · MACD ${stockNumber(point.macd_histogram,3)}`;
    case "kdj":return `K ${stockNumber(point.kdj_k,1)} · D ${stockNumber(point.kdj_d,1)} · J ${stockNumber(point.kdj_j,1)}`;
    case "rsi":return `RSI6 ${stockNumber(point.rsi_family?.["6"],1)} · RSI12 ${stockNumber(point.rsi_family?.["12"],1)} · RSI24 ${stockNumber(point.rsi_family?.["24"],1)}`;
    case "cci":return `CCI ${stockNumber(point.cci_family?.["14"],1)}`;
    case "roc":return `ROC20 ${stockPercent(point.roc_family_pct?.["20"])}`;
    case "obv":return `OBV ${stockVolumeText(point.obv)}`;
    case "bias":return `BIAS6 ${stockPercent(point.bias_6)} · 12 ${stockPercent(point.bias_12)} · 24 ${stockPercent(point.bias_24)}`;
    case "ppo":return `PPO ${stockNumber(point.ppo,2)} · 信号 ${stockNumber(point.ppo_signal,2)} · 柱 ${stockNumber(point.ppo_histogram,3)}`;
    case "trix":return `TRIX ${stockNumber(point.trix_12,2)} · 信号 ${stockNumber(point.trix_signal_9,2)}`;
    case "tsi":return `TSI ${stockNumber(point.tsi_25_13,1)}`;
    case "percentb":return `%B ${stockNumber(point.bollinger_percent_b,2)}`;
    case "bandwidth":return `带宽 ${stockNumber(point.bollinger_bandwidth_pct,2)}%`;
    case "natr":return `NATR ${stockNumber(point.natr_14,2)}%`;
    case "squeeze":return `TTM动量 ${stockNumber(point.ttm_squeeze_momentum,2)}`;
    case "pvt":return `PVT ${stockNumber(point.pvt,0)}`;
    case "vroc":return `VROC12 ${stockPercent(point.vroc_12)} · 20 ${stockPercent(point.vroc_20)}`;
    case "force":return `Force ${stockNumber(point.force_index_13_normalized,2)}`;
    default:return "—";
  }
}

function renderStockSubCharts(points){
  const area=$("stockSubChartArea");
  const keys=Object.keys(STOCK_SUB_INDICATORS);
  area.innerHTML=state.stock.subCharts.map((indicator,i)=>{
    const options=keys.map(key=>`<option value="${key}"${key===indicator?" selected":""}>${esc(STOCK_SUB_INDICATORS[key].label)}</option>`).join("");
    return `<div class="stock-subchart" data-sub-index="${i}">
      <div class="stock-subchart-head">
        <select class="stock-subchart-picker" data-sub-picker="${i}" aria-label="切换副图指标">${options}</select>
        <span class="stock-subchart-values" id="stockSubValues${i}" data-sub-values="${i}">—</span>
        <button class="stock-subchart-remove" data-sub-remove="${i}" title="删除此副图" aria-label="删除副图">×</button>
      </div>
      <svg id="stockSubChart${i}" viewBox="0 0 1200 ${STOCK_SUB_INDICATORS[indicator].height}" preserveAspectRatio="none" aria-label="${esc(STOCK_SUB_INDICATORS[indicator].label)}"></svg>
    </div>`;
  }).join("");
  const add=$("stockAddSubChart");
  add.disabled=state.stock.subCharts.length>=3;
  add.classList.toggle("hidden",state.stock.subCharts.length>=3);
  area.querySelectorAll("[data-sub-picker]").forEach(sel=>{
    sel.onchange=()=>{state.stock.subCharts[Number(sel.dataset.subPicker)]=sel.value;scheduleStockRender();};
  });
  state.stock.subCharts.forEach((indicator,i)=>renderSubIndicator(i,indicator,points));
}

function renderSubIndicator(i,indicator,points){
  const svg=$(`stockSubChart${i}`);if(!svg)return;
  const def=STOCK_SUB_INDICATORS[indicator],W=STOCK_SUB_WIDTH,H=def.height,M={left:STOCK_SUB_MARGIN.left,right:STOCK_SUB_MARGIN.right,top:9,bottom:16};
  const plotWidth=W-M.left-M.right,plotHeight=H-M.top-M.bottom,x=index=>stockX(index,points.length);
  let markup=subIndicatorHasData(indicator,points)?subIndicatorMarkup(indicator,points,x,M,W,H,plotWidth,plotHeight):`<text x="600" y="${H/2}" text-anchor="middle" class="axis-label">${subIndicatorEmptyText(indicator)}</text>`;
  markup+=`<g class="sub-crosshair" id="stockSubCross${i}"></g><rect class="hit-area" x="${M.left}" y="${M.top}" width="${plotWidth}" height="${plotHeight}"/>`;
  svg.innerHTML=markup;
  const hit=svg.querySelector(".hit-area");
  if(hit){
    hit.onpointermove=event=>{if(!state.stock.drag.active)stockSyncCrosshair(stockHitIndex(event,svg,points.length),event,false);};
    hit.onclick=event=>{if(state.stock.drag.moved)return;const index=stockHitIndex(event,svg,points.length);state.stock.selectedTradeDate=points[index].trade_date;stockSyncCrosshair(index,event,true);};
    hit.onpointerleave=()=>stockLeaveCrosshair(points);
  }
  const v=$(`stockSubValues${i}`);if(v)v.textContent=subIndicatorValue(indicator,points.at(-1));
}

function subIndicatorHasData(indicator,points){
  switch(indicator){
    case "turnover":return points.some(p=>p.turnover_rate!=null);
    case "kdj":return points.some(p=>p.kdj_k!=null||p.kdj_d!=null||p.kdj_j!=null);
    case "rsi":return points.some(p=>p.rsi_family?.["6"]!=null);
    case "cci":return points.some(p=>p.cci_family?.["14"]!=null);
    case "roc":return points.some(p=>p.roc_family_pct?.["20"]!=null);
    case "obv":return points.some(p=>p.obv!=null);
    case "bias":return points.some(p=>p.bias_6!=null||p.bias_12!=null||p.bias_24!=null);
    case "ppo":return points.some(p=>p.ppo!=null);
    case "trix":return points.some(p=>p.trix_12!=null);
    case "tsi":return points.some(p=>p.tsi_25_13!=null);
    case "percentb":return points.some(p=>p.bollinger_percent_b!=null);
    case "bandwidth":return points.some(p=>p.bollinger_bandwidth_pct!=null);
    case "natr":return points.some(p=>p.natr_14!=null);
    case "squeeze":return points.some(p=>p.ttm_squeeze_momentum!=null);
    case "pvt":return points.some(p=>p.pvt!=null);
    case "vroc":return points.some(p=>p.vroc_12!=null||p.vroc_20!=null);
    case "force":return points.some(p=>p.force_index_13_normalized!=null);
    default:return points.length>0;
  }
}
function subIndicatorEmptyText(indicator){
  if(indicator==="turnover")return stockIsEtf()?"仅个股提供换手率":"仅日线提供换手率";
  return "该指标无逐日数据";
}

function subIndicatorMarkup(indicator,points,x,M,W,H,plotWidth,plotHeight){
  const step=plotWidth/Math.max(points.length,1),barWidth=Math.max(1,Math.min(7,step*.6));
  if(indicator==="volume"){
    const max=Math.max(...points.map(p=>Number(p.volume)||0),1),unit=stockVolumeScale(max).unit,base=M.top+plotHeight;
    let out=`<line class="grid-line" x1="${M.left}" y1="${base}" x2="${W-M.right}" y2="${base}"/>`;
    for(let t=0;t<=2;t++){const v=max*(2-t)/2,py=M.top+plotHeight*t/2;out+=`<line class="grid-line" x1="${M.left}" y1="${py}" x2="${W-M.right}" y2="${py}"/><text class="axis-label" x="${W-M.right+8}" y="${py+3}">${stockVolumeText(v,unit).replace(` ${unit}`,"")}</text>`;}
    points.forEach((p,idx)=>{const v=Number(p.volume)||0,bh=v/max*plotHeight;out+=`<rect class="${Number(p.close)>=Number(p.open)?"bar-up":"bar-down"}" x="${x(idx)-barWidth/2}" y="${base-bh}" width="${barWidth}" height="${Math.max(1,bh)}" opacity=".72"/>`;});
    return out;
  }
  if(indicator==="turnover"){
    const values=points.map(p=>p.turnover_rate!=null?Number(p.turnover_rate):null);
    const max=Math.max(...values.map(v=>v||0),0.1),base=M.top+plotHeight,y=v=>M.top+plotHeight-(v/max)*plotHeight;
    let out=`<line class="grid-line" x1="${M.left}" y1="${base}" x2="${W-M.right}" y2="${base}"/>`;
    for(let t=0;t<=2;t++){const v=max*(2-t)/2,py=M.top+plotHeight*t/2;out+=`<line class="grid-line" x1="${M.left}" y1="${py}" x2="${W-M.right}" y2="${py}"/><text class="axis-label" x="${W-M.right+8}" y="${py+3}">${stockNumber(v,1)}</text>`;}
    points.forEach((p,idx)=>{const v=values[idx];if(v==null)return;const bh=v/max*plotHeight;out+=`<rect class="${Number(p.close)>=Number(p.open)?"bar-up":"bar-down"}" x="${x(idx)-barWidth/2}" y="${base-bh}" width="${barWidth}" height="${Math.max(1,bh)}" opacity=".55"/>`;});
    const ma20=values.map((v,idx)=>{let s=0,c=0;for(let j=Math.max(0,idx-19);j<=idx;j++){if(values[j]!=null){s+=values[j];c++;}}return c?s/c:null;});
    let line="";ma20.forEach((v,idx)=>{if(v!=null)line+=`${line?"L":"M"}${x(idx).toFixed(2)},${y(v).toFixed(2)} `;});
    if(line)out+=`<path class="factor-line" d="${line.trim()}" stroke="#d19b3f"/>`;
    return out;
  }
  if(indicator==="macd"){
    const values=points.flatMap(p=>[p.macd,p.macd_signal,p.macd_histogram]).map(Number).filter(Number.isFinite),extent=Math.max(...values.map(Math.abs),.01),y=v=>M.top+(extent-v)/(2*extent)*plotHeight,zero=y(0);
    let out=`<line class="grid-line" x1="${M.left}" y1="${zero}" x2="${W-M.right}" y2="${zero}"/>`;
    points.forEach((p,idx)=>{const v=Number(p.macd_histogram)||0,target=y(v);out+=`<rect class="${v>=0?"macd-positive":"macd-negative"}" x="${x(idx)-barWidth/2}" y="${Math.min(zero,target)}" width="${barWidth}" height="${Math.max(1,Math.abs(zero-target))}" opacity=".65"/>`;});
    out+=`<path class="factor-line" d="${stockPath(points,"macd",x,y)}" stroke="#348fcb"/><path class="factor-line" d="${stockPath(points,"macd_signal",x,y)}" stroke="#d19b3f"/>`;
    return out;
  }
  if(indicator==="kdj")return subMultiLineMarkup(points,[{get:p=>p.kdj_k,color:"#348fcb"},{get:p=>p.kdj_d,color:"#d19b3f"},{get:p=>p.kdj_j,color:"#c94848"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:20,label:"20"},{v:80,label:"80"}],domain:[0,100]});
  if(indicator==="rsi")return subMultiLineMarkup(points,[{get:p=>p.rsi_family?.["6"],color:"#348fcb"},{get:p=>p.rsi_family?.["12"],color:"#d19b3f"},{get:p=>p.rsi_family?.["24"],color:"#c94848"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:30,label:"30"},{v:70,label:"70"}],domain:[0,100]});
  if(indicator==="cci")return subMultiLineMarkup(points,[{get:p=>p.cci_family?.["14"],color:"#348fcb"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:100,label:"+100"},{v:-100,label:"-100"}]});
  if(indicator==="roc")return subMultiLineMarkup(points,[{get:p=>p.roc_family_pct?.["20"],color:"#348fcb"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:0,label:"0"}]});
  if(indicator==="obv")return subMultiLineMarkup(points,[{get:p=>p.obv,color:"#35a78a"}],x,M,W,H,plotWidth,plotHeight,{});
  if(indicator==="bias")return subMultiLineMarkup(points,[{get:p=>p.bias_6,color:"#348fcb"},{get:p=>p.bias_12,color:"#d19b3f"},{get:p=>p.bias_24,color:"#c94848"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:0,label:"0"}]});
  if(indicator==="ppo"){
    const values=points.flatMap(p=>[p.ppo,p.ppo_signal,p.ppo_histogram]).map(Number).filter(Number.isFinite),extent=Math.max(...values.map(Math.abs),.01),y=v=>M.top+(extent-v)/(2*extent)*plotHeight,zero=y(0);
    let out=`<line class="grid-line" x1="${M.left}" y1="${zero}" x2="${W-M.right}" y2="${zero}"/>`;
    points.forEach((p,idx)=>{const v=Number(p.ppo_histogram)||0,target=y(v);out+=`<rect class="${v>=0?"macd-positive":"macd-negative"}" x="${x(idx)-barWidth/2}" y="${Math.min(zero,target)}" width="${barWidth}" height="${Math.max(1,Math.abs(zero-target))}" opacity=".65"/>`;});
    out+=`<path class="factor-line" d="${stockPath(points,"ppo",x,y)}" stroke="#348fcb"/><path class="factor-line" d="${stockPath(points,"ppo_signal",x,y)}" stroke="#d19b3f"/>`;
    return out;
  }
  if(indicator==="trix")return subMultiLineMarkup(points,[{get:p=>p.trix_12,color:"#348fcb"},{get:p=>p.trix_signal_9,color:"#d19b3f"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:0,label:"0"}]});
  if(indicator==="tsi")return subMultiLineMarkup(points,[{get:p=>p.tsi_25_13,color:"#35a78a"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:0,label:"0"}]});
  if(indicator==="percentb")return subMultiLineMarkup(points,[{get:p=>p.bollinger_percent_b,color:"#348fcb"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:0,label:"0"},{v:0.5,label:"0.5"},{v:1,label:"1"}],domain:[0,1]});
  if(indicator==="bandwidth")return subMultiLineMarkup(points,[{get:p=>p.bollinger_bandwidth_pct,color:"#348fcb"}],x,M,W,H,plotWidth,plotHeight,{});
  if(indicator==="natr")return subMultiLineMarkup(points,[{get:p=>p.natr_14,color:"#d19b3f"}],x,M,W,H,plotWidth,plotHeight,{});
  if(indicator==="squeeze"){
    const values=points.map(p=>Number(p.ttm_squeeze_momentum)||0),max=Math.max(...values.map(Math.abs),.01),zero=M.top+plotHeight/2,y=v=>zero-(v/(2*max))*plotHeight;
    let out=`<line class="grid-line" x1="${M.left}" y1="${zero}" x2="${W-M.right}" y2="${zero}"/>`;
    points.forEach((p,idx)=>{const v=Number(p.ttm_squeeze_momentum)||0,target=y(v);out+=`<rect class="${v>=0?"macd-positive":"macd-negative"}" x="${x(idx)-barWidth/2}" y="${Math.min(zero,target)}" width="${barWidth}" height="${Math.max(1,Math.abs(zero-target))}" opacity=".65"/>`;});
    return out;
  }
  if(indicator==="pvt")return subMultiLineMarkup(points,[{get:p=>p.pvt,color:"#35a78a"}],x,M,W,H,plotWidth,plotHeight,{});
  if(indicator==="vroc")return subMultiLineMarkup(points,[{get:p=>p.vroc_12,color:"#348fcb"},{get:p=>p.vroc_20,color:"#d19b3f"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:0,label:"0"}]});
  if(indicator==="force")return subMultiLineMarkup(points,[{get:p=>p.force_index_13_normalized,color:"#c94848"}],x,M,W,H,plotWidth,plotHeight,{refs:[{v:0,label:"0"}]});
  return "";
}

function subMultiLineMarkup(points,series,x,M,W,H,plotWidth,plotHeight,opts={}){
  const allValues=points.flatMap(p=>series.map(s=>s.get(p))).map(Number).filter(Number.isFinite);
  let lo,hi;
  if(opts.domain){[lo,hi]=opts.domain;}else{lo=Math.min(...allValues);hi=Math.max(...allValues);}
  if(lo===hi){lo-=1;hi+=1;}
  if(opts.refs)opts.refs.forEach(r=>{lo=Math.min(lo,r.v);hi=Math.max(hi,r.v);});
  const span=Math.max(hi-lo,1e-9),y=v=>M.top+(hi-v)/span*plotHeight;
  let out="";
  if(opts.refs)opts.refs.forEach(r=>{const yy=y(r.v);out+=`<line class="grid-line" x1="${M.left}" y1="${yy}" x2="${W-M.right}" y2="${yy}"/><text class="axis-label" x="${W-M.right+8}" y="${yy+3}">${r.label}</text>`;});
  out+=`<text class="axis-label" x="${W-M.right+8}" y="${M.top+3}">${stockNumber(hi,1)}</text><text class="axis-label" x="${W-M.right+8}" y="${M.top+plotHeight}">${stockNumber(lo,1)}</text>`;
  series.forEach(s=>{let path="",drawing=false;points.forEach((p,idx)=>{const v=s.get(p);if(v==null||!Number.isFinite(v)){drawing=false;return;}path+=`${drawing?"L":"M"}${x(idx).toFixed(2)},${y(v).toFixed(2)} `;drawing=true;});if(path)out+=`<path class="factor-line" d="${path.trim()}" stroke="${s.color}"/>`;});
  return out;
}

function renderStockFactors(timeframe,points){
  const trend=timeframe.trend||{},momentum=timeframe.momentum||{},volatility=timeframe.volatility||{},strength=timeframe.trend_strength||{},volume=timeframe.volume_price||{},analysis=volume.analysis||{},latest=points.at(-1)||{},previous=points.at(-2)||latest,change=Number(previous.close)?(Number(latest.close)/Number(previous.close)-1)*100:null,niumen=trend.systems?.niumen_breakout||{},niumenValues=niumen.values||{},cost=analysis.transaction_cost_lines?.windows||{};
  $("stockClose").textContent=stockNumber(latest.close);$("stockChange").textContent=stockPercent(change);$("stockChange").className=change>0?"up":change<0?"down":"";$("stockDate").textContent=`${latest.trade_date||"—"} · ${state.stock.timeframe==="1d"?"日线":state.stock.timeframe==="1w"?"周线":"月线"}`;
  $("stockTrend").textContent=stockStateLabel(trend.regime);$("stockTrendDetail").textContent=`MA20 ${stockNumber(trend.moving_averages?.["20"])} · MA60 ${stockNumber(trend.moving_averages?.["60"])}`;
  const histogram=trend.macd!=null&&trend.macd_signal!=null?Number(trend.macd)-Number(trend.macd_signal):null;$("stockMacd").textContent=histogram==null?"—":histogram>=0?"多头动能":"空头动能";$("stockMacdDetail").textContent=`DIF ${stockNumber(trend.macd,3)} · DEA ${stockNumber(trend.macd_signal,3)} · 柱 ${stockNumber(histogram,3)}`;
  $("stockRsi").textContent=`RSI ${stockNumber(momentum.rsi_14,1)}`;$("stockKdj").textContent=`K ${stockNumber(momentum.kdj?.k,1)} · D ${stockNumber(momentum.kdj?.d,1)} · J ${stockNumber(momentum.kdj?.j,1)}`;
  if(state.stock.timeframe==="1d"){$("stockCost").textContent=`${stockNumber(cost["20_day"]?.value||latest.cost_20)} / ${stockNumber(cost["60_day"]?.value||latest.cost_60)}`;$("stockCostDistance").textContent=`距20日成本 ${stockPercent(cost["20_day"]?.distance_from_close_pct)} · 距60日成本 ${stockPercent(cost["60_day"]?.distance_from_close_pct)}`;$("stockNiumen").textContent=stockStateLabel(niumen.state);$("stockNiumenDetail").textContent=`牛门 ${stockNumber(niumenValues.niumen_line||latest.niumen_line)} · 确认 ${stockNumber(niumenValues.confirmation_line||latest.niumen_confirmation_line)}`;}else{$("stockCost").textContent="仅日线提供";$("stockCostDistance").textContent="成本线按20/60个交易日滚动计算";$("stockNiumen").textContent="仅日线提供";$("stockNiumenDetail").textContent="牛门线周期固定为交易日，不跨周期套用";}
  const xiongmen=xiongmenSummary(trend.systems?.xiongmen_rebound);
  $("stockXiongmen").textContent=xiongmen.label;$("stockXiongmenDetail").textContent=xiongmen.detail;
  const regime=analysis.price_volume_regime||{},boll=volatility.bollinger_20||{},bollWidth=Number(boll.middle)?(Number(boll.upper)-Number(boll.lower))/Number(boll.middle)*100:null,supertrend=trend.systems?.supertrend_10_3||{};$("stockVolumeState").textContent=stockStateLabel(regime.classification||analysis.activity?.state);$("stockVolumeDetail").textContent=`量能 5/20 比 ${stockNumber(volume.volume_5_to_20_ratio,2)} · 最新 ${stockVolumeText(latest.volume)}`;
  $("stockVolatility").textContent=`ATR ${stockNumber(volatility.atr_14)}`;$("stockVolatilityDetail").textContent=`20期年化 ${stockPercent(volatility.annualized_volatility_20_period_pct)} · BOLL宽 ${stockPercent(bollWidth)}`;
  $("stockStrength").textContent=`ADX ${stockNumber(strength.adx_14,1)}`;$("stockStrengthDetail").textContent=`+DI ${stockNumber(strength.plus_di_14,1)} · −DI ${stockNumber(strength.minus_di_14,1)} · Supertrend ${stockStateLabel(supertrend.direction)}`;
  $("stockMoneyFlow").textContent=`MFI ${stockNumber(momentum.mfi_14,1)}`;$("stockMoneyFlowDetail").textContent=`CMF20 ${stockNumber(volume.chaikin_money_flow_20,3)} · StochRSI ${stockNumber(momentum.stochastic_rsi_14,1)}`;
  const emas=trend.exponential_moving_averages||{},bbi=trend.bbi||{},bias=trend.bias||{},ppo=momentum.ppo_12_26_9||{},squeeze=volatility.ttm_squeeze||{};
  $("stockEmaBbi").textContent=`EMA20 ${stockNumber(emas["20"])} · BBI ${stockNumber(bbi.value)}`;$("stockEmaBbiDetail").textContent=`EMA50 ${stockNumber(emas["50"])} · EMA200 ${stockNumber(emas["200"])} · 距BBI ${stockPercent(bbi.distance_from_close_pct)}`;
  $("stockBiasPpo").textContent=`BIAS6 ${stockPercent(bias["6"])} · PPO ${stockNumber(ppo.value,2)}`;$("stockBiasPpoDetail").textContent=`BIAS12 ${stockPercent(bias["12"])} · BIAS24 ${stockPercent(bias["24"])} · PPO柱 ${stockNumber(ppo.histogram,3)}`;
  $("stockSqueeze").textContent=squeeze.on===true?"挤压中":squeeze.on===false?"未挤压":"历史不足";$("stockSqueezeDetail").textContent=`NATR14 ${stockPercent(volatility.natr_14_pct)} · 动量 ${stockNumber(squeeze.momentum,3)}`;
  $("stockVolumeMomentum").textContent=`VROC12 ${stockPercent(volume.vroc_12_pct)}`;$("stockVolumeMomentumDetail").textContent=`PVT20变化 ${stockNumber(volume.pvt_change_20)} · VROC20 ${stockPercent(volume.vroc_20_pct)} · Force归一 ${stockPercent(volume.force_index_13_normalized_pct)}`;
}

function stockWatchlistContains(code){return state.stock.watchlist.some(item=>item.ts_code===code);}

const stockModulePanels={market:"stockModuleMarket",chips:"stockModuleChips",fundamentals:"stockModuleFundamentals",events:"stockModuleEvents",sectors:"stockModuleSectors",chain:"stockModuleChain",navshares:"stockModuleNavShares"};
const stockModuleEndpoints={chips:"chips",fundamentals:"fundamentals?periods=8&include_external=false",events:"events",sectors:"sector-context",chain:"industry-chain"};
function stockSelectedCode(){return state.stock.selected?.ts_code||state.stock.selected?.code;}
function stockIsEtf(){return state.stock.selected?.asset_type==="etf";}
function selectStockModule(name){
  state.stock.module=name;
  document.querySelectorAll("[data-stock-module]").forEach(button=>button.classList.toggle("active",button.dataset.stockModule===name));
  document.querySelectorAll("[data-stock-module-panel]").forEach(panel=>panel.classList.toggle("hidden",panel.dataset.stockModulePanel!==name));
  if(name==="market")return;
  const code=stockSelectedCode();if(!code)return;
  const key=`${code}:${name}`,panel=$(stockModulePanels[name]);
  if(state.stock.modules[key]){renderStockModule(name,state.stock.modules[key]);return;}
  fetchStockModule(name,code,key,panel);
}
async function fetchStockModule(name,code,key,panel){
  if(state.stock.moduleBusy[key])return;state.stock.moduleBusy[key]=true;
  panel.innerHTML='<div class="module-loading">加载中…</div>';
  try{
    const url=name==="navshares"
      ?`/api/v1/research/etfs/${encodeURIComponent(code)}/nav-shares?lookback_days=400`
      :`/api/v1/research/stocks/${encodeURIComponent(code)}/${stockModuleEndpoints[name]}`;
    const response=await api(url);
    if(stockSelectedCode()!==code)return;
    state.stock.modules[key]=response;
    renderStockModule(name,response);
  }catch(error){panel.innerHTML=`<div class="module-loading">加载失败：${esc(error.message)}（<button class="task-link" data-stock-module-retry="${esc(name)}">重试</button>）</div>`;}
  finally{delete state.stock.moduleBusy[key];}
}
function resetStockModules(){
  state.stock.modules={};state.stock.moduleBusy={};state.stock.module="market";
  const isEtf=stockIsEtf();
  document.querySelectorAll("[data-stock-module]").forEach(button=>{
    const name=button.dataset.stockModule;
    const visible=name==="market"||(name==="navshares"&&isEtf)||(name!=="navshares"&&!button.hasAttribute("data-stock-only"))||(name!=="navshares"&&button.hasAttribute("data-stock-only")&&!isEtf);
    button.classList.toggle("hidden",!visible);
    button.classList.toggle("active",name==="market");
  });
  document.querySelectorAll("[data-stock-module-panel]").forEach(panel=>{
    const name=panel.dataset.stockModulePanel;
    const isMarket=name==="market";
    panel.classList.toggle("hidden",!isMarket);
    if(!isMarket)panel.innerHTML="";
  });
}
const moduleCard=(label,value,detail="")=>`<article class="module-card"><span>${esc(label)}</span><strong>${value}</strong>${detail?`<small>${detail}</small>`:""}</article>`;
const moduleTable=(headers,rows,emptyText="暂无数据")=>`<div class="table-wrap module-table"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.length?rows.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join("")}</tr>`).join(""):`<tr><td colspan="${headers.length}" class="empty-row">${esc(emptyText)}</td></tr>`}</tbody></table></div>`;
const moduleSection=(title,inner,note="")=>`<div class="module-section"><div class="module-section-head"><h4>${esc(title)}</h4>${note?`<small>${esc(note)}</small>`:""}</div>${inner}</div>`;

function renderStockModule(name,response){
  const panel=$(stockModulePanels[name]);if(!panel)return;
  const data=response?.data||{},meta=response?.meta||{};
  if(name==="chips")panel.innerHTML=renderStockChipsModule(data,meta);
  else if(name==="fundamentals")panel.innerHTML=renderStockFundamentalsModule(data,meta);
  else if(name==="events")panel.innerHTML=renderStockEventsModule(data,meta);
  else if(name==="sectors")panel.innerHTML=renderStockSectorsModule(data,meta);
  else if(name==="chain")panel.innerHTML=renderStockChainModule(data,meta);
  else if(name==="navshares")panel.innerHTML=renderStockNavSharesModule(data,meta);
}

function renderStockChipsModule(data,meta){
  const latest=data.latest||{},trend=data.trend||[],distribution=data.distribution||{},bins=distribution.bins||[];
  if(!trend.length)return `<div class="module-loading">该股票在窗口内没有筹码数据（cyq_perf 未覆盖或已停采）。</div>`;
  const close=Number(state.stock.response?.data?.observation?.close);
  const winner=latest.winner_rate==null?"—":`${stockNumber(latest.winner_rate,2)}%`;
  const costRange=latest.cost_5pct!=null?`${stockNumber(latest.cost_5pct)} – ${stockNumber(latest.cost_95pct)}`:"—";
  const position=latest.cost_5pct!=null&&latest.cost_95pct!=null&&Number.isFinite(close)&&close>latest.cost_5pct&&close<latest.cost_95pct?`${((close-latest.cost_5pct)/(latest.cost_95pct-latest.cost_5pct)*100).toFixed(1)}%`:"—";
  let histogram="";
  if(bins.length){
    const maxPercent=Math.max(...bins.map(bin=>bin.percent||0),.0001),width=880,height=170,margin={left:8,right:8,top:12,bottom:22},plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom,prices=bins.map(bin=>bin.price).filter(v=>v!=null),min=Math.min(...prices),max=Math.max(...prices),barWidth=plotWidth/bins.length;
    const x=value=>margin.left+(value-min)/(max-min||1)*plotWidth,y=value=>margin.top+plotHeight*(1-Math.min(value/maxPercent,1));
    histogram=`<svg viewBox="0 0 ${width} ${height}" class="chips-histogram" aria-label="筹码分布">`;
    bins.forEach(bin=>{const px=x(bin.price),h=plotHeight*(bin.percent||0)/maxPercent;histogram+=`<rect class="chip-bar" x="${px-barWidth/2+.4}" y="${margin.top+plotHeight-h}" width="${Math.max(barWidth-.8,1)}" height="${Math.max(h,1)}"/>`;});
    if(Number.isFinite(close)&&close>=min&&close<=max)histogram+=`<line class="chip-marker" x1="${x(close)}" y1="${margin.top}" x2="${x(close)}" y2="${margin.top+plotHeight}"/><text class="chip-marker-text" x="${x(close)}" y="${margin.top-2}" text-anchor="middle">现价 ${stockNumber(close)}</text>`;
    if(latest.weight_avg!=null&&latest.weight_avg>=min&&latest.weight_avg<=max)histogram+=`<line class="chip-marker avg" x1="${x(latest.weight_avg)}" y1="${margin.top}" x2="${x(latest.weight_avg)}" y2="${margin.top+plotHeight}"/><text class="chip-marker-text avg" x="${x(latest.weight_avg)}" y="${margin.top-2}" text-anchor="middle">均成本 ${stockNumber(latest.weight_avg)}</text>`;
    histogram+=`<text class="axis-label" x="${margin.left}" y="${height-6}">${stockNumber(min)}</text><text class="axis-label" x="${width-margin.right}" y="${height-6}" text-anchor="end">${stockNumber(max)}</text></svg><p class="module-note">筹码分布日期 ${esc(distribution.trade_date||"—")}（数据集 cyq_chips）</p>`;
  }else histogram=`<p class="module-note">当日筹码分布明细（cyq_chips）缺失，仅展示性能指标。</p>`;
  let spark="";
  if(trend.length>2){
    const width=880,height=90,pad=8,winnerValues=trend.map(row=>Number(row.winner_rate)).filter(Number.isFinite);
    if(winnerValues.length>2){
      const min=Math.min(...winnerValues),max=Math.max(...winnerValues),step=(width-pad*2)/(trend.length-1);
      const y=value=>pad+(height-pad*2)*(1-(value-min)/(max-min||1));
      const path=trend.map((row,index)=>Number.isFinite(Number(row.winner_rate))?`${index?"L":"M"}${(pad+index*step).toFixed(1)},${y(Number(row.winner_rate)).toFixed(1)} `:"").join("");
      spark=`<svg viewBox="0 0 ${width} ${height}" class="chips-sparkline"><path class="factor-line" d="${path.trim()}" stroke="#b96a93"/><text class="axis-label" x="${pad}" y="${height-2}">${esc(trend[0].trade_date||"")}</text><text class="axis-label" x="${width-pad}" y="${height-2}" text-anchor="end">${esc(trend.at(-1).trade_date||"")}</text></svg>`;
    }
  }
  const trendRows=trend.slice(-10).reverse().map(row=>[esc(row.trade_date),row.winner_rate==null?"—":`${stockNumber(row.winner_rate,2)}%`,stockNumber(row.cost_5pct),stockNumber(row.cost_50pct),stockNumber(row.cost_95pct),stockNumber(row.weight_avg)]);
  return `${moduleSection("筹码概览",`<div class="module-card-grid">${moduleCard("获利比例",winner,latest.trade_date?`截至 ${esc(latest.trade_date)}`:"")}${moduleCard("平均成本",stockNumber(latest.weight_avg))}${moduleCard("90% 成本区间",costRange,`现价位于区间 ${position}`)}${moduleCard("历史区间",`${stockNumber(latest.his_low)} – ${stockNumber(latest.his_high)}`)}</div>`)}
  ${moduleSection("当日筹码分布",histogram)}
  ${spark?moduleSection("获利比例走势（近 120 日）",spark):""}
  ${moduleSection("成本与获利明细",moduleTable(["交易日","获利比例","5%成本","50%成本","95%成本","加权成本"],trendRows),"窗口内没有筹码数据")}`;
}

function renderStockFundamentalsModule(data,meta){
  const profile=data.profile||{},latest=data.latest||{},periods=data.periods||[],segments=data.segments||{},evidence=meta.provider_evidence?.normalized||data.provider_evidence?.normalized||{};
  const quality=meta.quality||{};
  const prof=latest.profitability||{},growth=latest.growth||{},solvency=latest.solvency||{},efficiency=latest.efficiency||{},qualityMetrics=latest.quality||{},dupont=latest.dupont||{};
  const rating=evidence.rating_consensus||{},consensus=evidence.consensus_revision||{},target=evidence.target_price||{};
  const periodRows=periods.slice(0,8).map(p=>[esc(p.period||"—"),p.profitability?.roe_pct==null?"—":`${stockNumber(p.profitability.roe_pct,2)}%`,p.growth?.revenue_yoy_pct==null?"—":stockPercent(p.growth.revenue_yoy_pct),p.growth?.net_income_yoy_pct==null?"—":stockPercent(p.growth.net_income_yoy_pct),p.profitability?.gross_margin_pct==null?"—":`${stockNumber(p.profitability.gross_margin_pct,2)}%`,p.solvency?.debt_to_assets_pct==null?"—":`${stockNumber(p.solvency.debt_to_assets_pct,1)}%`,esc(p.announced_at||"—")]);
  const segItems=(segments.items||[]).slice(0,10).map(item=>[esc(item.item||"—"),({P:"产品",D:"地区",I:"行业"})[item.code]||esc(item.code||"—"),stockNumber(item.sales==null?null:item.sales/1e8,2)+" 亿",stockNumber(item.profit==null?null:item.profit/1e8,2)+" 亿",item.sales_share_pct==null?"—":`${stockNumber(item.sales_share_pct,2)}%`]);
  const ratingSummary=rating.status==="available"?`${moduleCard("机构评级",`${stockNumber(rating.positive,0)} 多 / ${stockNumber(rating.negative,0)} 空`,`观察日 ${esc(String(rating.observation_date||"—").slice(0,10))} · 机构 ${stockNumber(rating.organizations,0)} 家`)}${moduleCard("评级正向占比",rating.positive_share_pct==null?"—":`${stockNumber(rating.positive_share_pct,1)}%`,`上调 ${stockNumber(rating.upgrades,0)} · 下调 ${stockNumber(rating.downgrades,0)}`)}`:"";
  const targetCard=target.status==="available"?moduleCard("目标价（蚂蚁）",stockNumber(target.average),`中位 ${stockNumber(target.median)} · 样本 ${stockNumber(target.observations,0)} 家`):"";
  return `${moduleSection("公司档案",`<div class="module-card-grid">${moduleCard("行业",esc(profile.industry||"—"))}${moduleCard("上市日期",esc(profile.list_date||"—"))}${moduleCard("市场",esc([profile.market,profile.exchange].filter(Boolean).join(" · ")||"—"))}${moduleCard("最新报告期",esc(latest.period||"—"),latest.announced_at?`公告于 ${esc(latest.announced_at)}`:"")}</div>`,quality.status==="ready"?"":"部分数据缺失或提示，见质量标记")}
  ${moduleSection("盈利与成长",`<div class="module-card-grid">${moduleCard("ROE",prof.roe_pct==null?"—":`${stockNumber(prof.roe_pct,2)}%`,`ROIC ${stockNumber(prof.roic_pct,2)}%`)}${moduleCard("毛利率 / 净利率",`${stockNumber(prof.gross_margin_pct,1)}% / ${stockNumber(prof.net_margin_pct,1)}%`)}${moduleCard("营收同比",stockPercent(growth.revenue_yoy_pct),`净利润同比 ${stockPercent(growth.net_income_yoy_pct)}`)}${moduleCard("资产负债率",solvency.debt_to_assets_pct==null?"—":`${stockNumber(solvency.debt_to_assets_pct,1)}%`,`流动比率 ${stockNumber(solvency.current_ratio,2)}`)}${moduleCard("经营现金流/净利",stockNumber(qualityMetrics.operating_cash_to_net_income,2),`自由现金流 ${stockNumber(qualityMetrics.free_cashflow==null?null:qualityMetrics.free_cashflow/1e8,1)} 亿`)}${moduleCard("杜邦 ROE",dupont.reported_roe_pct==null?"—":`${stockNumber(dupont.reported_roe_pct,2)}%`,`权益乘数 ${stockNumber(dupont.equity_multiplier,2)}`)}</div>`)}
  ${ratingSummary||targetCard?moduleSection("一致预期（蚂蚁佐证）",`<div class="module-card-grid">${ratingSummary}${targetCard}</div>`,"来自蚂蚁查询穿透，已缓存，不落业务表"):""}
  ${moduleSection("财务周期序列",moduleTable(["报告期","ROE","营收同比","净利同比","毛利率","资产负债率","公告日"],periodRows,"暂无财务周期数据"))}
  ${moduleSection("主营构成",moduleTable(["业务项","类型","收入","利润","收入占比"],segItems,segments.period?`${esc(segments.period)} 无主营构成明细`:"暂无主营构成数据"),segments.period?`报告期 ${esc(segments.period)}`:"")}`;
}

function renderStockEventsModule(data,meta){
  const express=data.express||[],forecast=data.forecast||[],topList=data.top_list||[],limitList=data.limit_list||[],floats=data.share_float||{},pledge=data.pledge||{},holders=data.holder_number_trend||[],blocks=data.block_trade||[];
  const pct=(value)=>value==null?"—":stockPercent(value);
  const expressRows=express.map(row=>[esc(row.end_date||"—"),esc(row.ann_date||"—"),stockNumber(row.revenue==null?null:row.revenue/1e8,1)+" 亿",pct(row.yoy_sales),stockNumber(row.n_income==null?null:row.n_income/1e8,1)+" 亿",pct(row.yoy_net_profit),stockNumber(row.diluted_roe==null?null:row.diluted_roe,2)+"%"]);
  const forecastRows=forecast.map(row=>[esc(row.end_date||"—"),esc(row.type||"—"),pct(row.p_change_min)+" ~ "+pct(row.p_change_max),stockNumber(row.net_profit_min==null?null:row.net_profit_min/1e8,1)+" ~ "+stockNumber(row.net_profit_max==null?null:row.net_profit_max/1e8,1)+" 亿",`<span title="${esc(row.summary||"")}">${esc(String(row.summary||"—").slice(0,24))}</span>`]);
  const topRows=topList.map(row=>[esc(row.trade_date||"—"),esc(row.reason||"—"),stockNumber(row.l_sell==null?null:row.l_sell/1e8,2)+" 亿",stockNumber(row.l_buy==null?null:row.l_buy/1e8,2)+" 亿",stockNumber(row.net_amount==null?null:row.net_amount/1e8,2)+" 亿",pct(row.net_rate)]);
  const limitRows=limitList.map(row=>[esc(row.trade_date||"—"),esc(row.limit||row.limit_type||"—"),pct(row.pct_chg),stockNumber(row.amount==null?null:row.amount/1e8,2)+" 亿",esc(row.first_time||"—")]);
  const floatRows=(floats.upcoming||[]).slice(0,8).map(row=>[esc(row.float_date||"—"),stockNumber(row.float_share==null?null:row.float_share/1e8,2)+" 亿股",pct(row.float_ratio),esc(row.share_type||"—"),esc(row.holder_name||"—")]);
  const holderRows=holders.map(row=>[esc(row.end_date||row.ann_date||"—"),stockNumber(row.holder_num,0),esc(row.ann_date||"—")]);
  const blockRows=blocks.slice(0,8).map(row=>[esc(row.trade_date||"—"),stockNumber(row.price),stockNumber(row.vol==null?null:row.vol/1e4,2)+" 万股",stockNumber(row.amount==null?null:row.amount/1e8,2)+" 亿",esc(String(row.buyer||"—").slice(0,14))]);
  const pledgeCard=pledge?moduleCard("股权质押",pledge.pledge_ratio==null?"—":`${stockNumber(pledge.pledge_ratio,2)}%`,`质押 ${stockNumber(pledge.pledge_count,0)} 笔 · 未解押 ${stockNumber(pledge.rest_pledge==null?null:pledge.rest_pledge/1e8,2)} 亿股（${esc(pledge.end_date||"")}）`):"";
  return `${pledgeCard?moduleSection("质押与股东",`<div class="module-card-grid">${pledgeCard}${holderRows.length?moduleCard("股东人数最新",stockNumber(holderRows[0][1],0),`报告期 ${holderRows[0][0]}`):""}</div>${holderRows.length>1?moduleTable(["报告期","股东人数","公告日"],holderRows.slice(0,8)):""}`,""):""}
  ${moduleSection("业绩快报（express）",moduleTable(["报告期","公告日","营收","营收同比","净利润","净利同比","稀释ROE"],expressRows,"窗口内没有业绩快报"),"包含 express_vip 采集结果")}
  ${moduleSection("业绩预告（forecast）",moduleTable(["报告期","类型","净利变动幅度","预计净利润","摘要"],forecastRows,"窗口内没有业绩预告"))}
  ${moduleSection("龙虎榜（top_list）",moduleTable(["交易日","上榜原因","卖出","买入","净额","净占比"],topRows,"窗口内未上龙虎榜"))}
  ${moduleSection("涨跌停记录（limit_list_d）",moduleTable(["交易日","类型","涨跌幅","成交额","首次封板"],limitRows,"窗口内无涨跌停记录"))}
  ${moduleSection("限售解禁（share_float）",moduleTable(["解禁日","解禁数量","占总股本","类型","股东"],floatRows,"未来一年无解禁安排"),"同时含近期已解禁记录请见数据集")}
  ${moduleSection("大宗交易（block_trade）",moduleTable(["交易日","成交价","成交量","成交额","买方营业部"],blockRows,"窗口内无大宗交易"))}`;
}

function renderStockSectorsModule(data,meta){
  const sectors=data.sectors||[],peers=data.peers||[];
  if(!sectors.length)return `<div class="module-loading">该股票没有板块归属记录（同花顺/东财/通达信目录未覆盖）。</div>`;
  const cards=sectors.map(sector=>{
    const perf=sector.performance||{},flow=sector.money_flow||{},recent=(perf.recent||[]).slice(-5).reverse();
    const spark=recent.map(day=>`<span class="sector-day ${Number(day.pct_change)>=0?"up":"down"}">${day.pct_change==null?"—":stockPercent(day.pct_change)}</span>`).join("");
    return `<article class="sector-card"><div class="sector-card-head"><strong>${esc(sector.name||sector.sector_code)}</strong><span class="pill info">${esc(sector.category||"—")}</span></div><div class="sector-card-body"><div><small>近 20 日涨幅</small><strong class="${Number(perf.window_return_pct)>=0?"up":"down"}">${stockPercent(perf.window_return_pct)}</strong></div><div><small>近 20 日资金净流</small><strong>${flow.net_amount_sum==null?"—":stockNumber(flow.net_amount_sum/1e8,2)+" 亿"}</strong></div><div><small>权重 / 加入日</small><span>${stockNumber(sector.weight,2)}% · ${esc(sector.in_date||"—")}</span></div></div><div class="sector-card-recent">${spark}</div><code class="sector-code">${esc(sector.sector_code)}</code></article>`;
  }).join("");
  const peerItems=peers.map(peer=>`<button class="dataset-chip link" data-stock-peer="${esc(peer.ts_code)}" title="打开 ${esc(peer.name||peer.ts_code)}">${esc(peer.name||peer.ts_code)}</button>`).join("");
  return `${moduleSection("所属板块（近 20 日表现与资金流）",`<div class="sector-card-grid">${cards}</div>`,"来源：同花顺指数目录；点击近 5 日涨跌查看节奏")}
  ${moduleSection("同行股票（共享板块数排序）",`<div class="peer-chips">${peerItems||'<span class="muted">暂无同行</span>'}</div>`,"点击任意同行直接切换")}`;
}

function renderStockChainModule(data,meta){
  const membership=data.membership||[],tree=data.chain_tree||{},rows=tree.rows||[];
  if(!membership.length)return `<div class="module-loading">蚂蚁产业链未覆盖该股票，或数据源暂不可用（${esc(meta.provider_status||"—")}）。</div>`;
  const m=membership[0];
  const nodeRows=rows.map(row=>{const nodes=row.constituents||[];return [esc(row.node_name||"—"),esc(row.stream_level_desc||"—"),esc(row.parent_node_symbol||"—"),esc(row.is_leaf_node||"—"),nodes.length?`<span class="dataset-more">${nodes.length} 家</span>`:"—"];});
  const currentNode=rows.find(row=>row.node_symbol===m.node_symbol)||rows.find(row=>row.node_name===m.node_name)||{};
  const constituents=(currentNode.constituents||[]).slice(0,40).map(item=>[`<code>${esc(item.stock_symbol||"—")}</code>`,esc(item.stock_name||"—"),`<span title="${esc(item.reason||"")}">${esc(String(item.reason||"—").slice(0,40))}</span>`]);
  return `${moduleSection("归属产业链（蚂蚁查询穿透）",`<div class="module-card-grid">${moduleCard("产业链",esc(m.chain_name||"—"))}${moduleCard("节点",esc(m.node_name||"—"))}${moduleCard("上中下游",esc(m.stream_level_desc||"—"))}</div>${m.reason?`<p class="module-note">归属理由：${esc(m.reason)}</p>`:""}`,"经 QueryBroker 调用蚂蚁接口，结果缓存 24 小时，不落业务表")}
  ${nodeRows.length?moduleSection("产业链结构",moduleTable(["节点","环节","上级节点","节点类型","成分股"],nodeRows)):""}
  ${constituents.length?moduleSection("本节点成分股",moduleTable(["代码","名称","关联理由"],constituents)):""}`;
}

function renderStockNavSharesModule(data,meta){
  const nav=data.nav||{},shares=data.shares||{},premium=data.premium_pct||{},instrument=data.instrument||{};
  const navRows=nav.series||[],shareRows=shares.series||[],flows=shares.flows||[],premiumLatest=premium.latest;
  const latestShare=shareRows.at(-1)?.[1],latestNav=navRows.at(-1)?.[1],accumNav=navRows.at(-1)?.[2];
  const recentFlows=flows.slice(-20),netCreate=recentFlows.reduce((sum,[,v])=>sum+(Number(v)||0),0);
  const maxFlow=recentFlows.reduce((a,[,v])=>Math.abs(Number(v))>Math.abs(a)?Number(v):a,0);
  const cards=`<div class="module-card-grid">
    ${moduleCard("最新单位净值",stockNumber(latestNav,4),`累计净值 ${stockNumber(accumNav,4)} · ${navRows.length} 个净值日`)}
    ${moduleCard("最新溢价率",researchPct(premiumLatest),`二级市场收盘价相对单位净值的偏离`)}
    ${moduleCard("最新份额",`${stockNumber(latestShare,3)} 亿份`,`${shareRows.length} 个份额观测日`)}
    ${moduleCard("近 20 日净申赎",`${netCreate>=0?"+":""}${stockNumber(netCreate,3)} 亿份`,netCreate>0?"净申购（资金流入）":netCreate<0?"净赎回（资金流出）":"份额基本持平")}
    ${moduleCard("近 20 日最大单日变动",`${maxFlow>=0?"+":""}${stockNumber(maxFlow,3)} 亿份`,`${recentFlows.at(0)?.[0]||"—"} → ${recentFlows.at(-1)?.[0]||"—"}`)}
    ${moduleCard("管理机构",esc(instrument.management||"—"),esc(instrument.fund_type||"场内基金"))}
  </div>`;
  let navSvg="",shareSvg="",premiumSvg="";
  if(navRows.length>1){
    const svg=renderInlineLineSvg(navRows.map(r=>[r[0],r[1]]),{color:"#1d9e75",digits:3});
    navSvg=moduleSection("单位净值走势",svg,"基金官方净值（元）");
  }
  if(shareRows.length>1){
    const svg=renderInlineLineSvg(shareRows,{color:"#348fcb",digits:2});
    shareSvg=moduleSection("份额走势（亿份）",svg,"份额增量≈净申购，减量≈净赎回");
  }
  const flowRows=flows.slice().reverse().slice(0,20).map(([day,value])=>[esc(day),`<span class="${value>0?"up":value<0?"down":""}">${value>0?"+":""}${stockNumber(value,3)}</span>`]);
  const flowTable=moduleSection("近期份额变动（申赎估计）",moduleTable(["日期","份额变动（亿份）"],flowRows,"暂无份额变动记录"),"单位亿份");
  return `${cards}${navSvg}${shareSvg}${flowTable}`;
}

function renderInlineLineSvg(series,{color="#348fcb",digits=2}={}){
  const width=880,height=180,margin={left:10,right:64,top:14,bottom:24},pw=width-margin.left-margin.right,ph=height-margin.top-margin.bottom;
  const values=series.map(s=>Number(s[1])).filter(Number.isFinite);
  if(values.length<2)return '<div class="module-loading">数据不足，无法绘制</div>';
  const min=Math.min(...values),max=Math.max(...values),pad=(max-min)||Math.abs(max)*0.02||1,lo=min-pad,hi=max+pad;
  const x=i=>margin.left+(i+0.5)*pw/series.length,y=v=>margin.top+(hi-v)/(hi-lo)*ph;
  let m="";
  for(let t=0;t<=3;t++){const v=hi-(hi-lo)*t/3,py=margin.top+ph*t/3;m+=`<line class="grid-line" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/><text class="axis-label" x="${width-margin.right+6}" y="${py+3}">${stockNumber(v,digits)}</text>`;}
  let path="";series.forEach((s,i)=>{const v=Number(s[1]);if(!Number.isFinite(v))return;path+=`${path?"L":"M"}${x(i).toFixed(2)},${y(v).toFixed(2)} `;});
  m+=`<path class="factor-line" d="${path.trim()}" stroke="${color}" fill="none" stroke-width="1.6"/>`;
  const ticks=Math.min(5,series.length);for(let t=0;t<ticks;t++){const i=Math.round(t*(series.length-1)/Math.max(ticks-1,1));m+=`<text class="axis-label" text-anchor="middle" x="${x(i)}" y="${height-6}">${esc(String(series[i][0]||"").slice(0,10))}</text>`;}
  return `<svg viewBox="0 0 ${width} ${height}" class="module-line-chart" role="img">${m}</svg>`;
}

function stockWatchlistContains(code){return state.stock.watchlist.some(item=>item.ts_code===code);}
function updateStockWatchToggle(){
  const button=$("stockWatchToggle"),code=state.stock.selected?.ts_code||state.stock.selected?.code;if(!button)return;
  const saved=Boolean(code&&stockWatchlistContains(code));button.disabled=!code||state.stock.watchlistBusy;button.classList.toggle("saved",saved);button.textContent=saved?"★ 已在自选":"☆ 加入自选";button.title=saved?"点击后确认移出自选":"加入自选，便于快速切换K线";
}
function renderStockWatchlist(){
  const list=$("stockWatchlist"),selected=state.stock.selected?.ts_code||state.stock.selected?.code;$("stockWatchlistCount").textContent=`${state.stock.watchlist.length} 只`;
  list.innerHTML=state.stock.watchlist.length?state.stock.watchlist.map(item=>`<article class="stock-watch-item ${item.ts_code===selected?"selected":""}"><button class="stock-watch-open" data-watch-open="${esc(item.ts_code)}"><strong>${esc(item.name||item.fullname||item.ts_code)}</strong><small>${esc(item.ts_code)} · ${esc(item.industry||item.market||"A股")}</small></button><button class="stock-watch-remove" data-watch-remove="${esc(item.ts_code)}" aria-label="移出${esc(item.name||item.ts_code)}" title="移出自选">×</button></article>`).join(""):'<div class="stock-watchlist-empty">还没有自选股票。搜索并打开股票后，点击“加入自选”。</div>';
  updateStockWatchToggle();
}
async function loadStockWatchlist(force=false){
  if(state.stock.watchlistLoaded&&!force){renderStockWatchlist();return;}
  try{const result=await api("/api/v1/research/watchlist");state.stock.watchlist=result.data||[];state.stock.watchlistLoaded=true;renderStockWatchlist();}catch(error){notice(`自选加载失败：${error.message}`);}
}
async function addStockWatchlist(code){
  if(state.stock.watchlistBusy)return;state.stock.watchlistBusy=true;updateStockWatchToggle();
  try{await api(`/api/v1/research/watchlist/${encodeURIComponent(code)}`,{method:"POST"});await loadStockWatchlist(true);}catch(error){notice(`加入自选失败：${error.message}`);}finally{state.stock.watchlistBusy=false;updateStockWatchToggle();}
}
async function removeStockWatchlist(code){
  const item=state.stock.watchlist.find(row=>row.ts_code===code),name=item?.name||code;if(!window.confirm(`确认将 ${name}（${code}）移出自选？`))return;
  if(state.stock.watchlistBusy)return;state.stock.watchlistBusy=true;updateStockWatchToggle();
  try{await api(`/api/v1/research/watchlist/${encodeURIComponent(code)}`,{method:"DELETE"});await loadStockWatchlist(true);}catch(error){notice(`移出自选失败：${error.message}`);}finally{state.stock.watchlistBusy=false;updateStockWatchToggle();}
}
function toggleStockWatchlist(){const code=state.stock.selected?.ts_code||state.stock.selected?.code;if(!code)return;stockWatchlistContains(code)?removeStockWatchlist(code):addStockWatchlist(code);}

function renderStockResearch(){
  const response=state.stock.response;if(!response)return;const data=response.data||{},timeframe=data.timeframes?.[state.stock.timeframe];if(!timeframe)return;const allPoints=stockEnsureMacd(timeframe.chart?.points||[]),points=stockVisiblePoints(allPoints),selected=state.stock.selected||{},isEtf=stockIsEtf(),identity=data.instrument?.identity||{},instrument={...selected,...(isEtf?identity:data.instrument||{}),...selected},quality=response.meta?.quality||{};
  $("stockEmpty").classList.add("hidden");$("stockWorkspace").classList.remove("hidden");$("stockName").textContent=instrument.name||instrument.fullname||instrument.ts_code||(isEtf?"未知 ETF":"未知股票");$("stockCode").textContent=instrument.ts_code||instrument.code||response.meta?.code||"—";$("stockAvatar").textContent=(instrument.name||"标").slice(0,1);$("stockMeta").textContent=isEtf?[instrument.fund_type,instrument.management,instrument.benchmark&&`基准 ${instrument.benchmark}`].filter(Boolean).join(" · ")||"场内基金":[instrument.industry,instrument.market,instrument.exchange].filter(Boolean).join(" · ")||"A股";$("stockQuality").className=`pill ${quality.status==="ready"?"ready":"attention"}`;$("stockQuality").textContent=quality.status==="ready"?"数据已核验":"数据有提示";
  document.querySelectorAll("[data-stock-overlay]").forEach(button=>button.classList.toggle("active",state.stock.overlays.has(button.dataset.stockOverlay)));
  renderStockWatchlist();document.querySelectorAll("[data-stock-timeframe]").forEach(button=>button.classList.toggle("active",button.dataset.stockTimeframe===state.stock.timeframe));document.querySelectorAll(".daily-only").forEach(button=>button.classList.toggle("disabled",state.stock.timeframe!=="1d"));$("stockDailyNote").classList.toggle("hidden",state.stock.timeframe!=="1d");const loadedFirst=allPoints[0]?.trade_date,loadedLast=allPoints.at(-1)?.trade_date,history=response.meta?.history||{},isDaily=state.stock.timeframe==="1d",truncated=isDaily&&history.truncated;$("stockHistoryRange").textContent=allPoints.length?`已加载 ${loadedFirst} → ${loadedLast} · ${allPoints.length} 根${truncated?" · 达到所选范围，可切换更长历史":" · 当前查询范围（不代表全历史完整）"}`:"没有可展示的历史行情";
  updateStockViewportControls(allPoints);
  state.stock._view={points,allPoints,timeframe};
  renderStockPriceChart(points);
  renderStockSubCharts(points);
  renderStockFactors(timeframe,allPoints);
  const selIdx=points.findIndex(point=>point.trade_date===state.stock.selectedTradeDate);
  if(selIdx>=0)stockSyncCrosshair(selIdx,null,true);
}

async function fetchStockResearch(){
  if(!state.stock.selected)return;const code=state.stock.selected.ts_code||state.stock.selected.code,assetType=state.stock.selected.asset_type||"stock",requestVersion=++state.stock.requestVersion;notice("");$("stockWorkspace").classList.add("stock-loading");try{
    // 分析历史（lookback_days）决定因子计算的数据量；可浏览K线根数（chart_points）独立封顶，
    // 避免「分析历史 1200 日」却把 1200 根×63字段全量下发给前端（前端初始只显示约180根）。
    const lookback=Number($("stockHistory").value)||500,chartPoints=Math.min(lookback,500);
    const endpoint=assetType==="etf"
      ?`/api/v1/research/instruments/etf/${encodeURIComponent(code)}/technicals?lookback_days=${Math.min(lookback,5000)}&chart_points=${chartPoints}`
      :`/api/v1/research/stocks/${encodeURIComponent(code)}/technicals?lookback_days=${lookback}&chart_points=${chartPoints}&include_external=false&include_realtime=false&include_chart_alias=false`;
    const response=await api(endpoint);if(requestVersion!==state.stock.requestVersion||(state.stock.selected?.ts_code||state.stock.selected?.code)!==code)return;state.stock.response=response;state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();}catch(error){if(requestVersion===state.stock.requestVersion)notice(`${assetType==="etf"?"ETF":"个股"}研究加载失败：${error.message}`);}finally{if(requestVersion===state.stock.requestVersion)$("stockWorkspace").classList.remove("stock-loading");}
}

async function stockSearch(selectFirst=false){
  const query=$("stockSearch").value.trim(),suggestions=$("stockSuggestions");if(!query){suggestions.classList.add("hidden");return;}try{const result=await api(`/api/v1/research/instruments/search?${new URLSearchParams({q:query,limit:"12"})}`),items=result.data||[];if(selectFirst&&items.length){selectStock(items[0]);return;}suggestions.innerHTML=items.map(item=>item.asset_type==="etf"?`<button class="stock-suggestion" data-stock-code="${esc(item.ts_code)}" data-asset-type="etf"><span><strong>${esc(item.name)}</strong><small><span class="pill info">ETF</span> ${esc(item.fund_type||item.management||"场内基金")}</small></span><code>${esc(item.ts_code)}</code></button>`:`<button class="stock-suggestion" data-stock-code="${esc(item.ts_code)}" data-asset-type="stock"><span><strong>${esc(item.name||item.fullname)}</strong><small>${esc(item.industry||item.market||"A股")} · ${item.list_status==="L"?"上市":"历史证券"}</small></span><code>${esc(item.ts_code)}</code></button>`).join("")||'<div class="empty-state">没有找到匹配标的</div>';suggestions._items=items;suggestions.classList.remove("hidden");}catch(error){notice(`标的搜索失败：${error.message}`);}
}

async function selectStock(item){
  state.stock.requestVersion++;
  state.stock.selected=item;
  state.stock.response=null;
  resetStockModules();
  state.stock.viewport={timeframe:null,total:0,start:0,count:0};
  state.stock.selectedTradeDate=null;
  $("stockSearch").value=`${item.name||""} ${item.ts_code}`.trim();
  $("stockSuggestions").classList.add("hidden");
  $("stockEmpty").classList.add("hidden");
  $("stockWorkspace").classList.remove("hidden");
  $("stockName").textContent=item.name||item.fullname||item.ts_code;
  $("stockCode").textContent=item.ts_code;
  $("stockAvatar").textContent=(item.name||item.fullname||"标").slice(0,1);
  const isEtf=item.asset_type==="etf";
  $("stockMeta").textContent=isEtf?[item.fund_type,item.management,item.benchmark&&`基准 ${item.benchmark}`].filter(Boolean).join(" · ")||"场内基金":[item.industry,item.market,item.exchange].filter(Boolean).join(" · ")||"A股";
  $("stockQuality").className="pill pending";
  $("stockQuality").textContent="加载中";
  $("stockWatchToggle").classList.toggle("hidden",isEtf);
  state.stock.overlays=new Set(["ma_20","ma_60","cost_20","cost_60","niumen_line","niumen_confirmation_line"]);
  $("stockClose").textContent="加载中";
  $("stockChange").textContent="—";
  $("stockChange").className="";
  $("stockDate").textContent="正在读取长历史行情";
  $("stockPriceChart").replaceChildren();
  $("stockSubChartArea").innerHTML="";
  state.stock.priceScale=null;state.stock.hoverIndex=null;state.stock._view=null;
  [
    "stockTrend","stockTrendDetail","stockMacd","stockMacdDetail",
    "stockRsi","stockKdj","stockCost","stockCostDistance","stockNiumen","stockNiumenDetail","stockXiongmen","stockXiongmenDetail",
    "stockVolumeState","stockVolumeDetail","stockVolatility",
    "stockVolatilityDetail","stockStrength","stockStrengthDetail","stockMoneyFlow",
    "stockMoneyFlowDetail"
  ].forEach(id=>$(id).textContent="—");
  $("stockZoomStatus").textContent="正在加载…";
  $("stockPan").min="0";
  $("stockPan").max="0";
  $("stockPan").value="0";
  $("stockPan").disabled=true;
  ["stockPanPrev","stockPanNext","stockZoomIn","stockZoomOut","stockZoomReset"].forEach(id=>$(id).disabled=true);
  $("stockTooltip").classList.add("hidden");
  renderStockWatchlist();
  await fetchStockResearch();
}
async function loadStockResearch(){await loadStockWatchlist();if(state.stock.response)renderStockResearch();else if(state.stock.selected)fetchStockResearch();}

async function refresh(options={}){
  const {force=false, background=false}={...options};
  const active=state.activeView||"overview";
  // 后台轮询在标签页不可见时没有意义，还会挤占前台请求；回到页面时补一次。
  if(background&&document.hidden)return;
  if(!force)notice("");
  try{
    if(active==="overview"){await loadOverview(force);return;}
    // 后台轮询只刷新轻量视图；研究页图表已渲染，不必每 30 秒重画。
    if(["stock","market","etf","sector","macro","factors","derivations"].includes(active)){
      if(background)return;
      if(active==="stock")return await fetchStockResearch();
      if(active==="market")return await selectMarketIndex(state.research.market.selected||MARKET_INDEXES[0]);
      if(active==="etf")return await (state.research.etf.selected?selectEtf(state.research.etf.selected):loadEtfResearch());
      if(active==="sector")return await (state.research.sector.selected?selectSector(state.research.sector.selected):loadSectorResearch());
      if(active==="macro")return await loadMacroResearch();
      if(active==="factors")return await loadFactors();
      return await loadDerivations();
    }
    await ({today:loadToday,intraday:loadIntraday,stock:loadStockResearch,tasks:loadTasks,executions:loadExecutions,calendar:loadCalendar,coverage:loadCoverage,initialization:loadInitialization,usage:loadProviderUsage,sources:loadSources,services:loadServices,investment:loadInvestment}[active]||(()=>{}))();
  }catch(e){if((state.activeView||"overview")===active){
    if(active==="overview"){$("healthKicker").textContent="刷新失败";$("healthSummary").textContent="未能核实当前状态。保留的上次结果不能作为当前交付依据。";}
    notice(`加载失败：${e.message}`);}}
}

// ===== 盘中观察：采集 → 指标 → 信号 → 结论 =====
const intradayStateLabels={strong_uptrend:"强上涨",uptrend:"上涨",range:"震荡",downtrend:"下跌",strong_downtrend:"强下跌",selloff:"快速下跌",reversal_watch:"反转观察",reversal_confirmed:"反转确认",broad_risk_on:"普遍转强",style_rotation:"结构轮动",relative_strength:"相对强势",relative_weakness:"相对弱势",leading_reversal:"领先反转",risk_alert:"风险提示",none:"无额外事件"};
const intradayStatusLabels={running:"采集中",success:"完整",attention:"部分数据",failed:"失败"};
function intradayPercent(value){return value==null?"—":`${Number(value)>=0?"+":""}${Number(value).toFixed(2)}%`;}
function renderIntraday(){
  const data=state.intraday.response;if(!data)return;
  const latest=data.latest||[],market=latest.find(x=>x.scope_type==="market"),run=data.last_run;
  if(market){
    $("intradayAsOf").textContent=new Date(market.as_of).toLocaleString("zh-CN",{hour12:false});
    const event=market.metrics?.event_state;$("intradayState").textContent=`${intradayStateLabels[market.state]||market.state}${event&&event!=="none"?` · ${intradayStateLabels[event]||event}`:""}`;
    $("intradayScore").textContent=Number(market.score).toFixed(0);
    $("intradayConclusion").textContent=market.conclusion;
    const q=market.data_quality||{};$("intradayQuality").textContent=`可信度 ${market.confidence} · 数据覆盖 ${(Number(q.coverage||0)*100).toFixed(1)}% · 规则 ${market.rule_version}`;
    $("intradayEvidence").innerHTML=(market.evidence||[]).map(item=>`<span>${esc(item)}</span>`).join("");
    $("intradayMarket").classList.remove("loading");
  }else{$("intradayAsOf").textContent="等待首次采集";$("intradayState").textContent="等待数据";$("intradayScore").textContent="—";$("intradayConclusion").textContent="尚未生成盘中结论";$("intradayQuality").textContent="自动采集进程将在A股交易时段每15分钟运行，受共享额度约束。";$("intradayEvidence").innerHTML="";}
  $("intradayRunStatus").textContent=run?(intradayStatusLabels[run.status]||run.status):"尚未运行";
  $("intradayRunTime").textContent=run?new Date(run.scheduled_for).toLocaleString("zh-CN",{hour12:false}):"—";
  $("intradayOuterCalls").textContent=run?.outer_calls??"—";$("intradaySubrequests").textContent=run?.subrequests??"—";$("intradayRows").textContent=run?`${fmt(run.fetched_rows)} / ${fmt(run.stored_rows)}`:"—";
  const etfs=latest.filter(x=>["etf","index"].includes(x.scope_type));
  $("intradayEtfs").innerHTML=etfs.map(item=>`<article class="intraday-signal-card"><header><h3>${esc(item.scope_name)}</h3><span class="pill info">${esc(intradayStateLabels[item.state]||item.state)}</span></header><p>${esc(item.conclusion)}</p><footer><span>涨跌 ${intradayPercent(item.metrics?.pct_chg)}</span><span>相对 ${intradayPercent(item.metrics?.relative_strength_pct)}</span><b>${Number(item.score).toFixed(0)} 分</b></footer></article>`).join("")||'<p class="empty-row">等待首次采集ETF信号。</p>';
  const stocks=new Map(latest.filter(x=>x.scope_type==="stock").map(x=>[x.scope_code,x]));
  const watch=data.watchlist||[];
  $("intradayWatchlist").innerHTML=`<table><thead><tr><th>股票</th><th>观察</th><th>最新信号</th><th>相对市场</th><th>结论</th></tr></thead><tbody>${watch.map(item=>{const signal=stocks.get(item.ts_code);return `<tr><td><strong>${esc(item.name)}</strong><small>${esc(item.ts_code)}</small></td><td><button class="observation-toggle ${item.intraday_observation_enabled?"active":""}" data-intraday-toggle="${esc(item.ts_code)}" data-enabled="${item.intraday_observation_enabled?"1":"0"}>${item.intraday_observation_enabled?"已开启":"开启观察"}</button></td><td>${signal?`<span class="pill info">${esc(intradayStateLabels[signal.state]||signal.state)}</span> · ${Number(signal.score).toFixed(0)}分`:item.intraday_observation_enabled?"等待下一轮":"—"}</td><td>${signal?intradayPercent(signal.metrics?.relative_strength_pct):"—"}</td><td>${esc(signal?.conclusion||"—")}</td></tr>`;}).join("")||'<tr><td colspan="5" class="empty-row">请先在“个股研究”中添加自选股。</td></tr>'}</tbody></table>`;
  const stockHistory=data.validation_summary||[];
  $("intradayStockHistory").innerHTML=`<table><thead><tr><th>股票</th><th>覆盖</th><th>强涨 / 涨</th><th>震荡</th><th>跌 / 强跌</th><th>领先反转</th><th>相对强 / 弱</th><th>质量</th></tr></thead><tbody>${stockHistory.map(item=>`<tr><td><strong>${esc(item.scope_name)}</strong><small>${esc(item.scope_code)}</small></td><td>${fmt(item.days)}日 · ${fmt(item.checkpoints)}点</td><td>${fmt(item.strong_uptrend)} / ${fmt(item.uptrend)}</td><td>${fmt(item.range_count)}</td><td>${fmt(item.downtrend)} / ${fmt(item.strong_downtrend)}</td><td>${fmt(item.reversals)}</td><td>${fmt(item.relative_strength)} / ${fmt(item.relative_weakness)}</td><td>${Number(item.incomplete||0)===0?"完整":"缺失 "+fmt(item.incomplete)}</td></tr>`).join("")||'<tr><td colspan="8" class="empty-row">暂无个股历史验证。</td></tr>'}</tbody></table>`;
  const history=(data.market_history||[]).slice().reverse();
  $("intradayHistory").innerHTML=history.map(item=>{const d=new Date(item.as_of);return `<div class="intraday-history-item" title="${esc(item.conclusion)}"><i style="height:${Math.max(6,Number(item.score||0)*.7)}px"></i><small>${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}<br>${d.toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit",hour12:false})}</small></div>`;}).join("")||'<p class="empty-row">暂无历史轮次。</p>';
}
async function loadIntraday(){try{state.intraday.response=await api("/api/v1/intraday/overview");renderIntraday();}catch(error){notice(`盘中观察加载失败：${error.message}`);}}
async function toggleIntradayObservation(symbol,enabled){
  try{await api(`/api/v1/intraday/watchlist/${encodeURIComponent(symbol)}/observation`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled,profile:"balanced"})});await loadIntraday();}
  catch(error){notice(`自选观察设置失败：${error.message}`);}
}
async function runIntradayNow(){
  if(state.intraday.busy)return;state.intraday.busy=true;$("intradayRun").disabled=true;$("intradayRun").textContent="采集中…";
  try{await api("/api/v1/intraday/run",{method:"POST"});await loadIntraday();}
  catch(error){notice(`盘中采集失败：${error.message}`);}
  finally{state.intraday.busy=false;$("intradayRun").disabled=false;$("intradayRun").textContent="立即采集一轮";}
}

document.querySelector("nav").onclick=e=>{const b=e.target.closest("[data-view]");if(b)activate(b.dataset.view)};
// ===== 研究分组：大盘 / ETF / 板块（共用通用图表渲染器） =====
const MARKET_INDEXES=[{ts_code:"000001.SH",name:"上证指数"},{ts_code:"399001.SZ",name:"深证成指"},{ts_code:"399006.SZ",name:"创业板指"},{ts_code:"399673.SZ",name:"创业板50"},{ts_code:"399005.SZ",name:"中小100"},{ts_code:"000300.SH",name:"沪深300"},{ts_code:"000905.SH",name:"中证500"},{ts_code:"000852.SH",name:"中证1000"},{ts_code:"000016.SH",name:"上证50"},{ts_code:"000688.SH",name:"科创50"}];
const researchMA=(points,window)=>{const closes=points.map(p=>Number(p.close));return points.map((_,i)=>i+1>=window?closes.slice(i+1-window,i+1).reduce((a,b)=>a+b,0)/window:null);};
const RESEARCH_MA_DEFS=[[5,"#348fcb"],[20,"#d19b3f"],[60,"#8a63c9"]];
const RESEARCH_CHART_MARGIN={left:12,right:72,top:15,bottom:28};
function renderResearchCandles(svgId,points,opts={}){
  const svg=$(svgId),width=1200,height=430,margin=RESEARCH_CHART_MARGIN,pw=width-margin.left-margin.right,ph=height-margin.top-margin.bottom;
  if(!points||!points.length){svg.innerHTML='<text x="600" y="215" text-anchor="middle" class="axis-label">没有可展示的行情</text>';return null;}
  const series=opts.maSeries||RESEARCH_MA_DEFS.map(([w])=>researchMA(points,w));
  // 均线不拉伸刻度；主动勾选的参考线和减仓标记纳入刻度。
  const overlays=opts.overlays||[];
  const values=points.flatMap(p=>[p.high,p.low,...overlays.map(key=>p[key]),...(opts.showXiongmen?[p.xiongmen_marker_price]:[])]).filter(v=>v!=null).map(Number).filter(Number.isFinite);
  const rawMin=Math.min(...values),rawMax=Math.max(...values),pad=Math.max((rawMax-rawMin)*.06,rawMax*.005),min=rawMin-pad,max=rawMax+pad;
  const x=i=>margin.left+(i+.5)*pw/points.length,y=v=>margin.top+(max-v)/(max-min)*ph,step=pw/points.length,bw=Math.max(1.5,Math.min(7,step*.64));
  let m="";
  for(let t=0;t<=5;t++){const v=max-(max-min)*t/5,py=margin.top+ph*t/5;m+=`<line class="grid-line" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/><text class="axis-label" x="${width-margin.right+8}" y="${py+3}">${stockNumber(v,2)}</text>`;}
  const ticks=Math.min(6,points.length);for(let t=0;t<ticks;t++){const i=Math.round(t*(points.length-1)/Math.max(ticks-1,1));m+=`<text class="axis-label" text-anchor="middle" x="${x(i)}" y="${height-7}">${esc(String(points[i].trade_date).slice(5,10))}</text>`;}
  points.forEach((p,i)=>{const o=Number(p.open),c=Number(p.close),up=c>=o,top=y(Math.max(o,c)),b=y(Math.min(o,c));m+=`<line class="${up?"candle-up":"candle-down"}" x1="${x(i)}" y1="${y(Number(p.high))}" x2="${x(i)}" y2="${y(Number(p.low))}"/><rect class="${up?"candle-up":"candle-down"}" x="${x(i)-bw/2}" y="${top}" width="${bw}" height="${Math.max(1,b-top)}"/>`;});
  series.forEach((vals,idx)=>{const color=RESEARCH_MA_DEFS[idx][1];let path="",draw=false;vals.forEach((v,i)=>{const gap=i>0?(Date.parse(points[i].trade_date)-Date.parse(points[i-1].trade_date))/86400000:0;if(gap>10)draw=false;if(!Number.isFinite(v)){draw=false;return;}path+=`${draw?"L":"M"}${x(i).toFixed(2)},${y(v).toFixed(2)} `;draw=true;});m+=`<path class="factor-line" d="${path.trim()}" stroke="${color}"/>`;});
  overlays.forEach(key=>{const def=stockLineDefinitions[key];m+=`<path class="factor-line" d="${stockPath(points,key,x,y)}" stroke="${def.color}"${def.dash?' stroke-dasharray="6 4"':""}/>`;});
  if(opts.showXiongmen)m+=xiongmenMarkers(points,x,y);
  m+=`<g id="${svgId}-cross"></g><rect class="hit-area" x="${margin.left}" y="${margin.top}" width="${pw}" height="${ph}"/>`;
  svg.innerHTML=m;
  return {margin,width,pw,ph,x,y,overlays,showXiongmen:opts.showXiongmen};
}
function renderResearchVolume(svgId,points){
  const svg=$(svgId);if(!svg)return;
  const width=1200,height=96,margin={left:12,right:72,top:6,bottom:16},pw=width-margin.left-margin.right,ph=height-margin.top-margin.bottom;
  const values=points.map(p=>Number(p.volume)).filter(Number.isFinite);
  if(!values.length||!values.some(v=>v>0)){svg.innerHTML=`<text x="${width/2}" y="${height/2}" text-anchor="middle" class="axis-label">无成交量数据</text>`;return;}
  const max=Math.max(...values,1),step=pw/Math.max(points.length,1),bw=Math.max(1,Math.min(7,step*.64));
  let m="";
  for(let t=0;t<=1;t++){const v=max*(1-t),py=margin.top+ph*t;m+=`<line class="grid-line" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/><text class="axis-label" x="${width-margin.right+8}" y="${py+3}">${stockVolumeText(v).replace(/ [万亿]?手?$/,"")}</text>`;}
  points.forEach((p,i)=>{const v=Number(p.volume);if(!Number.isFinite(v))return;const h=v/max*ph,x=margin.left+(i+.5)*step;m+=`<rect class="${Number(p.close)>=Number(p.open)?"bar-up":"bar-down"}" x="${x-bw/2}" y="${height-margin.bottom-h}" width="${bw}" height="${Math.max(1,h)}" opacity=".72"/>`;});
  svg.innerHTML=m;
}
function researchWindowNormalize(view,points){
  const total=points.length;
  let w=view.window;
  if(!w){
    // 默认展示最近一年（稀疏标的如债券 ETF 可能只跳空几十根，按根数取窗会把远古点拉进来压扁蜡烛）
    const lastMs=Date.parse(points[total-1]?.trade_date||"")||Date.now(),cutoff=lastMs-365*86400000;
    let start=total-1;
    while(start>0&&(Date.parse(points[start-1].trade_date)||0)>=cutoff)start--;
    if(total-start>250)start=total-250;
    if(total-start<30)start=Math.max(0,total-30);
    w=view.window={start,count:total-start};
  }
  w.count=Math.max(30,Math.min(w.count||180,total));
  w.start=Math.max(0,Math.min(w.start,total-w.count));
  return w;
}
function renderResearchChart(prefix,points){
  const view=state.research[prefix],total=points.length;
  if(!total)return;
  const w=researchWindowNormalize(view,points),visible=points.slice(w.start,w.start+w.count);
  // 稀疏序列（中位交易日间隔 > 7 天）不画均线：跨跳空的均线没有参考意义
  const gaps=[];
  for(let i=1;i<visible.length;i++){const gap=(Date.parse(visible[i].trade_date)-Date.parse(visible[i-1].trade_date))/86400000;if(Number.isFinite(gap))gaps.push(gap);}
  gaps.sort((a,b)=>a-b);
  const dense=!gaps.length||gaps[Math.floor(gaps.length/2)]<=7;
  const maSeries=dense?RESEARCH_MA_DEFS.map(([win])=>researchMA(points,win).slice(w.start,w.start+w.count)):[[],[],[]];
  view.overlays??=new Set();
  const showXiongmen=view.overlays.has("xiongmen"),overlays=[...(showXiongmen?XIONGMEN_MAIN_LINES:[]),...(view.overlays.has("xiongmen_bear_entry_line")?["xiongmen_bear_entry_line"]:[])];
  const meta=renderResearchCandles(`${prefix}PriceChart`,visible,{maSeries,overlays,showXiongmen});
  renderResearchVolume(`${prefix}VolumeChart`,visible);
  view._chart={meta,visible};
  if(meta)attachResearchChartEvents(prefix);
  const status=$(prefix+"ZoomStatus");
  if(status)status.textContent=`共 ${total} 根 · 显示 ${visible.length} 根 · Ctrl / ⌘ + 滚轮缩放 / 按钮平移`;
  ["ZoomIn","ZoomOut","ZoomReset","PanPrev","PanNext"].forEach(suffix=>{const el=$(prefix+suffix);if(el)el.disabled=total<40;});
}
function researchZoom(prefix,direction,anchorRatio){
  const view=state.research[prefix],points=view.response?.data?.timeframes?.["1d"]?.chart?.points||[];
  if(points.length<40)return;
  const w=view.window,old=w.count,next=Math.max(30,Math.min(points.length,Math.round(old*(direction>0?.7:1.45))));
  if(next===old)return;
  if(anchorRatio==null)w.start+=Math.round(old-next);
  else w.start=Math.round(w.start+anchorRatio*old-anchorRatio*next);
  w.count=next;renderResearchChart(prefix,points);
}
function researchPan(prefix,direction){
  const view=state.research[prefix],points=view.response?.data?.timeframes?.["1d"]?.chart?.points||[];
  if(points.length<40)return;
  const w=view.window,shift=Math.max(10,Math.round(w.count*.25))*direction;
  w.start+=shift;renderResearchChart(prefix,points);
}
function resetResearchWindow(prefix){
  const view=state.research[prefix];view.window=null;
  const points=view.response?.data?.timeframes?.["1d"]?.chart?.points||[];
  if(points.length)renderResearchChart(prefix,points);
}
function attachResearchChartEvents(prefix){
  const view=state.research[prefix],{meta,visible}=view._chart||{};if(!meta)return;
  const svg=$(prefix+"PriceChart"),hit=svg.querySelector(".hit-area"),tip=$(prefix+"Tooltip"),cross=svg.querySelector(`#${prefix}PriceChart-cross`);
  if(!hit||!tip||!cross)return;
  const {margin,width,pw,ph,x,y}=meta;
  const vol=$(prefix+'VolumeChart');
  const indexAt=e=>{const rect=(e.currentTarget.ownerSVGElement||e.currentTarget).getBoundingClientRect(),rel=(e.clientX-rect.left)/rect.width*width;return Math.max(0,Math.min(visible.length-1,Math.floor((rel-margin.left)/pw*visible.length)));};
  hit.onpointermove=e=>{
    const i=indexAt(e),p=visible[i],px=x(i),py=y(Number(p.close)),rect=svg.getBoundingClientRect();
    cross.innerHTML=`<line class="crosshair" x1="${px}" y1="${margin.top}" x2="${px}" y2="${margin.top+ph}"/><line class="crosshair" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/>`;
    if(vol){let marker=vol.querySelector(".sync-marker");if(!marker){marker=document.createElementNS(svg.namespaceURI,"line");marker.setAttribute("class","crosshair sync-marker");vol.append(marker);}for(const [k,v] of Object.entries({x1:px,x2:px,y1:5,y2:80}))marker.setAttribute(k,v);}
    const rows=[["开",p.open],["高",p.high],["低",p.low],["收",p.close],["量",p.volume!=null?stockVolumeText(p.volume):null]].map(([k,v])=>v==null?"":`<span>${k} ${esc(String(v))}</span>`).join("");
    const pctChg=p.pct_chg!=null?`<span class="${Number(p.pct_chg)>=0?"up":"down"}">涨跌幅 ${stockPercent(p.pct_chg)}</span>`:"";
    tip.style.left=`${Math.min(rect.width-230,Math.max(6,e.clientX-rect.left+14))}px`;
    tip.style.top=`${Math.min(rect.height-120,Math.max(6,e.clientY-rect.top-60))}px`;
    tip.innerHTML=`<strong>${esc(String(p.trade_date))}</strong><div class="stock-tooltip-grid">${rows}${pctChg}${meta.overlays.map(key=>p[key]==null?"":`<span style="color:${stockLineDefinitions[key].color}">${esc(stockLineDefinitions[key].label)} ${stockNumber(p[key])}</span>`).join("")}${meta.showXiongmen?xiongmenTooltip(p):""}</div>`;
    tip.classList.remove("hidden");
  };
  hit.onpointerleave=()=>{vol?.querySelector(".sync-marker")?.remove();cross.innerHTML="";tip.classList.add("hidden");};
  if(vol){vol.onpointermove=hit.onpointermove;vol.onpointerleave=hit.onpointerleave;}
}
const researchFactorCard=(label,value,detail)=>`<article><span>${esc(label)}</span><strong>${value}</strong><small>${detail||""}</small></article>`;
const researchPct=value=>value==null||Number.isNaN(Number(value))?"—":`${Number(value)>=0?"+":""}${Number(value).toFixed(2)}%`;
function researchIndicatorCards(timeframe){
  const trend=timeframe.trend||{},momentum=timeframe.momentum||{},volatility=timeframe.volatility||{},strength=timeframe.trend_strength||{},volume=timeframe.volume_price||{};
  const ma=trend.moving_averages||{},regimeLabel={bullish:"多头排列",bearish:"空头排列",mixed:"多空交织"}[trend.regime]||"—";
  const points=timeframe.chart?.points||[],windowHigh=window=>{const rows=points.slice(-window);const highs=rows.map(p=>Number(p.high)).filter(Number.isFinite),lows=rows.map(p=>Number(p.low)).filter(Number.isFinite);return {high:highs.length?Math.max(...highs):null,low:lows.length?Math.min(...lows):null}};
  const recent=windowHigh(20),year=windowHigh(250),xiongmen=xiongmenSummary(trend.systems?.xiongmen_rebound);
  return [
    researchFactorCard("趋势状态",regimeLabel,`MA20 ${stockNumber(ma["20"])} · MA60 ${stockNumber(ma["60"])} · MA250 ${stockNumber(ma["250"])}`),
    researchFactorCard("MACD",`${stockNumber(trend.macd,3)}`,`DIF ${stockNumber(trend.macd,3)} · DEA ${stockNumber(trend.macd_signal,3)}`),
    researchFactorCard("RSI / KDJ",`RSI ${stockNumber(momentum.rsi_14,1)}`,`K ${stockNumber(momentum.kdj?.k,1)} · D ${stockNumber(momentum.kdj?.d,1)} · J ${stockNumber(momentum.kdj?.j,1)}`),
    researchFactorCard("ADX 趋势强度",`${stockNumber(strength.adx_14,1)}`,`+DI ${stockNumber(strength.plus_di_14,1)} · −DI ${stockNumber(strength.minus_di_14,1)}`),
    researchFactorCard("波动率",`ATR ${stockNumber(volatility.atr_14)}`,`20期年化 ${researchPct(volatility.annualized_volatility_20_period_pct)} · NATR ${researchPct(volatility.natr_14_pct)}`),
    researchFactorCard("量能",`5/20 比 ${stockNumber(volume.volume_5_to_20_ratio,2)}`,`5日均量 ${stockVolumeText(volume.volume_5_average)} · 20日均量 ${stockVolumeText(volume.volume_20_average)}`),
    researchFactorCard("动量",`ROC12 ${researchPct(momentum.roc_12_pct)}`,`20日 ${researchPct(momentum.return_20_period_pct)} · 60日 ${researchPct(momentum.return_60_period_pct)}`),
    researchFactorCard("熊门反弹体系",esc(xiongmen.label),esc(xiongmen.detail)),
    researchFactorCard("区间极值",`高 ${stockNumber(recent.high)} / 20日`,`低 ${stockNumber(recent.low)} / 20日 · 250日高 ${stockNumber(year.high)}`),
  ].join("");
}
function renderResearchHeadline(prefix,timeframe,instrument){
  const points=timeframe?.chart?.points||[],latest=points.at(-1),previous=points.at(-2)||latest,change=Number(previous?.close)?(Number(latest.close)/Number(previous.close)-1)*100:null;
  $(`${prefix}Name`).textContent=instrument.name||instrument.code||"—";
  $(`${prefix}Code`).textContent=instrument.ts_code||instrument.code||"—";
  $(`${prefix}Close`).textContent=stockNumber(latest?.close);
  const changeEl=$(`${prefix}Change`);changeEl.textContent=researchPct(change);changeEl.className=change>0?"up":change<0?"down":"";
  $(`${prefix}Date`).textContent=latest?.trade_date||"—";
}
function renderValuationGrid(target,metrics){
  const labels={pe:"市盈率 PE",pe_ttm:"市盈率 TTM",pb:"市净率 PB",turnover_rate:"换手率 %"};
  $(target).innerHTML=Object.entries(metrics||{}).filter(([,v])=>v).map(([field,v])=>`<article><span>${labels[field]||field}</span><strong>${stockNumber(v.latest)}</strong><small>分位 ${stockNumber(v.percentile_pct,1)}% · 区间 ${stockNumber(v.history_min)} – ${stockNumber(v.history_max)}</small></article>`).join("")||'<p class="empty-row">暂无估值数据</p>';
}
// ---- 大盘研究 ----
async function loadResearchPanels(view, requests, render, title){
  notice("");
  const prefix=title==="大盘研究"?"market":title==="ETF 研究"?"etf":title==="板块研究"?"sector":null;
  if(prefix){
    ["PriceChart","VolumeChart","MacdChart","IndicatorGrid","ValuationGrid","NavGrid","MemberChips"].forEach(suffix=>$(prefix+suffix)?.replaceChildren());
  }
  const version=view.requestVersion=(view.requestVersion||0)+1;
  const failures=[];
  await Promise.allSettled(Object.entries(requests).map(async ([key,path])=>{
    try{
      const result=await api(path);
      if(version!==view.requestVersion)return;
      view[key]=result;render();
    }catch(error){
      if(version!==view.requestVersion)return;
      failures.push(`${key==="response"?"K 线":key==="valuation"?"估值":key==="nav"?"净值与份额":"成分股"}：${error.message}`);
      notice(`${title}部分内容未加载（已成功内容保留）。${failures.join("；")}`);
    }
  }));
}
async function selectMarketIndex(item){
  const view=state.research.market;view.selected=item;view.response=null;view.valuation=null;view.window=null;
  $("marketWorkspace").classList.remove("hidden");$("marketLoading").classList.add("hidden");
  $("marketName").textContent=item.name;$("marketCode").textContent=item.ts_code;$("marketClose").textContent="加载中…";
  $("marketIndexChips").querySelectorAll("button").forEach(b=>b.classList.toggle("active",b.dataset.marketIndex===item.ts_code));
  try{
    await loadResearchPanels(view,{
      response:`/api/v1/research/instruments/index/${encodeURIComponent(item.ts_code)}/technicals?lookback_days=1200&chart_points=180`,
      valuation:`/api/v1/research/indices/${encodeURIComponent(item.ts_code)}/valuation?lookback_days=750`,
    },renderMarketResearch,"大盘研究");
  }catch(error){notice(`大盘研究加载失败：${error.message}`);}
}
function renderMarketResearch(){
  const view=state.research.market;if(!view.response)return;
  const timeframe=view.response.data.timeframes["1d"];
  renderResearchHeadline("market",timeframe,view.response.data.instrument.identity||view.selected);
  renderResearchChart("market",timeframe.chart.points);
  $("marketIndicatorGrid").innerHTML=researchIndicatorCards(timeframe);
  $("marketTrendSummary").textContent=`观测 ${timeframe.observations} 根 · ${timeframe.chart.points.length} 根展示`;
  renderValuationGrid("marketValuationGrid",view.valuation?.data?.metrics);
}
function switchMarketModule(name){
  state.research.market.tab=name;
  document.querySelectorAll("[data-market-module]").forEach(b=>b.classList.toggle("active",b.dataset.marketModule===name));
  document.querySelectorAll("[data-market-module-panel]").forEach(p=>p.classList.toggle("hidden",p.dataset.marketModulePanel!==name));
  if(name==="funds")loadMarketFunds();
}
async function loadMarketFunds(){
  const view=state.research.market;
  try{
    if(!view.funds)view.funds=await api("/api/v1/research/market/funds?days=120");
    const funds=view.funds.data;
    const metric=$("marketMarginMetric")?.value||"margin_balance",balance=funds[metric];
    renderLineCard("marketMarginChart","marketMarginNote",balance.series,{color:"#348fcb",digits:2});
    $("marketMarginNote").textContent=`${balance.label} · 数据截至 ${balance.series.at(-1)?.[0]||"—"} · ${$("marketMarginNote").textContent}`;
    const gaps=view.funds.meta?.margin_quality?.incomplete_dates||[];
    if(gaps.length)$("marketMarginNote").textContent+=` · ${gaps.length} 个日期余额未完整，未计入曲线`;
    renderLineCard("marketNorthChart","marketNorthNote",funds.north_money.series,{color:"#1d9e75",zero:true,digits:0});
    renderLineCard("marketFlowChart","marketFlowNote",funds.market_flow.series,{color:"#d85a30",zero:true,digits:0});
  }catch(error){notice(`资金面加载失败：${error.message}`);}
}
$("marketMarginMetric")?.addEventListener("change",()=>loadMarketFunds());
function renderResearchLinesInto(svg,rows,opts){
  const container=svg.closest("section");svg.setAttribute("viewBox","0 0 640 190");
  const proxy={innerHTML:"",setAttribute(){},closest:()=>container};
  // 简单封装：直接在原 svg 上渲染
  const width=640,height=190,margin={left:8,right:64,top:12,bottom:20},pw=width-margin.left-margin.right,ph=height-margin.top-margin.bottom;
  const values=rows.map(r=>Number(r[1])).filter(Number.isFinite);
  if(!values.length){svg.innerHTML='<text x="300" y="90" text-anchor="middle" class="axis-label">暂无数据</text>';return;}
  const zero=opts.zero,rawMin=Math.min(...values,zero?0:Infinity),rawMax=Math.max(...values,zero?0:-Infinity),pad=(rawMax-rawMin)*.1||Math.abs(rawMax)*.05||1,min=rawMin-pad,max=rawMax+pad;
  const x=i=>margin.left+(i+.5)*pw/rows.length,y=v=>margin.top+(max-v)/(max-min)*ph;
  let m="";
  for(let t=0;t<=3;t++){const v=max-(max-min)*t/3,py=margin.top+ph*t/3;m+=`<line class="grid-line" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/><text class="axis-label" x="${width-margin.right+6}" y="${py+3}">${stockNumber(v,opts.digits??2)}</text>`;}
  if(opts.baseline!=null&&opts.baseline>=min&&opts.baseline<=max)m+=`<line class="chart-reference" x1="${margin.left}" x2="${width-margin.right}" y1="${y(opts.baseline)}" y2="${y(opts.baseline)}"/>`;
  if(zero&&min<0&&max>0)m+=`<line class="grid-line" x1="${margin.left}" y1="${y(0)}" x2="${width-margin.right}" y2="${y(0)}" stroke-dasharray="4 3"/>`;
  let path="",draw=false;rows.forEach((r,i)=>{const v=Number(r[1]);if(!Number.isFinite(v)){draw=false;return;}path+=`${draw?"L":"M"}${x(i).toFixed(2)},${y(v).toFixed(2)} `;draw=true;});
  m+=`<path class="factor-line" d="${path.trim()}" stroke="${opts.color||"#348fcb"}"/>`;
  if(opts.label&&rows.length){const last=rows[rows.length-1],lv=Number(last[1]);if(Number.isFinite(lv)){const lx=x(rows.length-1),ly=y(lv),color=opts.color||"#348fcb";m+=`<circle cx="${lx}" cy="${ly}" r="2.6" fill="${color}"/><text class="axis-label" x="${Math.min(lx-6,width-6)}" y="${Math.max(ly-6,10)}" text-anchor="end" fill="${color}" font-weight="600">${stockNumber(lv,opts.digits??2)}</text>`;}}
  const ticks=Math.min(3,rows.length);for(let t=0;t<ticks;t++){const i=Math.round(t*(rows.length-1)/Math.max(ticks-1,1));m+=`<text class="axis-label" text-anchor="middle" x="${x(i)}" y="${height-5}">${esc(String(rows[i][0]).slice(0,10))}</text>`;}
  svg.innerHTML=m;
}
// 时间序列归一为升序（部分后端序列最新在前），并计算「最新值 / 5期变动 / 20期变动」摘要。
function renderLineCard(svgId,noteId,rows,opts={}){
  const norm=[...rows].sort((a,b)=>String(a[0]).localeCompare(String(b[0])));
  const note=noteId?$(noteId):null;
  if(note){
    const vals=norm.map(r=>Number(r[1])).filter(Number.isFinite);
    const fmtDiff=v=>v==null||!Number.isFinite(v)?"—":`${v>=0?"+":""}${stockNumber(v,opts.digits??2)}`;
    if(vals.length>=21)note.textContent=`最新 ${stockNumber(vals.at(-1),opts.digits??2)} · 5期 ${fmtDiff(vals.at(-1)-vals.at(-6))} · 20期 ${fmtDiff(vals.at(-1)-vals.at(-21))}`;
    else if(vals.length>=6)note.textContent=`最新 ${stockNumber(vals.at(-1),opts.digits??2)} · 5期 ${fmtDiff(vals.at(-1)-vals.at(-6))}`;
    else note.textContent=vals.length?`最新 ${stockNumber(vals.at(-1),opts.digits??2)}`:"暂无数据";
  }
  renderResearchLinesInto($(svgId),norm,{...opts,label:true});
}
async function loadMarketResearch(){
  $("marketIndexChips").innerHTML=MARKET_INDEXES.map(item=>`<button data-market-index="${item.ts_code}">${esc(item.name)}</button>`).join("");
  if(!state.research.market.response)await selectMarketIndex(state.research.market.selected||MARKET_INDEXES[0]);
}
// ---- ETF 研究：宽基国家队资金流 ----
const etfYi = v => v==null || !Number.isFinite(Number(v)) ? null : Number(v)/10000;
const etfSigned = (v,d=2) => v==null||!Number.isFinite(Number(v)) ? "—" : `${Number(v)>=0?"+":""}${stockNumber(v,d)}`;
const etfAxisNum = v => v>=1 ? `${v.toFixed(v>=10?0:1)}亿` : `${(v*10000).toFixed(0)}万`;

function etfRenderPicker(){
  const flow=state.research.etf.flow;
  const all=flow.series;
  const groups={};
  all.forEach(s=>{ (groups[s.index_name]=groups[s.index_name]||[]).push(s); });
  const sel=flow.selectedCodes;
  let groupHtml=`<button class="etf-flow-chip etf-flow-chip-all${sel===null?" active":""}" data-etf-flow-group="__all__" type="button">全部宽基（${all.length}）</button>`;
  Object.entries(groups).forEach(([idx,members])=>{
    const codes=members.map(m=>m.ts_code);
    const active=sel!==null&&sel.length>0&&codes.every(c=>sel.includes(c));
    groupHtml+=`<button class="etf-flow-chip${active?" active":""}" data-etf-flow-group="${esc(idx)}" type="button">${esc(idx)}（${members.length}）</button>`;
  });
  $("etfFlowGroups").innerHTML=groupHtml;
  let memberHtml="";
  Object.entries(groups).forEach(([idx,members])=>{
    memberHtml+=`<div class="etf-flow-member-group"><span class="etf-flow-member-group-label">${esc(idx)}</span><span class="etf-flow-member-chips">`;
    members.forEach(m=>{
      const active=sel!==null&&sel.includes(m.ts_code);
      memberHtml+=`<button class="etf-flow-chip etf-flow-chip-member${active?" active":""}" data-etf-flow-member="${esc(m.ts_code)}" type="button" title="${esc(m.ts_code)}">${esc(m.name)}</button>`;
    });
    memberHtml+=`</span></div>`;
  });
  $("etfFlowMembers").innerHTML=memberHtml;
  etfUpdateSelectedLabel();
}

function etfUpdateSelectedLabel(){
  const flow=state.research.etf.flow;
  const sel=flow.selectedCodes;
  if(sel===null){ $("etfFlowSelectedLabel").textContent=`全部宽基（${flow.series.length} 只）`; return; }
  if(sel.length===0){ $("etfFlowSelectedLabel").textContent="未选择（请选至少 1 只）"; return; }
  const names=flow.series.filter(s=>sel.includes(s.ts_code)).map(s=>s.name);
  $("etfFlowSelectedLabel").textContent=sel.length===1?names[0]:`已选 ${sel.length} 只：${names.slice(0,3).join("、")}${names.length>3?"…":""}`;
}

function etfNormalizeSelection(sel){
  const all=state.research.etf.flow.series.map(s=>s.ts_code);
  if(sel.length===0) return [];
  if(all.length>0 && all.every(c=>sel.includes(c))) return null;
  return sel;
}

function etfToggleMember(code){
  const flow=state.research.etf.flow;
  let sel=flow.selectedCodes;
  if(sel===null){ sel=[code]; }
  else { sel=sel.includes(code)?sel.filter(c=>c!==code):[...sel,code]; }
  flow.selectedCodes=etfNormalizeSelection(sel);
}

function etfToggleGroup(idx){
  const flow=state.research.etf.flow;
  const codes=flow.series.filter(s=>s.index_name===idx).map(s=>s.ts_code);
  let sel=flow.selectedCodes;
  if(sel===null){ sel=[...codes]; }
  else {
    const allIn=codes.length>0&&codes.every(c=>sel.includes(c));
    sel=allIn?sel.filter(c=>!codes.includes(c)):[...new Set([...sel,...codes])];
  }
  flow.selectedCodes=etfNormalizeSelection(sel);
}

function etfResolveSelection(selectedCodes,series){
  let members,label;
  if(selectedCodes===null){ members=series; label="全部宽基"; }
  else if(!selectedCodes.length){ members=[]; label="未选择"; }
  else { members=series.filter(s=>selectedCodes.includes(s.ts_code)); label=members.length===1?members[0].name:`已选 ${members.length} 只`; }
  const byDate=new Map();
  members.forEach(s=>{
    (s.points||[]).forEach(p=>{
      const d=p.trade_date; if(!d) return;
      let agg=byDate.get(d);
      if(!agg){ agg={trade_date:d,share_change_wan:0,flow_yi:0,amount_yi:0,total_share_wan:0,nav:null,hasShare:false}; byDate.set(d,agg); }
      if(p.share_change_wan!=null){ agg.share_change_wan+=Number(p.share_change_wan)||0; agg.hasShare=true; }
      if(p.flow_yi!=null){ agg.flow_yi+=Number(p.flow_yi)||0; }
      if(p.amount_yi!=null){ agg.amount_yi+=Number(p.amount_yi)||0; }
      if(p.total_share_wan!=null){ agg.total_share_wan+=Number(p.total_share_wan)||0; }
      if(p.nav!=null&&agg.nav==null){ agg.nav=Number(p.nav); }
    });
  });
  const points=[...byDate.values()].sort((a,b)=>String(a.trade_date).localeCompare(String(b.trade_date)));
  return {label,members,points};
}
function renderEtfFlowAll(){
  const flow=state.research.etf.flow;
  if(!flow.loaded) return;
  const scope=etfResolveSelection(flow.selectedCodes,flow.series);
  const window=flow.window||60;
  const minFlow=Number(flow.meta.min_flow_yi)||5;
  const points=scope.points.slice(-window);
  points.forEach(p=>{ p.spike=p.flow_yi!=null&&Math.abs(Number(p.flow_yi))>=minFlow; });
  flow._view={points,scope};
  renderEtfFlowSummary(points,scope.label);
  renderEtfFlowSeriesChart(points,scope.label,flow.selectedDate);
  renderEtfFlowDetail(scope,points,flow.selectedDate);
  renderEtfFlowSeriesSignals(flow.signals,flow.selectedCodes,points);
  etfSyncSingleDetail(scope.members);
}

function renderEtfFlowSummary(points,label){
  const sum=fn=>points.reduce((a,p)=>a+(fn(p)||0),0);
  const netShare=etfYi(sum(p=>p.share_change_wan));
  const netFlow=sum(p=>p.flow_yi);
  const last=points[points.length-1];
  const totalShare=etfYi(last?.total_share_wan);
  const lastAmount=last?.amount_yi!=null?Number(last.amount_yi):null;
  let maxIn=null,maxOut=null,maxInDate=null,maxOutDate=null;
  points.forEach(p=>{
    const v=etfYi(p.share_change_wan); if(v==null) return;
    if(maxIn==null||v>maxIn){ maxIn=v; maxInDate=p.trade_date; }
    if(maxOut==null||v<maxOut){ maxOut=v; maxOutDate=p.trade_date; }
  });
  const spikeDays=points.filter(p=>p.spike).length;
  $("etfFlowSummary").innerHTML=[
    researchFactorCard("区间净申赎",`${etfSigned(netShare,2)} 亿份`,`${label} · ${points.length} 个交易日`),
    researchFactorCard("区间净流入",`${etfSigned(netFlow,2)} 亿元`,"一级市场申赎金额（份额×净值）"),
    researchFactorCard("最新总份额",`${stockNumber(totalShare,2)} 亿份`,last?.trade_date?`截至 ${last.trade_date}`:"—"),
    researchFactorCard("最新成交额",lastAmount!=null?`${stockNumber(lastAmount,2)} 亿元`:"—",last?.trade_date?`${last.trade_date} 二级市场`:"—"),
    researchFactorCard("单日最大净申购",maxIn!=null&&maxIn>0?`+${stockNumber(maxIn,2)} 亿份`:"—",maxInDate||"—"),
    researchFactorCard("单日最大净赎回",maxOut!=null&&maxOut<0?`${stockNumber(maxOut,2)} 亿份`:"—",maxOutDate||"—"),
    researchFactorCard("异常信号天数",`${spikeDays} 天`,"单日净流入变动 ≥ 阈值"),
  ].join("");
}

function renderEtfFlowSeriesChart(points,label,selectedDate){
  const svg=$("etfFlowSeriesChart");
  const W=1200,margin={left:76,right:72},pw=W-margin.left-margin.right;
  const mainTop=24,mainH=196,subH=82,gap=18,topPad=14;
  const sub1Top=mainTop+mainH+gap;
  const sub2Top=sub1Top+subH+gap;
  const dateY=sub2Top+subH+24;
  const H=dateY+8;
  if(!points||!points.length){ svg.innerHTML=`<text x="600" y="${H/2}" text-anchor="middle" class="axis-label">暂无数据</text>`; return; }
  const n=points.length;
  const x=i=>margin.left+(i+0.5)*pw/n;
  const bw=Math.max(1.5,pw/n*0.62);
  /* 主图：份额柱 + 净流入折线（双轴） */
  const shareYi=points.map(p=>etfYi(p.share_change_wan));
  const flowYi=points.map(p=>Number(p.flow_yi)||0);
  const shareMax=Math.max(1,...shareYi.map(v=>v==null?0:Math.abs(v)));
  const flowMax=Math.max(1,...flowYi.map(Math.abs));
  const mainMid=mainTop+mainH/2;
  const yS=v=>mainMid-(v/(2*shareMax))*mainH;
  const yF=v=>mainMid-(v/(2*flowMax))*mainH;
  let out=`<text class="axis-label" x="${margin.left}" y="${mainTop-4}" text-anchor="start" font-weight="600">份额 · 亿份</text>`;
  out+=`<text class="axis-label" x="${W-margin.right}" y="${mainTop-4}" text-anchor="end" font-weight="600">净流入/流出 · 亿元</text>`;
  for(let t=0;t<=2;t++){
    const sv=shareMax*(1-t),fv=flowMax*(1-t),gy=mainTop+mainH*t/2;
    out+=`<line class="grid-line" x1="${margin.left}" y1="${gy}" x2="${W-margin.right}" y2="${gy}"/>`;
    out+=`<text class="axis-label" x="${margin.left-6}" y="${gy+3}" text-anchor="end">${etfAxisNum(sv)}</text>`;
    out+=`<text class="axis-label" x="${W-margin.right+6}" y="${gy+3}">${etfAxisNum(fv)}</text>`;
  }
  let bars="",line="",spikes="";
  points.forEach((p,i)=>{
    const sv=etfYi(p.share_change_wan),fv=Number(p.flow_yi)||0;
    const bx=x(i);
    const color=sv==null?"#8a96a1":(sv>=0?"#e24b4a":"#1d9e75");
    const y0=yS(0),y1=sv==null?y0:yS(sv);
    bars+=`<rect x="${(bx-bw/2).toFixed(2)}" y="${Math.min(y0,y1).toFixed(2)}" width="${bw.toFixed(2)}" height="${Math.max(1,Math.abs(y1-y0)).toFixed(2)}" fill="${color}" opacity="0.72"/>`;
    line+=`${i?"L":"M"}${bx.toFixed(2)},${yF(fv).toFixed(2)} `;
    if(p.spike) spikes+=`<circle cx="${bx.toFixed(2)}" cy="${yF(fv).toFixed(2)}" r="3.6" fill="#ba7517" stroke="#ffffff" stroke-width="1"/>`;
  });
  out+=bars;
  out+=`<path d="${line.trim()}" stroke="#348fcb" fill="none" stroke-width="1.6" opacity="0.9" vector-effect="non-scaling-stroke"/>`;
  out+=spikes;
  /* 副图1：累计净申赎 */
  const cum=[]; let run=0;
  points.forEach(p=>{ const v=etfYi(p.share_change_wan); if(v!=null) run+=v; cum.push(run); });
  const cMin=Math.min(0,...cum),cMax=Math.max(0,...cum),cSpan=Math.max(1,cMax-cMin);
  const yC=v=>sub1Top+subH-(v-cMin)/cSpan*(subH-topPad);
  out+=`<line class="grid-line" x1="${margin.left}" y1="${sub1Top}" x2="${W-margin.right}" y2="${sub1Top}"/>`;
  out+=`<text class="axis-label" x="${margin.left}" y="${sub1Top+10}" text-anchor="start" font-weight="600" fill="#176b61">累计净申赎 · 亿份</text>`;
  out+=`<text class="axis-label" x="${margin.left-6}" y="${sub1Top+topPad+3}" text-anchor="end">${stockNumber(cMax,1)}</text>`;
  out+=`<text class="axis-label" x="${margin.left-6}" y="${sub1Top+subH+3}" text-anchor="end">${stockNumber(cMin,1)}</text>`;
  let cPath=""; cum.forEach((v,i)=>{ cPath+=`${i?"L":"M"}${x(i).toFixed(2)},${yC(v).toFixed(2)} `; });
  out+=`<path d="${cPath.trim()}" stroke="#176b61" fill="none" stroke-width="1.6" vector-effect="non-scaling-stroke"/>`;
  const cLv=cum[cum.length-1];
  out+=`<circle cx="${x(n-1).toFixed(2)}" cy="${yC(cLv).toFixed(2)}" r="2.6" fill="#176b61"/><text class="axis-label" x="${W-margin.right}" y="${Math.max(yC(cLv)-6,sub1Top+10)}" text-anchor="end" fill="#176b61" font-weight="600">${etfSigned(cLv,2)}</text>`;
  /* 副图2：二级市场成交额 */
  const vals=points.map(p=>p.amount_yi!=null?Number(p.amount_yi):null);
  const vMax=Math.max(1,...vals.filter(v=>v!=null));
  const yV=v=>sub2Top+subH-(v/vMax)*(subH-topPad);
  out+=`<line class="grid-line" x1="${margin.left}" y1="${sub2Top}" x2="${W-margin.right}" y2="${sub2Top}"/>`;
  out+=`<text class="axis-label" x="${margin.left}" y="${sub2Top+10}" text-anchor="start" font-weight="600" fill="#8e6fc8">二级市场成交额 · 亿元</text>`;
  out+=`<text class="axis-label" x="${margin.left-6}" y="${sub2Top+topPad+3}" text-anchor="end">${stockNumber(vMax,1)}</text>`;
  out+=`<text class="axis-label" x="${margin.left-6}" y="${sub2Top+subH+3}" text-anchor="end">0</text>`;
  const base=sub2Top+subH;
  let area=`M${margin.left},${base.toFixed(2)} `;
  vals.forEach((v,i)=>{ area+=`L${x(i).toFixed(2)},${v==null?base.toFixed(2):yV(v).toFixed(2)} `; });
  area+=`L${x(n-1).toFixed(2)},${base.toFixed(2)} Z`;
  out+=`<path d="${area}" fill="#8e6fc8" opacity="0.16"/>`;
  let vLine="";
  vals.forEach((v,i)=>{ if(v!=null) vLine+=`${i?"L":"M"}${x(i).toFixed(2)},${yV(v).toFixed(2)} `; });
  out+=`<path d="${vLine.trim()}" stroke="#8e6fc8" fill="none" stroke-width="1.6" vector-effect="non-scaling-stroke"/>`;
  const vLv=vals[vals.length-1];
  if(vLv!=null){ out+=`<circle cx="${x(n-1).toFixed(2)}" cy="${yV(vLv).toFixed(2)}" r="2.6" fill="#8e6fc8"/>`; }
  const clean=vals.filter(v=>v!=null);
  const avg=clean.length?clean.reduce((a,b)=>a+b,0)/clean.length:null;
  out+=`<text class="axis-label" x="${W-margin.right}" y="${sub2Top+10}" text-anchor="end" fill="#8e6fc8" font-weight="600">日均 ${avg!=null?stockNumber(avg,2):"—"} 亿元</text>`;
  /* 选中竖线（贯穿三个 pane） */
  if(selectedDate){
    const idx=points.findIndex(p=>String(p.trade_date)===String(selectedDate));
    if(idx>=0){ const sx=x(idx); out+=`<line x1="${sx.toFixed(2)}" y1="${mainTop}" x2="${sx.toFixed(2)}" y2="${sub2Top+subH}" stroke="#176b61" stroke-width="1.5" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>`; }
  }
  /* 热区（覆盖三个 pane 整列）+ 底部共享日期轴 */
  let hits="";
  points.forEach((p,i)=>{
    const bx=x(i);
    hits+=`<rect class="etf-hit" data-etf-flow-day="${i}" x="${(bx-bw/2-2).toFixed(2)}" y="${mainTop}" width="${(bw+4).toFixed(2)}" height="${(sub2Top+subH-mainTop).toFixed(2)}" fill="transparent"/>`;
  });
  out+=hits;
  const ticks=Math.min(8,n);
  for(let t=0;t<ticks;t++){
    const i=Math.round(t*(n-1)/Math.max(ticks-1,1));
    out+=`<text class="axis-label" text-anchor="middle" x="${x(i).toFixed(2)}" y="${dateY}">${esc(String(points[i].trade_date||""))}</text>`;
  }
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  svg.innerHTML=out;
}

function renderEtfFlowDetail(scope,points,selectedDate){
  const box=$("etfFlowDetail");
  if(!selectedDate){ box.classList.add("hidden"); box.innerHTML=""; return; }
  const p=points.find(x=>String(x.trade_date)===String(selectedDate));
  box.classList.remove("hidden");
  if(!p){ box.innerHTML='<p class="empty-row">该日期在当前窗口内无数据</p>'; return; }
  const shareYi=etfYi(p.share_change_wan),flowYi=p.flow_yi!=null?Number(p.flow_yi):null,totalYi=etfYi(p.total_share_wan),amountYi=p.amount_yi!=null?Number(p.amount_yi):null;
  const direction=shareYi==null?"—":(shareYi>0?"净申购":shareYi<0?"净赎回":"持平");
  let contrib="";
  if(scope.members.length>1){
    const rows=scope.members.map(m=>{
      const mp=(m.points||[]).find(x=>String(x.trade_date)===String(selectedDate));
      if(!mp||mp.share_change_wan==null) return null;
      return {name:m.name,ts_code:m.ts_code,shareYi:etfYi(mp.share_change_wan),flowYi:mp.flow_yi!=null?Number(mp.flow_yi):null};
    }).filter(Boolean).sort((a,b)=>Math.abs(b.shareYi)-Math.abs(a.shareYi));
    contrib=`<div class="etf-flow-detail-contrib"><div class="etf-flow-detail-contrib-head">当日成分贡献（按份额变动排序）</div><div class="table-wrap"><table class="etf-flow-detail-table"><thead><tr><th>成分基金</th><th>份额变化（亿份）</th><th>金额变化（亿元）</th></tr></thead><tbody>${rows.map(r=>`<tr><td><span class="row-name">${esc(r.name)}</span><code class="row-code">${esc(r.ts_code)}</code></td><td class="${r.shareYi>0?"up":r.shareYi<0?"down":""}">${etfSigned(r.shareYi,2)}</td><td class="${r.flowYi>0?"up":r.flowYi<0?"down":""}">${etfSigned(r.flowYi,2)}</td></tr>`).join("")||'<tr><td colspan="3" class="empty-row">当日无成分份额变动</td></tr>'}</tbody></table></div></div>`;
  }
  box.innerHTML=`
    <div class="etf-flow-detail-head">
      <div><p class="eyebrow">DAILY DETAIL</p><h3>${esc(String(selectedDate))} · ${esc(scope.label)}</h3></div>
      <button class="quiet-action" data-etf-flow-clear>清除选择</button>
    </div>
    <div class="valuation-grid">
      ${researchFactorCard("份额变化",`${etfSigned(shareYi,2)} 亿份`,`${direction}${p.spike?" · 单日异常":""}`)}
      ${researchFactorCard("净流入/流出",`${etfSigned(flowYi,2)} 亿元`,"一级市场申赎金额（份额×净值）")}
      ${researchFactorCard("成交额",amountYi!=null?`${stockNumber(amountYi,2)} 亿元`:"—","二级市场买卖成交金额")}
      ${researchFactorCard("当日总份额",`${stockNumber(totalYi,2)} 亿份`,"全部/分组为成分合计")}
      ${researchFactorCard("单位净值",p.nav!=null?stockNumber(p.nav,4):"—","份额 × 净值 = 规模")}
    </div>
    ${contrib}
  `;
}

function renderEtfFlowSeriesSignals(signals,selectedCodes,points){
  const typeLabel={single_day_spike:"单日异常",consecutive_trend:"连续趋势"};
  const minDate=points[0]?.trade_date;
  const inScope=s=>{
    if(selectedCodes===null) return true;
    return selectedCodes.includes(s.ts_code);
  };
  const recent=(signals||[]).filter(s=>inScope(s)&&(!minDate||String(s.trade_date)>=String(minDate))).slice(0,40);
  $("etfFlowSeriesSignals").innerHTML=recent.map(s=>{
    const up=s.direction==="creation";
    const shareYi=etfYi(s.share_change_wan);
    const flowYi=s.flow_yi!=null?Number(s.flow_yi):null;
    const streak=s.streak_days!=null?` · 连续 ${s.streak_days} 日`:"";
    const dirCell=`${up?"净申购":"净赎回"}${streak}`;
    const shareCell=s.type==="single_day_spike"&&shareYi!=null?`${etfSigned(shareYi,2)} 亿份`:"—";
    const flowCell=s.type==="single_day_spike"&&flowYi!=null?`${etfSigned(flowYi,2)} 亿元`:"—";
    return `<tr><td>${esc(String(s.trade_date||"").slice(0,10))}</td><td><span class="pill info">${esc(typeLabel[s.type]||s.type)}</span></td><td><span class="row-name">${esc(s.name||"")}</span><code class="row-code">${esc(s.ts_code||"")}</code></td><td class="${up?"up":"down"}">${dirCell}</td><td class="${up?"up":"down"}">${shareCell}</td><td class="${up?"up":"down"}">${flowCell}</td></tr>`;
  }).join("")||'<tr><td colspan="6" class="empty-row">当前口径与窗口内暂无达到阈值的异常信号</td></tr>';
}

function etfTooltipHtml(p){
  const shareYi=etfYi(p.share_change_wan),flowYi=p.flow_yi!=null?Number(p.flow_yi):null,totalYi=etfYi(p.total_share_wan),amountYi=p.amount_yi!=null?Number(p.amount_yi):null;
  return `<strong>${esc(p.trade_date)}</strong><div class="stock-tooltip-grid"><span>份额变化</span><b class="${shareYi>0?"up":shareYi<0?"down":""}">${etfSigned(shareYi,2)} 亿份</b><span>净流入/流出</span><b class="${flowYi>0?"up":flowYi<0?"down":""}">${etfSigned(flowYi,2)} 亿元</b><span>成交额</span><b>${amountYi!=null?stockNumber(amountYi,2)+" 亿元":"—"}</b><span>总份额</span><b>${stockNumber(totalYi,2)} 亿份</b></div>`;
}

function bindEtfFlowChart(){
  const svg=$("etfFlowSeriesChart"),stage=$("etfFlowChartStage"),tip=$("etfFlowTooltip"),flow=state.research.etf.flow;
  const pointAt=ev=>{ const hit=ev.target.closest?.("[data-etf-flow-day]"); if(!hit) return null; const i=Number(hit.dataset.etfFlowDay); const pts=flow._view?.points; return pts?pts[i]||null:null; };
  svg.onmousemove=ev=>{
    const p=pointAt(ev); if(!p){ tip.classList.add("hidden"); return; }
    const sr=stage.getBoundingClientRect();
    tip.innerHTML=etfTooltipHtml(p);
    tip.classList.remove("hidden");
    tip.style.left=Math.min(ev.clientX-sr.left+14,sr.width-280)+"px";
    tip.style.top=Math.min(ev.clientY-sr.top+12,sr.height-90)+"px";
  };
  svg.onmouseleave=()=>tip.classList.add("hidden");
  svg.onclick=ev=>{ const p=pointAt(ev); if(!p) return; flow.selectedDate=flow.selectedDate===String(p.trade_date)?null:String(p.trade_date); renderEtfFlowAll(); };
}

async function loadEtfFlowSeries(){
  const flow=state.research.etf.flow;
  try{
    const view=await api("/api/v1/research/etfs/flow-series?lookback_days=250&min_flow_yi=5&streak_days=3");
    const data=view.data||{},meta=view.meta||{};
    flow.series=data.series||[]; flow.basket=data.basket||[]; flow.signals=data.signals||[]; flow.meta=meta; flow.loaded=true;
    if(flow.selectedCodes===undefined) flow.selectedCodes=null;
    etfRenderPicker();
    $("etfFlowSeriesMeta").textContent=`${meta.universe_size} 只主要宽基 · 数据至 ${meta.latest_data_date||"—"} · 单日异常阈值 ${meta.min_flow_yi} 亿 · 连续 ${meta.streak_days} 日同向`;
    renderEtfFlowAll();
  }catch(error){
    $("etfFlowSeriesMeta").textContent="宽基 ETF 资金流加载失败";
    $("etfFlowSeriesChart").innerHTML='<text x="600" y="200" text-anchor="middle" class="axis-label">加载失败</text>';
    $("etfFlowSummary").innerHTML='<p class="empty-row">加载失败</p>';
    $("etfFlowSeriesSignals").innerHTML='<tr><td colspan="6" class="empty-row">加载失败</td></tr>';
  }
}

let _etfFlowSingleTimer=null;
async function etfSyncSingleDetail(members){
  const panel=$("etfFlowSinglePanel");
  if(!members || members.length!==1){ panel.classList.add("hidden"); panel.innerHTML=""; return; }
  const m=members[0];
  clearTimeout(_etfFlowSingleTimer);
  _etfFlowSingleTimer=setTimeout(async()=>{
    panel.classList.remove("hidden");
    panel.innerHTML='<div class="module-loading">正在读取该 ETF 的净值与份额…</div>';
    try{
      const view=await api(`/api/v1/research/etfs/${encodeURIComponent(m.ts_code)}/nav-shares?lookback_days=120`);
      const nav=view.data||{},navRows=nav.nav?.series||[],shares=nav.shares||{},premium=nav.premium_pct||{};
      const latestNav=navRows.at(-1)?.[1],accumNav=navRows.at(-1)?.[2];
      const latestShare=shares.series?.at(-1)?.[1];
      const recentFlows=(shares.flows||[]).slice(-20),netCreate=recentFlows.reduce((sum,[,v])=>sum+(Number(v)||0),0);
      panel.innerHTML=`
        <div class="etf-flow-single-head">
          <div><p class="eyebrow">SINGLE ETF</p><h3>${esc(m.name)} <code class="row-code">${esc(m.ts_code)}</code></h3></div>
          <button class="primary" data-etf-jump-stock="${esc(m.ts_code)}" data-etf-jump-name="${esc(m.name)}">在标的研究中查看完整 K 线 →</button>
        </div>
        <div class="valuation-grid">
          ${researchFactorCard("最新单位净值",stockNumber(latestNav,4),`累计净值 ${stockNumber(accumNav,4)} · ${navRows.length} 个净值日`)}
          ${researchFactorCard("最新溢价率",researchPct(premium.latest),`二级市场收盘价相对单位净值的偏离`)}
          ${researchFactorCard("最新份额",`${stockNumber(latestShare,3)} 亿份`,`${shares.series?.length||0} 个份额观测日`)}
          ${researchFactorCard("近 20 日净申赎",`${netCreate>=0?"+":""}${stockNumber(netCreate,3)} 亿份`,netCreate>0?"净申购（资金流入）":netCreate<0?"净赎回（资金流出）":"份额基本持平")}
        </div>
        <p class="muted etf-flow-methodology">K 线与技术因子已合并到「个股研究 → 标的研究」，点击上方按钮跳转查看完整技术分析。</p>
      `;
    }catch(error){
      panel.innerHTML=`<div class="module-loading">净值与份额加载失败：${esc(error.message)}</div>`;
    }
  },180);
}
bindEtfFlowChart();
async function loadEtfResearch(){
  loadEtfFlowSeries();
  const view=state.research.etf;
  if(!view.items){
    try{const directory=await api("/api/v1/research/etfs/directory?limit=200");view.items=directory.data.items;view.meta=`${directory.data.trade_date} · 共 ${directory.meta.matched} 只场内基金`;}
    catch(error){notice(`ETF 目录加载失败：${error.message}`);return;}
  }
  renderEtfRows();
}
function researchSortedRows(view,items,limit,columns){
  const {key,dir}=view.sort||{key:null,dir:-1};
  if(!key)return items.slice(0,limit);
  const numeric=columns[key]!=="text";
  return [...items].sort((a,b)=>{
    const av=a[key],bv=b[key];
    if(av==null)return 1;if(bv==null)return -1;
    const cmp=numeric?Number(av)-Number(bv):String(av).localeCompare(String(bv),"zh");
    return cmp*dir;
  }).slice(0,limit);
}
function refreshSortIndicators(viewKey){
  const view=state.research[viewKey];
  document.querySelectorAll(`th[data-research-sort="${viewKey}"]`).forEach(el=>el.removeAttribute("data-dir"));
  if(view?.sort){const th=document.querySelector(`th[data-research-sort="${viewKey}"][data-sort-key="${view.sort.key}"]`);if(th)th.dataset.dir=view.sort.dir>0?"asc":"desc";}
}
function bindResearchSortHeaders(){
  document.querySelectorAll("th[data-research-sort]").forEach(th=>{
    const viewKey=th.dataset.researchSort,key=th.dataset.sortKey;
    th.onclick=()=>{
      const view=state.research[viewKey];
      if(view.sort&&view.sort.key===key)view.sort.dir=-view.sort.dir;
      else view.sort={key,dir:-1};
      refreshSortIndicators(viewKey);
      (viewKey==="etf"?renderEtfRows:renderSectorRows)();
    };
  });
}
const researchAmountYi=value=>value==null||!Number.isFinite(Number(value))?"—":(Number(value)/100000).toFixed(2);
function renderEtfRows(){
  const view=state.research.etf,query=($("etfSearch").value||"").trim().toLowerCase();
  const items=(view.items||[]).filter(item=>!query||String(item.name||"").toLowerCase().includes(query)||String(item.ts_code||"").toLowerCase().includes(query));
  const sorted=researchSortedRows(view,items,80,{});
  $("etfDirectoryMeta").textContent=`${view.meta||""} · 匹配 ${items.length} 只`;
  $("etfRows").innerHTML=sorted.map(item=>`<tr class="interface-row${view.selected?.ts_code===item.ts_code?" active":""}" data-etf-select="${esc(item.ts_code)}" data-etf-name="${esc(item.name)}"><td><span class="row-name">${esc(item.name)}</span><code class="row-code">${esc(item.ts_code)}</code></td><td>${stockNumber(item.close)}</td><td class="${Number(item.pct_change)>0?"up":Number(item.pct_change)<0?"down":""}">${researchPct(item.pct_change)}</td><td>${researchAmountYi(item.amount)}</td></tr>`).join("")||'<tr><td colspan="4" class="empty-row">没有匹配的 ETF</td></tr>';
}
async function selectEtf(item){
  const view=state.research.etf;view.selected=item;view.response=null;view.nav=null;view.window=null;view.requestVersion=(view.requestVersion||0)+1;const version=view.requestVersion;
  $("etfWorkspace").classList.remove("hidden");const empty=$("etfEmpty");if(empty)empty.classList.add("hidden");
  $("etfName").textContent=item.name;$("etfCode").textContent=item.ts_code;$("etfClose").textContent="加载中…";
  $("etfMeta").textContent=[item.fund_type||"场内基金",item.amount!=null?`成交额 ${researchAmountYi(item.amount)} 亿元`:null].filter(Boolean).join(" · ");
  $("etfChange").textContent=researchPct(item.pct_change);$("etfChange").className=Number(item.pct_change)>0?"up":Number(item.pct_change)<0?"down":"";$("etfDate").textContent="最新交易日";
  try{
    const result=await api(`/api/v1/research/etfs/${encodeURIComponent(item.ts_code)}/nav-shares?lookback_days=400`);
    if(version!==view.requestVersion)return;
    view.nav=result;renderEtfResearch();
  }catch(error){notice(`ETF 净值与份额加载失败：${error.message}`);}
}
function renderEtfResearch(){
  const view=state.research.etf;if(!view.nav)return;
  const nav=view.nav?.data||{};
  const navRows=nav.nav?.series||[],premium=nav.premium_pct||{},shares=nav.shares||{};
  $("etfClose").textContent=stockNumber(navRows.at(-1)?.[1],4);
  $("etfNavGrid").innerHTML=[
    researchFactorCard("单位净值",stockNumber(navRows.at(-1)?.[1],4),`累计净值 ${stockNumber(navRows.at(-1)?.[2],4)} · ${navRows.length} 个净值日`),
    researchFactorCard("最新溢价率",researchPct(premium.latest),`基于最新收盘价相对单位净值`),
    researchFactorCard("最新份额",`${stockNumber(shares.series?.at(-1)?.[1],3)} 亿份`,`管理机构 ${esc(nav.instrument?.management||"—")}`),
  ].join("");
  $("etfFlowRows").innerHTML=(shares.flows||[]).slice(-15).reverse().map(([day,value])=>`<tr><td>${esc(day)}</td><td class="${value>0?"up":value<0?"down":""}">${stockNumber(value,3)}</td></tr>`).join("")||'<tr><td colspan="2" class="empty-row">暂无份额变动记录</td></tr>';
  const shareRows=shares.series||[],recentFlows=(shares.flows||[]).slice(-20),netCreate=recentFlows.reduce((sum,[,v])=>sum+(Number(v)||0),0);
  $("etfSharesGrid").innerHTML=[
    researchFactorCard("最新份额",`${stockNumber(shareRows.at(-1)?.[1],3)} 亿份`,`${shareRows.length} 个份额观测日`),
    researchFactorCard("近 20 日净申赎",`${netCreate>=0?"+":""}${stockNumber(netCreate,3)} 亿份`,netCreate>0?"净申购（资金流入）":netCreate<0?"净赎回（资金流出）":"份额基本持平"),
    researchFactorCard("最大单日变动",`${(function(){const m=recentFlows.reduce((a,[,v])=>Math.abs(Number(v))>Math.abs(a)?Number(v):a,0);return `${m>=0?"+":""}${stockNumber(m,3)}`})()} 亿份`,`观测窗口 ${recentFlows.at(0)?.[0]||"—"} → ${recentFlows.at(-1)?.[0]||"—"}`),
  ].join("");
  renderEtfNavChart(navRows);
  renderEtfShareChart(shareRows);
}
function renderEtfNavChart(navRows){
  const grid=$("etfNavGrid");let svg=document.getElementById("etfNavChart");
  if(!svg){svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.id="etfNavChart";svg.setAttribute("viewBox","0 0 640 190");svg.setAttribute("role","img");svg.style.gridColumn="1 / -1";grid.appendChild(svg);}
  renderResearchLinesInto(svg,navRows.map(r=>[r[0],r[1]]),{color:"#1d9e75",digits:2});
}
function renderEtfShareChart(shareRows){
  const grid=$("etfSharesGrid");let svg=document.getElementById("etfShareChart");
  if(!svg){svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.id="etfShareChart";svg.setAttribute("viewBox","0 0 640 190");svg.setAttribute("role","img");svg.style.gridColumn="1 / -1";grid.appendChild(svg);}
  renderResearchLinesInto(svg,shareRows,{color:"#348fcb",digits:1});
}
// ---- 板块研究 ----
async function loadSectorResearch(){await loadSectorDirectory();}
async function loadAlipayHotPlates(){
  try{
    const view=await api("/api/v1/research/sectors/alipay-hot-plates?limit=50");
    const data=view.data||{},items=data.items||[],meta=view.meta||{};
    const dateStr=data.trade_date?`${data.trade_date}${meta.lag_days!=null?` · 滞后 ${meta.lag_days} 天`:""}`:"暂无数据";
    if(state.research.sector.source!=="alipay")return;
    Object.assign(state.research.sector,{items:items.map(r=>({ts_code:r.symbol,name:r.plate_name,pct_change:r.pct_chg,net_amount:r.main_net_inflow==null?null:r.main_net_inflow/1e8,rank:r.rank})),meta:"支付宝热门榜 · "+dateStr});
    renderSectorRows();
  }catch(error){if(state.research.sector.source==="alipay"){$("sectorDirectoryMeta").textContent="支付宝热门板块加载失败："+error.message;$("sectorRows").replaceChildren();}}
}
async function loadSectorDirectory(){
  const view=state.research.sector;
  if(view.source==="alipay")return loadAlipayHotPlates();
  const source=view.source;
  try{
    const directory=await api(`/api/v1/research/sectors/directory?source=${view.source}&limit=400`);
    if(source!==view.source)return;
    view.items=directory.data.items;
    view.meta=`${directory.data.quote_date} · ${view.source==="ths"?"同花顺行业与概念指数":"东方财富板块"}`;
    refreshSortIndicators("sector");
  }catch(error){notice(`板块列表加载失败：${error.message}`);return;}
  renderSectorRows();
}
function renderSectorRows(){
  const view=state.research.sector,query=($("sectorSearch").value||"").trim().toLowerCase();
  const items=(view.items||[]).filter(item=>!query||String(item.name||"").toLowerCase().includes(query)||String(item.ts_code||"").toLowerCase().includes(query));
  const sorted=researchSortedRows(view,items,120,{});
  $("sectorDirectoryMeta").textContent=`${view.meta||"同花顺行业与概念指数"} · 匹配 ${items.length} 个`;
  $("sectorRows").innerHTML=sorted.map(item=>`<tr class="interface-row${view.selected?.ts_code===item.ts_code?" active":""}" data-sector-select="${esc(item.ts_code)}" data-sector-name="${esc(item.name)}"><td><span class="row-name">${esc(item.name||"")}${item.board_type==="N"?' <small class="iface-name">概念</small>':item.board_type==="I"?' <small class="iface-name">行业</small>':""}</span><code class="row-code">${esc(item.ts_code)}</code></td><td class="${Number(item.pct_change)>0?"up":Number(item.pct_change)<0?"down":""}">${researchPct(item.pct_change)}</td><td>${item.volume==null?"—":fmt(item.volume)}</td><td class="${Number(item.net_amount)>0?"up":Number(item.net_amount)<0?"down":""}">${item.net_amount==null?"—":fmt(item.net_amount)}</td><td>${esc(item.lead_stock||"—")}</td></tr>`).join("")||'<tr><td colspan="5" class="empty-row">没有匹配的板块</td></tr>';
}
function switchSectorSource(source){
  state.research.sector.requestVersion=(state.research.sector.requestVersion||0)+1;
  $("sectorRows").replaceChildren();state.research.sector.source=source;state.research.sector.items=null;state.research.sector.selected=null;state.research.sector.response=null;state.research.sector.members=null;state.research.sector.window=null;
  document.querySelectorAll("[data-sector-source]").forEach(b=>b.classList.toggle("active",b.dataset.sectorSource===source));
  $("sectorWorkspace").classList.add("hidden");const empty=$("sectorEmpty");if(empty)empty.classList.remove("hidden");
  loadSectorDirectory();
}
async function selectSector(item){
  const view=state.research.sector;view.selected=item;view.response=null;view.members=null;view.window=null;
  $("sectorWorkspace").classList.remove("hidden");const empty=$("sectorEmpty");if(empty)empty.classList.add("hidden");
  $("sectorName").textContent=item.name;$("sectorCode").textContent=item.ts_code;$("sectorClose").textContent="加载中…";
  $("sectorMeta").textContent=`${view.source==="ths"?"同花顺":"东方财富"} · ${item.board_type==="N"?"概念板块":item.board_type==="I"?"行业板块":"板块指数"}`;
  if(view.source==="alipay"){
    const version=view.requestVersion=(view.requestVersion||0)+1;
    $("sectorMeta").textContent="支付宝板块 · 日K · 不复权";
    for(const id of ["sectorPriceChart","sectorVolumeChart","sectorMemberChips","sectorChange","sectorDate"])$(id).replaceChildren();
    $("sectorMembersMeta").textContent="本页不提供支付宝成分股";
    try{
      const route="/api/v1/quote/kline-batch";
      const result=await api("/api/v1/data/sources/ant_data/query",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode:"data",requests:[{url:route,params:{symbols:[item.ts_code],period:"P_Day1",split:"S_Unsplit",count:180}}]})});
      if(version!==view.requestVersion)return;
      const batch=result.data?.results?.find(r=>r.url===route),fields=batch?.meta?.fields||[];
      const points=(batch?.data||[]).map(row=>Object.fromEntries(fields.map((k,i)=>[k,row[i]]))).filter(r=>r.symbol===item.ts_code&&r.period==="P_Day1"&&["open","high","low","close"].every(k=>r[k]!=null&&Number.isFinite(Number(r[k])))).map(r=>({...r,trade_date:String(r.date).slice(0,10)})).sort((a,b)=>a.trade_date.localeCompare(b.trade_date));
      if(!points.length)throw Error("该板块没有可验证的日K数据");
      view.response={data:{timeframes:{"1d":{chart:{points},observations:points.length}}}};
      renderResearchHeadline("sector",view.response.data.timeframes["1d"],item);renderResearchChart("sector",points);
    }catch(e){if(version===view.requestVersion){$("sectorClose").textContent="—";notice("支付宝板块行情未加载："+e.message);}}
    return;
  }
  try{
    await loadResearchPanels(view,{
      response:`/api/v1/research/instruments/sector/${encodeURIComponent(item.ts_code)}/technicals?lookback_days=1200&chart_points=180&provider=${view.source}`,
      members:`/api/v1/research/sectors/${encodeURIComponent(item.ts_code)}/members?source=${view.source}&limit=150`,
    },renderSectorResearch,"板块研究");
  }catch(error){notice(`板块研究加载失败：${error.message}`);}
}
function renderSectorResearch(){
  const view=state.research.sector;if(!view.response)return;
  const timeframe=view.response.data.timeframes["1d"];
  renderResearchHeadline("sector",timeframe,{name:view.selected.name,ts_code:view.selected.ts_code});
  renderResearchChart("sector",timeframe.chart.points);
  $("sectorDate").textContent=`${timeframe.chart.points.at(-1)?.trade_date||"—"} · ${timeframe.observations} 根`;
  const members=view.members?.data?.members||[];
  $("sectorMembersMeta").textContent=`共 ${members.length} 只成分股 · 点击跳转个股研究`;
  $("sectorMemberChips").innerHTML=members.map(member=>`<button class="peer-chip" data-sector-member="${esc(member.ts_code)}">${esc(member.name||member.ts_code)}</button>`).join("")||'<span class="empty-row">暂无成分股数据</span>';
}
function jumpToStock(code,name){
  $("stockSearch").value=code;stockSearch(true);activate("stock");
}
// ===== 研究分组结束 =====

// ---- 宏观研究 ----
const MACRO_ENDPOINTS={regime:"/api/v1/research/macro/regime",growth:"/api/v1/research/macro/growth?periods=36",inflation:"/api/v1/research/macro/inflation?periods=36",liquidity:"/api/v1/research/macro/liquidity?periods=36",rates:"/api/v1/research/macro/rates?observations=90",calendar:"/api/v1/research/macro/schedule?limit=80"};
const MACRO_DIRECTIONS={improving:"改善",weakening:"走弱",rising:"上行",falling:"下行",tightening:"收紧",easing:"宽松",mixed:"混合"};
function macroNumber(v){return v==null||v===""?NaN:Number(v);}
function macroSeriesRows(series){
  if(!Array.isArray(series))return[];
  return series.map(row=>[String(row.observation_date||row.period||""),Number(row.gdp_yoy??row.yoy??row.m2_yoy??row.inc_month??row.three_month??row.manufacturing??NaN)]).filter(r=>r[0]&&Number.isFinite(r[1])).reverse();
}
async function loadMacroResearch(){
  const view=state.research.macro;
  if(!view.loaded.regime){
    $("macroLoading").classList.remove("hidden");
    document.querySelectorAll("[data-macro-module]").forEach(b=>b.classList.toggle("active",b.dataset.macroModule===view.tab));
    document.querySelectorAll("[data-macro-module-panel]").forEach(p=>p.classList.toggle("hidden",p.dataset.macroModulePanel!==view.tab));
    await loadMacroModule(view.tab);
  }
}
async function loadMacroModule(name){
  const view=state.research.macro;
  try{
    if(!view.loaded[name])view.data[name]=await api(MACRO_ENDPOINTS[name]);
    view.loaded[name]=true;
    $("macroLoading").classList.add("hidden");
    ({regime:renderMacroRegime,growth:renderMacroGrowth,inflation:renderMacroInflation,liquidity:renderMacroLiquidity,rates:renderMacroRates,calendar:renderMacroCalendar})[name](view.data[name]);
  }catch(error){$("macroLoading").classList.add("hidden");notice(`宏观研究「${name}」加载失败：${error.message}`);}
}
function switchMacroModule(name){
  const view=state.research.macro;view.tab=name;
  document.querySelectorAll("[data-macro-module]").forEach(b=>b.classList.toggle("active",b.dataset.macroModule===name));
  document.querySelectorAll("[data-macro-module-panel]").forEach(p=>p.classList.toggle("hidden",p.dataset.macroModulePanel!==name));
  loadMacroModule(name);
}
function renderMacroRegime(payload){
  const data=payload?.data||{},meta=payload?.meta||{};
  $("macroRegimeGrid").innerHTML=[
    researchFactorCard("增长",MACRO_DIRECTIONS[data.growth?.direction]||"—",`GDP 同比 ${stockNumber(data.growth?.gdp?.gdp_yoy)}%（${data.growth?.gdp?.period||"—"}）· PMI ${stockNumber(data.growth?.pmi?.manufacturing)}（${data.growth?.pmi?.period||"—"}）`),
    researchFactorCard("通胀",MACRO_DIRECTIONS[data.inflation?.direction]||"—",`CPI 同比 ${stockNumber(data.inflation?.cpi?.yoy)}% · PPI 同比 ${stockNumber(data.inflation?.ppi?.yoy)}%（${data.inflation?.cpi?.period||"—"}）`),
    researchFactorCard("流动性",MACRO_DIRECTIONS[data.liquidity?.direction]||"—",`M2 同比 ${stockNumber(data.liquidity?.money_supply?.m2_yoy)}% · SHIBOR 3M ${stockNumber(data.liquidity?.shibor?.three_month)}% · LPR 1Y ${stockNumber(data.liquidity?.lpr?.one_year)}%`),
    researchFactorCard("社融增量",`${stockNumber(data.liquidity?.social_financing?.inc_month,0)} 亿`,`单月增量 · ${data.liquidity?.social_financing?.period||"—"}`),
  ].join("");
  $("macroRegimeNote").textContent=`象限判定 ${data.quadrant||"—"} · 方向为分项多数投票 · 数据截至 ${meta.as_of||"—"}`;
}
function renderMacroThemeChart(svgId,rows,opts){
  renderResearchLinesInto($(svgId),rows,opts);
}
function renderMacroGrowth(payload){
  const data=payload?.data||{};
  const gdp=macroSeriesRows(data.gdp);
  renderLineCard("macroGdpChart","macroGdpNote",gdp,{color:"#185FA5",digits:2});
  const pmi=data.pmi||[];
  const fields=[["manufacturing","制造业"],["large_enterprise","大型企业"],["medium_enterprise","中型企业"],["small_enterprise","小型企业"],["production","生产"],["new_orders","新订单"],["composite","综合"]];
  $("macroPmiGrid").innerHTML=fields.map(([key,label])=>{
    const rows=pmi.map(r=>[String(r.observation_date||r.period),macroNumber(r[key])]).filter(r=>r[0]&&Number.isFinite(r[1])).reverse();
    const latest=rows.at(-1)?.[1];
    return `<section class="card"><div class="card-head"><h3>${label}</h3><p>${latest!=null?`最新 ${stockNumber(latest)}`:"暂无数据"}</p></div><svg viewBox="0 0 640 190" role="img"></svg></section>`;
  }).join("");
  $("macroPmiGrid").querySelectorAll("svg").forEach((svg,i)=>renderResearchLinesInto(svg,pmi.map(r=>[String(r.observation_date||r.period),macroNumber(r[fields[i][0]])]).filter(r=>r[0]&&Number.isFinite(r[1])).reverse(),{color:"#0F6E56",baseline:50,digits:1,label:true}));
  $("macroPmiNote").textContent=`50 为荣枯线 · 共 ${pmi.length} 个月度观测`;
}
function renderMacroInflation(payload){
  const data=payload?.data||{};
  renderLineCard("macroCpiChart","macroCpiNote",macroSeriesRows(data.cpi),{color:"#BA7517",zero:true,digits:2});
  renderLineCard("macroPpiChart","macroPpiNote",macroSeriesRows(data.ppi),{color:"#993C1D",zero:true,digits:2});
}
function renderMacroLiquidity(payload){
  const data=payload?.data||{};
  const m2=data.money_supply||[];
  const pairs=m2.map(r=>[String(r.observation_date||r.period),macroNumber(r.m1_yoy),macroNumber(r.m2_yoy)]).filter(r=>r[0]&&Number.isFinite(r[1])&&Number.isFinite(r[2])).reverse();
  const scissors=pairs.map(([d,m1,m2v])=>[d,m1-m2v]);
  renderLineCard("macroM2Chart","macroM2Note",scissors,{color:"#534AB7",zero:true,digits:2});
  renderLineCard("macroSfChart","macroSfNote",(data.social_financing||[]).map(r=>[String(r.observation_date||r.period),macroNumber(r.inc_month)]).filter(r=>r[0]&&Number.isFinite(r[1])).reverse(),{color:"#378ADD",zero:true,digits:0});
  renderLineCard("macroShiborChart","macroShiborNote",(data.shibor||[]).map(r=>[String(r.observation_date),macroNumber(r.three_month)]).filter(r=>r[0]&&Number.isFinite(r[1])).reverse(),{color:"#1D9E75",digits:3});
  const lpr=data.lpr||[],latest=lpr.at(-1);
  $("macroLprGrid").innerHTML=[
    researchFactorCard("LPR 1Y",stockNumber(latest?.[1]??latest?.one_year),latest?`发布日 ${latest[0]||latest.observation_date||"—"}`:"暂无数据"),
    researchFactorCard("LPR 5Y",stockNumber(latest?.five_year),`${lpr.length} 个月度发布`),
  ].join("");
  $("macroLprNote").textContent=`LPR 自 2019-08 改革后按月发布；最新 ${latest?.[0]||"—"}`;
}
function renderMacroRates(payload){
  const data=payload?.data||{},meta=payload?.meta||{};
  const spread=(data.spread_10y||[]).map(r=>[String(r.observation_date),macroNumber(r.spread)]).reverse();
  renderResearchLinesInto($("macroSpreadChart"),spread,{color:"#D85A30",zero:true,digits:2,label:true});
  const latestSpread=(data.spread_10y||[])[0];
  $("macroSpreadNote").textContent=latestSpread?`最新 ${latestSpread.observation_date} · 中债 10Y ${stockNumber(latestSpread.cn_10y)}% − 美债 10Y ${stockNumber(latestSpread.us_10y)}%`:"暂无重叠交易日";
  const tenorLabels={yield_3m:"3月",yield_6m:"6月",yield_1y:"1年",yield_3y:"3年",yield_5y:"5年",yield_7y:"7年",yield_10y:"10年",yield_30y:"30年",m3:"3月",m6:"6月",y1:"1年",y2:"2年",y3:"3年",y5:"5年",y7:"7年",y10:"10年",y20:"20年",y30:"30年"};
  const curveCards=(curveRow,dateField)=>{
    if(!curveRow||!Object.keys(curveRow).length)return'<p class="empty-row">暂无数据</p>';
    const date=curveRow.observation_date;
    return Object.entries(tenorLabels).filter(([k])=>curveRow[k]!=null).map(([k,label])=>researchFactorCard(label,`${stockNumber(curveRow[k])}%`,`观测日 ${date||"—"}`)).join("");
  };
  const cnCurves=data.cn_curve?.latest||{};
  $("macroCnCurveGrid").innerHTML=Object.entries(cnCurves).map(([name,row])=>`<h3 style="grid-column:1/-1;margin:4px 0 0">${esc(name)}${row.observation_date?` · ${row.observation_date}`:""}</h3>${Object.entries(tenorLabels).filter(([k])=>row[k]!=null).map(([k,label])=>researchFactorCard(label,`${stockNumber(row[k])}%`,`10Y−3M ${stockNumber(row.yield_10y==null||row.yield_3m==null?null:row.yield_10y-row.yield_3m)}%`)).join("")}`).join("")||'<p class="empty-row">暂无中债数据（等待首次定采入库）</p>';
  $("macroCnCurveNote").textContent=`三条曲线 · 8 档期限 · 历史序列 ${data.cn_curve?.history?.length||0} 行`;
  $("macroUsCurveGrid").innerHTML=curveCards(data.us_curve?.latest);
  $("macroUsCurveNote").textContent=data.us_curve?.latest?.observation_date?`观测日 ${data.us_curve.latest.observation_date} · 历史 ${data.us_curve?.history?.length||0} 个交易日`:"暂无美债数据";
  const cn10=(data.cn_curve?.history||[]).concat(Object.values(data.cn_curve?.latest||{})).filter(r=>r.curve_name==="中债国债收益率曲线").map(r=>[String(r.observation_date),macroNumber(r.yield_10y)]).filter(r=>r[0]&&Number.isFinite(r[1])).sort((a,b)=>a[0]<b[0]?-1:1);
  const us10=(data.us_curve?.history||[]).concat(data.us_curve?.latest?[data.us_curve.latest]:[]).map(r=>[String(r.observation_date),macroNumber(r.y10)]).filter(r=>r[0]&&Number.isFinite(r[1])).sort((a,b)=>a[0]<b[0]?-1:1);
  renderLineCard("macroCn10yChart","macroCn10yNote",cn10,{color:"#185FA5",digits:2});
  renderLineCard("macroUs10yChart","macroUs10yNote",us10,{color:"#993C1D",digits:2});
}
function renderMacroCalendar(payload){
  const rows=payload?.data||[];
  $("macroScheduleRows").innerHTML=rows.map(r=>`<tr><td>${esc(String(r.publish_date||"—"))}</td><td>${esc(String(r.title||"—"))}</td><td>${esc(String(r.issuing_org||"—"))}</td><td><code>${esc(String(r.data_api||"—"))}</code></td></tr>`).join("")||'<tr><td colspan="4" class="empty-row">暂无未来的发布安排</td></tr>';
}
document.getElementById("macroModuleTabs").addEventListener("click",e=>{const b=e.target.closest("[data-macro-module]");if(b)switchMacroModule(b.dataset.macroModule);});

// 研究页 K 线缩放/平移按钮与滚轮、列表排序表头绑定
["market","etf","sector"].forEach(prefix=>{
  const bind=(suffix,fn)=>{const el=$(prefix+suffix);if(el)el.onclick=fn;};
  bind("ZoomIn",()=>researchZoom(prefix,1));
  bind("ZoomOut",()=>researchZoom(prefix,-1));
  bind("ZoomReset",()=>resetResearchWindow(prefix));
  bind("PanPrev",()=>researchPan(prefix,-1));
  bind("PanNext",()=>researchPan(prefix,1));
  const svg=$(prefix+"PriceChart");
  if(svg)svg.addEventListener("wheel",e=>{if(!(e.ctrlKey||e.metaKey)||!state.research[prefix].response)return;e.preventDefault();const rect=svg.getBoundingClientRect();researchZoom(prefix,e.deltaY<0?1:-1,(e.clientX-rect.left)/Math.max(rect.width,1));},{passive:false});
});
bindResearchSortHeaders();
refreshSortIndicators("etf");refreshSortIndicators("sector");

// ---- 量化因子目录 ----
async function loadFactors(force=false){
  if(force||!state.factors){
    try{ state.factors=await api("/api/v1/data/factor-catalog"); }
    catch(error){ notice(`量化因子目录加载失败：${error.message}`); return; }
  }
  renderFactors();
}
let factorPage = 1;
function renderFactors(){
  const cat=state.factors; if(!cat) return;
  $("factorProviderInventory").innerHTML=(cat.unregistered_provider_datasets||[]).map(item=>`<p><code>${esc(item.dataset)}</code> · ${esc(item.source)}<br>${esc(item.reason)}</p>`).join("");
  const category=$("factorCategory");
  if(category.options.length===1) category.insertAdjacentHTML("beforeend",cat.categories.map(c=>`<option value="${esc(c.name)}">${esc(c.label)}</option>`).join(""));
  const search=($("factorSearch").value||"").trim().toLowerCase();
  const rows=cat.factors.filter(f=>(!category.value||f.category===category.value)&&(!$("factorOrigin").value||f.origin===$("factorOrigin").value)&&(!$("factorPackage").value||f.package===$("factorPackage").value)&&(!$("factorReadiness").value||f.availability===$("factorReadiness").value)&&(!search||[f.name,f.category_label,f.official_source,...f.aliases].join(" ").toLowerCase().includes(search)));
  const pages=Math.max(1,Math.ceil(rows.length/25)); factorPage=Math.min(factorPage,pages);
  const range=cat.local_storage_range||{};
  $("factorSummary").textContent=`${cat.factor_count} 个正式特征 · 本地计算 ${cat.local_count} · Tushare 筹码 ${cat.provider_count} · 同义名称不重复计数`;
  $("factorStrip").innerHTML=`<div class="metrics compact"><article><span>日频快照存储边界</span><strong>${esc(range.min_date||"—")} ~ ${esc(range.max_date||"—")}</strong><small>边界不代表连续完整；各因子以最新日非空证券数为准</small></article><article><span>内部对照库 · 不对外供给</span><strong>factor_value</strong><small>保留采集与抽检，不用它填补本地缺值</small></article></div>`;
  $("factorStrip").innerHTML+=`<p class="muted">口径 ${esc(cat.schema_version||"—")} · 逐特征输入审计：${(cat.quality||[]).map(q=>`${esc({ready:"就绪",partial:"有未解释缺口",not_expected:"当日无行情",not_audited:"未审计"}[q.audit_status]||q.audit_status)} ${fmt(q.securities)} 只`).join(" / ")||"新口径尚未计算"}。执行成功、有计算值、输入就绪、数值抽检通过是不同状态。</p>`;
  const labels={matched:"逐值抽检达标（≥99%容差内）",correlated:"仅相关性达标 · 数值未对齐",review_required:"口径待核验",not_comparable:"缺对照或无配对样本",not_compared:"未抽检",provider_contract:"供应商口径"};
  const available={has_values:"有计算值",missing:"无计算值",not_audited:"待审计"};
  const body=rows.slice((factorPage-1)*25,factorPage*25).map(f=>`<tr><td><strong><code>${esc(f.name)}</code></strong><small class="muted">${f.aliases.length?"别名："+esc(f.aliases.join(" / ")):"独立特征"}</small></td><td>${esc(f.category_label)}<small class="muted">${esc(f.package)} · 日频</small></td><td><span class="pill ${f.origin==="local"?"info":"ready"}">${f.origin==="local"?"本地计算":"Tushare 提供"}</span><small class="muted">输入：${esc(f.input_provider)}</small></td><td><span class="pill ${f.availability==="missing"?"warning":"info"}">${available[f.availability]||"未知"}</span><small class="muted">${f.observation_date?esc(f.observation_date)+" · "+fmt(f.available_securities)+"/"+fmt(f.observed_securities)+" 只非空":"尚无证券级审计"}</small></td><td>${esc(labels[f.validation?.validation_status]||"未核验")}</td><td><details><summary>口径与接口</summary><p>${esc(f.formula||"详见版本化计算代码 / 供应商契约；不推断公式等价")}</p><p><code>${esc(f.query_path)}</code></p><small>${esc(f.id)}<br>唯一存储：${esc(f.storage)}${f.implementation?"<br>"+esc(f.implementation):""}</small></details></td></tr>`).join("");
  $("factorCatalog").innerHTML=`<section class="card"><div class="table-wrap"><table><thead><tr><th>正式特征 / 别名</th><th>研究分类 / 系列</th><th>唯一正式来源</th><th>数据可用性</th><th>独立验证</th><th>契约</th></tr></thead><tbody>${body||'<tr><td colspan="6">没有匹配的特征</td></tr>'}</tbody></table></div><p class="muted">${cat.notes.map(esc).join("<br>")}</p></section>`;
  $("factorPage").textContent=`共 ${rows.length} 项 · 第 ${factorPage} / ${pages} 页 · 每页 25 项`;
  $("factorPrev").disabled=factorPage<=1; $("factorNext").disabled=factorPage>=pages;
}
["factorCategory","factorOrigin","factorPackage","factorReadiness"].forEach(id=>$(id).onchange=()=>{factorPage=1;renderFactors();});
$("factorPrev").onclick=()=>{factorPage--;renderFactors();};
$("factorNext").onclick=()=>{factorPage++;renderFactors();};

document.body.onclick=e=>{
  const intradayToggle=e.target.closest("[data-intraday-toggle]");if(intradayToggle){toggleIntradayObservation(intradayToggle.dataset.intradayToggle,intradayToggle.dataset.enabled!=="1");return;}
  const factorChip=e.target.closest("[data-factor-dataset]");if(factorChip){const el=$("factor-dataset-"+factorChip.dataset.factorDataset);if(el)el.scrollIntoView({behavior:"smooth",block:"start"});return;}
  const marketIndex=e.target.closest("[data-market-index]");if(marketIndex){const item=MARKET_INDEXES.find(x=>x.ts_code===marketIndex.dataset.marketIndex);if(item)selectMarketIndex(item);return;}
  const marketModule=e.target.closest("[data-market-module]");if(marketModule){switchMarketModule(marketModule.dataset.marketModule);return;}
  const etfSelect=e.target.closest("[data-etf-select]");if(etfSelect){const item=(state.research.etf.items||[]).find(x=>x.ts_code===etfSelect.dataset.etfSelect);if(item)selectEtf(item);return;}
  const etfFlowWindow=e.target.closest("[data-etf-flow-window]");if(etfFlowWindow){const f=state.research.etf.flow;f.window=Number(etfFlowWindow.dataset.etfFlowWindow);f.selectedDate=null;document.querySelectorAll("[data-etf-flow-window]").forEach(b=>b.classList.toggle("active",b===etfFlowWindow));renderEtfFlowAll();return;}
  const etfFlowClear=e.target.closest("[data-etf-flow-clear]");if(etfFlowClear){state.research.etf.flow.selectedDate=null;renderEtfFlowAll();return;}
  const etfFlowGroup=e.target.closest("[data-etf-flow-group]");if(etfFlowGroup){const f=state.research.etf.flow;const g=etfFlowGroup.dataset.etfFlowGroup;if(g==="__all__"){f.selectedCodes=null;}else{etfToggleGroup(g);}f.selectedDate=null;etfRenderPicker();renderEtfFlowAll();return;}
  const etfFlowMember=e.target.closest("[data-etf-flow-member]");if(etfFlowMember){const f=state.research.etf.flow;etfToggleMember(etfFlowMember.dataset.etfFlowMember);f.selectedDate=null;etfRenderPicker();renderEtfFlowAll();return;}
  const etfFlowSelectAll=e.target.closest("[data-etf-flow-select-all]");if(etfFlowSelectAll){const f=state.research.etf.flow;f.selectedCodes=null;f.selectedDate=null;etfRenderPicker();renderEtfFlowAll();return;}
  const etfFlowClearSel=e.target.closest("[data-etf-flow-clear-selection]");if(etfFlowClearSel){const f=state.research.etf.flow;f.selectedCodes=[];f.selectedDate=null;etfRenderPicker();renderEtfFlowAll();return;}
  const sectorSource=e.target.closest("[data-sector-source]");if(sectorSource){switchSectorSource(sectorSource.dataset.sectorSource);return;}
  const sectorSelect=e.target.closest("[data-sector-select]");if(sectorSelect){const item=(state.research.sector.items||[]).find(x=>x.ts_code===sectorSelect.dataset.sectorSelect);if(item)selectSector(item);return;}
  const sectorMember=e.target.closest("[data-sector-member]");if(sectorMember){jumpToStock(sectorMember.dataset.sectorMember);return;}
  const etfJumpStock=e.target.closest("[data-etf-jump-stock]");if(etfJumpStock){activate("stock");selectStock({ts_code:etfJumpStock.dataset.etfJumpStock,name:etfJumpStock.dataset.etfJumpName,asset_type:"etf"});return;}
  const sourceTasks=e.target.closest("[data-source-tasks]");if(sourceTasks){$("detailDialog").close();$("taskSource").value=sourceTasks.dataset.sourceTasks;$("taskSearch").value="";state.tasks.items=null;activate("tasks");return;}const definitionLink=e.target.closest("[data-task-definition-key]");if(definitionLink){$("detailDialog").close();$("taskSource").value="";$("taskSearch").value=definitionLink.dataset.taskDefinitionKey;state.tasks.items=null;activate("tasks");return;}const subRemove=e.target.closest("[data-sub-remove]");if(subRemove){state.stock.subCharts.splice(Number(subRemove.dataset.subRemove),1);scheduleStockRender();return;}const moduleTab=e.target.closest("[data-stock-module]");if(moduleTab){selectStockModule(moduleTab.dataset.stockModule);return;}const moduleRetry=e.target.closest("[data-stock-module-retry]");if(moduleRetry){selectStockModule(moduleRetry.dataset.stockModuleRetry);return;}const stockPeer=e.target.closest("[data-stock-peer]");if(stockPeer){const item=state.stock.watchlist.find(row=>row.ts_code===stockPeer.dataset.stockPeer);selectStock(item||{ts_code:stockPeer.dataset.stockPeer,name:stockPeer.textContent});return;}const watchRemove=e.target.closest("[data-watch-remove]");if(watchRemove){removeStockWatchlist(watchRemove.dataset.watchRemove);return;}const watchOpen=e.target.closest("[data-watch-open]");if(watchOpen){const item=state.stock.watchlist.find(row=>row.ts_code===watchOpen.dataset.watchOpen);if(item)selectStock(item);return;}const example=e.target.closest("[data-stock-example]");if(example){$("stockSearch").value=example.dataset.stockExample;stockSearch(true);return;}const suggestion=e.target.closest("[data-stock-code]");if(suggestion){const item=($("stockSuggestions")._items||[]).find(row=>row.ts_code===suggestion.dataset.stockCode);if(item)selectStock(item);return;}const timeframe=e.target.closest("[data-stock-timeframe]");if(timeframe){state.stock.timeframe=timeframe.dataset.stockTimeframe;state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();return;}const overlay=e.target.closest("[data-stock-overlay]");if(overlay){const key=overlay.dataset.stockOverlay;state.stock.overlays.has(key)?state.stock.overlays.delete(key):state.stock.overlays.add(key);overlay.classList.toggle("active",state.stock.overlays.has(key));renderStockResearch();return;}const interfaceViewSwitch=e.target.closest("[data-interface-view]");if(interfaceViewSwitch){setInterfaceView(interfaceViewSwitch.dataset.interfaceView);return;}const taskLink=e.target.closest("[data-task-name]");if(taskLink){$("detailDialog").close();$("executionStatus").value="";$("executionTask").value=taskLink.dataset.taskName;state.execution={page:1,size:50,before:null,history:[],next:null,total:0};activate("executions");return;}const gotoService=e.target.closest("[data-goto-service]");if(gotoService){$("serviceSearch").value=gotoService.dataset.gotoService;activate("services");return;}const gotoCoverage=e.target.closest("[data-goto-coverage]");if(gotoCoverage){activate("coverage");return;}const stripTile=e.target.closest("[data-strip-source]");if(stripTile){const value=stripTile.dataset.stripSource;const select=$("interfaceSource");select.value=select.value===value?"":value;state.interfaces.page=1;renderInterfaceRows();document.querySelector(".source-mapping")?.scrollIntoView({behavior:"smooth",block:"start"});return;}const derivationRow=e.target.closest("[data-derivation-key]");if(derivationRow){state.derivations.expanded=state.derivations.expanded===derivationRow.dataset.derivationKey?null:derivationRow.dataset.derivationKey;renderDerivationRows();return;}const interfaceRow=e.target.closest(".interface-row");if(interfaceRow){const identity=`${interfaceRow.dataset.interfaceSource}/${interfaceRow.dataset.interfaceKey}`;state.interfaces.expanded=state.interfaces.expanded===identity?null:identity;renderInterfaceRows();return;}const retry=e.target.closest("[data-retry]");if(retry){retryExecution(retry.dataset.retry,retry.dataset.taskKey);return;}const execution=e.target.closest("[data-execution]");if(execution){showExecution(execution.dataset.execution);return;}const task=e.target.closest("[data-task]");if(task){showTask(task.dataset.task);return;}const target=e.target.closest("[data-view-target]");if(target)activate(target.dataset.viewTarget);if(!e.target.closest(".stock-search-box"))$("stockSuggestions").classList.add("hidden");};
$("sidebarToggle").onclick=()=>{const collapsed=$("sidebar").classList.toggle("collapsed");localStorage.setItem("cq-sidebar",collapsed?"collapsed":"expanded");}; $("themeToggle").onclick=()=>{document.body.classList.toggle("dark");localStorage.setItem("cq-theme",document.body.classList.contains("dark")?"dark":"light");if(state.stock.response)renderStockResearch();};
$("intradayRun").onclick=runIntradayNow;
$("stockAddSubChart").onclick=()=>{if(state.stock.subCharts.length<3){state.stock.subCharts.push("macd");scheduleStockRender();}};
$("refreshButton").onclick=()=>refresh(); $("etfSearch").oninput=renderEtfRows; $("sectorSearch").oninput=renderSectorRows; $("stockSearchButton").onclick=()=>stockSearch(true); $("stockSearch").onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();stockSearch(true);}}; $("stockSearch").oninput=()=>{clearTimeout(state.stock.searchTimer);state.stock.searchTimer=setTimeout(()=>stockSearch(false),220);}; $("stockWatchToggle").onclick=toggleStockWatchlist; $("stockReload").onclick=fetchStockResearch; $("stockPoints").onchange=()=>{state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();}; $("stockZoomIn").onclick=()=>zoomStockChart(1); $("stockZoomOut").onclick=()=>zoomStockChart(-1); $("stockZoomReset").onclick=()=>{state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();}; $("stockPanPrev").onclick=()=>panStockChart(-1); $("stockPanNext").onclick=()=>panStockChart(1); $("stockPan").oninput=e=>{state.stock.viewport.start=Number(e.target.value)||0;state.stock.selectedTradeDate=null;scheduleStockRender();}; $("stockPriceChart").addEventListener("wheel",e=>{if(!(e.ctrlKey||e.metaKey)||!state.stock.response)return;e.preventDefault();const rect=e.currentTarget.getBoundingClientRect(),anchor=(e.clientX-rect.left)/Math.max(rect.width,1);zoomStockChart(e.deltaY<0?1:-1,anchor);},{passive:false});
const stockStage=$("stockChartStage");stockStage.onpointerdown=e=>{if(!state.stock.response||e.button!==0)return;const drag=state.stock.drag;drag.active=true;drag.moved=false;drag.startX=e.clientX;drag.startIndex=state.stock.viewport.start;drag.pointerId=e.pointerId;stockStage.setPointerCapture?.(e.pointerId);stockStage.classList.add("dragging");};stockStage.onpointermove=e=>{const drag=state.stock.drag;if(!drag.active||drag.pointerId!==e.pointerId)return;const delta=e.clientX-drag.startX;if(Math.abs(delta)<4)return;drag.moved=true;const bars=Math.round(delta/Math.max(stockStage.clientWidth,1)*state.stock.viewport.count),maxStart=Math.max(0,state.stock.viewport.total-state.stock.viewport.count),next=Math.max(0,Math.min(maxStart,drag.startIndex-bars));if(next!==state.stock.viewport.start){state.stock.viewport.start=next;state.stock.selectedTradeDate=null;scheduleStockRender();}};const finishStockDrag=e=>{const drag=state.stock.drag;if(!drag.active||drag.pointerId!==e.pointerId)return;drag.active=false;stockStage.releasePointerCapture?.(e.pointerId);stockStage.classList.remove("dragging");setTimeout(()=>{drag.moved=false;},0);};stockStage.onpointerup=finishStockDrag;stockStage.onpointercancel=finishStockDrag;
$("todayDate").onchange=loadToday; $("factorSearch").oninput=renderFactors; $("factorSearch").onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();renderFactors();}}; $("todayQuery").onclick=()=>{state.today.page=1;renderTodayRows();}; $("todaySearch").onkeydown=e=>{if(e.key==="Enter"){state.today.page=1;renderTodayRows();}}; $("taskQuery").onclick=()=>loadTasks(true); $("taskSearch").onkeydown=e=>{if(e.key==="Enter"){state.tasks.page=1;renderTaskRows();}}; $("executionQuery").onclick=()=>loadExecutions(true); $("calendarMonth").onchange=loadCalendar; $("calendarDetailQuery").onclick=()=>{state.calendar.page=1;renderCalendarDetail();}; $("calendarDetailSearch").onkeydown=e=>{if(e.key==="Enter"){state.calendar.page=1;renderCalendarDetail();}}; $("auditAll").onclick=auditAll; $("initStartButton").onclick=startInitialization; $("interfaceQuery").onclick=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceSearch").onkeydown=e=>{if(e.key==="Enter"){state.interfaces.page=1;renderInterfaceRows();}}; $("interfaceSource").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceAssetClass").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceStatus").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceCategory").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceCadence").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("lineageQuery").onclick=()=>{state.interfaces.lineagePage=1;renderFieldLineage();}; $("lineageSearch").onkeydown=e=>{if(e.key==="Enter"){state.interfaces.lineagePage=1;renderFieldLineage();}}; $("serviceQuery").onclick=()=>loadServices(true); $("serviceLayer").onchange=()=>{state.services.page=1;renderServiceRows();}; $("serviceCategory").onchange=()=>{state.services.page=1;renderServiceRows();}; $("serviceSearch").onkeydown=e=>{if(e.key==="Enter"){state.services.page=1;renderServiceRows();}}; $("investmentMonth").onchange=loadInvestment; $("detailClose").onclick=()=>$("detailDialog").close();
$("todayPrev").onclick=()=>{if(state.today.page>1){state.today.page--;renderTodayRows();}};$("todayNext").onclick=()=>{state.today.page++;renderTodayRows();};
$("executionPrev").onclick=()=>{if(state.execution.page===1)return;state.execution.before=state.execution.history.pop()||null;state.execution.page--;loadExecutions()};$("executionNext").onclick=()=>{if(!state.execution.next)return;state.execution.history.push(state.execution.before);state.execution.before=state.execution.next;state.execution.page++;loadExecutions()};
$("taskPrev").onclick=()=>{if(state.tasks.page>1){state.tasks.page--;renderTaskRows();}};$("taskNext").onclick=()=>{state.tasks.page++;renderTaskRows();};
$("calendarDetailPrev").onclick=()=>{if(state.calendar.page>1){state.calendar.page--;renderCalendarDetail();}};$("calendarDetailNext").onclick=()=>{state.calendar.page++;renderCalendarDetail();};
$("servicePrev").onclick=()=>{if(state.services.page>1){state.services.page--;loadServices();}};$("serviceNext").onclick=()=>{state.services.page++;loadServices();};
$("interfacePrev").onclick=()=>{if(state.interfaces.page>1){state.interfaces.page--;renderInterfaceRows();}};$("interfaceNext").onclick=()=>{state.interfaces.page++;renderInterfaceRows();};
$("lineagePrev").onclick=()=>{if(state.interfaces.lineagePage>1){state.interfaces.lineagePage--;renderFieldLineage();}};$("lineageNext").onclick=()=>{state.interfaces.lineagePage++;renderFieldLineage();};
$("derivationPrev").onclick=()=>{if(state.derivations.page>1){state.derivations.page--;renderDerivationRows();}};$("derivationNext").onclick=()=>{state.derivations.page++;renderDerivationRows();};
$("ondemandPrev").onclick=()=>{if(state.derivations.ondemandPage>1){state.derivations.ondemandPage--;renderOndemandRows();}};$("ondemandNext").onclick=()=>{state.derivations.ondemandPage++;renderOndemandRows();};
$("todayDate").value=isoDate(new Date());$("calendarMonth").value=monthValue();$("investmentMonth").value=monthValue();$("initEnd").value=isoDate(new Date(Date.now()-86400000));if(localStorage.getItem("cq-theme")==="dark")document.body.classList.add("dark");if(localStorage.getItem("cq-sidebar")==="collapsed")$("sidebar").classList.add("collapsed");activate(pageFromURL(),false);setInterval(()=>refresh({background:true}),30000);document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh({background:true});});

// Daily index and sector overlay controls use backend-calculated Xiongmen values.
document.addEventListener("click",event=>{
  const button=event.target.closest("[data-research-overlay]");if(!button)return;
  const prefix=button.dataset.researchPrefix,view=state.research[prefix];if(!view)return;
  view.overlays??=new Set();const key=button.dataset.researchOverlay;
  view.overlays.has(key)?view.overlays.delete(key):view.overlays.add(key);
  button.classList.toggle("active",view.overlays.has(key));
  renderResearchChart(prefix,view.response?.data?.timeframes?.["1d"]?.chart?.points||[]);
});
