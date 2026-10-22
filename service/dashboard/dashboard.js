const $ = (id) => document.getElementById(id);
const state = { execution: { page: 1, size: 50, before: null, history: [], next: null, total: 0 }, tasks: { page: 1, size: 30, items: null }, today: { page: 1, size: 20, items: [] }, calendar: { page: 1, size: 20, items: [], issues: new Map(), day: null }, services: { page: 1, size: 20, items: null }, interfaces: { page: 1, size: 50, items: null, runtimeAvailable: true, viewMode: "table", expanded: null, detailCache: new Map(), lineage: null, lineagePage: 1, lineageSize: 15 }, derivations: { items: null, runtimeAvailable: true, coverageAvailable: true, summary: null, expanded: null, page: 1, size: 20, ondemand: null, ondemandPage: 1, ondemandSize: 20 }, stock: { selected: null, response: null, timeframe: "1d", overlays: new Set(["ma_20","ma_60","cost_20","cost_60","niumen_line","niumen_confirmation_line"]), viewport: { timeframe: null, total: 0, start: 0, count: 0 }, selectedTradeDate: null, searchTimer: null, watchlist: [], watchlistLoaded: false, watchlistBusy: false, requestVersion: 0, module: "market", modules: {}, moduleBusy: {}, drag: { active: false, moved: false, startX: 0, startIndex: 0, pointerId: null } }, initId: null };
const labels = {queued:"排队",running:"运行",retrying:"重试",validating:"校验",publishing:"发布",success:"成功",attention:"需处理",historical_attention:"历史失败",superseded:"已被后续成功替代",cancelled:"已取消",not_dispatched:"未派发",not_due:"尚未到调度或发布时间",not_expected:"非交易日无需执行",complete:"完整",empty_verified:"已验证为空",gaps:"缺失",partial:"不完整",indeterminate:"待确认",ready:"严格就绪",ready_after_repair:"补采恢复",active:"进行中",waiting_upstream:"等待上游",operator_action_required:"需要处理",present:"审计通过",observed_only:"已有数据",missing:"缺失",pending:"待核验",acquisition:"原生采集",transformation:"派生计算",draft:"草稿",retired:"已停用"};
const fmt = (v) => Number(v || 0).toLocaleString();
const esc = (v) => String(v ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pill = (v) => `<span class="pill ${esc(v)}">${esc(labels[v] || v)}</span>`;
const isoDate = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const monthValue = (d=new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;

async function api(path, options={}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try { const body = await response.json(); message = body.error?.message || body.detail || message; } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}
function notice(message) { $("notice").textContent=message; $("notice").classList.toggle("hidden",!message); }
function activate(name) {
  document.querySelectorAll("[data-panel]").forEach(x=>x.classList.toggle("hidden",x.dataset.panel!==name));
  document.querySelectorAll(".nav").forEach(x=>x.classList.toggle("active",x.dataset.view===name));
  const names={overview:"数据运营总览",today:"今日交付",stock:"个股研究",tasks:"采集任务",executions:"执行历史",calendar:"数据日历",coverage:"覆盖审计",initialization:"数据初始化",sources:"数据依赖",derivations:"数据派生",services:"对外服务目录",investment:"投资日历"};
  $("pageTitle").textContent=names[name];
  ({today:loadToday,stock:loadStockResearch,tasks:loadTasks,executions:loadExecutions,calendar:loadCalendar,coverage:loadCoverage,initialization:loadInitialization,sources:loadSources,derivations:loadDerivations,services:loadServices,investment:loadInvestment}[name]||(()=>{}))();
}

async function loadOverview() {
  const system = await api("/api/v1/system/overview");
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
  $("issueList").innerHTML=health.issues.length?health.issues.map(x=>{
    const ratio=x.completeness_ratio==null?"—":`${Math.round(x.completeness_ratio*1000)/10}%`;
    const quantityLabel=x.kind==="historical_coverage_gap"?"历史周期覆盖":"实体完整度";
    const quantity=x.expected_count==null?"":`<span>${quantityLabel} ${fmt(x.actual_count)} / ${fmt(x.expected_count)}（${ratio}）</span>`;
    const next=x.next_automatic_repair_at?`<span>下次自动复查 ${new Date(x.next_automatic_repair_at).toLocaleString("zh-CN",{hour12:false})}</span>`:"";
    const explanation=x.action||(x.resolution_state==="waiting_upstream"?"最近一次采集已成功，但上游尚未发布完整截面；系统会按限定范围自动复查。":"数据校验未通过，需要检查来源执行并做范围补采。");
    const coverageAction=x.kind==="historical_coverage_gap"?'<button data-view-target="coverage">查看覆盖审计</button>':"";
    return `<div class="issue ${x.severity}"><div><div class="issue-title"><strong>${esc(x.dataset)}</strong>${pill(x.resolution_state)}<span>${esc(x.observation_key)}</span></div><div class="issue-meta"><span>${esc(explanation)}</span>${quantity}${next}</div></div><div class="issue-actions">${x.source_execution_id?`<button data-execution="${x.source_execution_id}">查看最近尝试</button>`:""}${coverageAction}</div></div>`;
  }).join(""):'<div class="empty-state">最新交付没有问题；全历史覆盖义务以“覆盖审计”为准。</div>';
  $("updatedAt").textContent=`更新于 ${new Date(health.generated_at).toLocaleTimeString("zh-CN")}`;
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
  $("todaySummary").textContent=!view.trade_day?`${day} 为非交易日：日常交易任务不创建执行实例，因此这里为空；trade_calendar 等日历型数据可能已由此前快照覆盖，请在“数据日历”查看数据证据。系统共有 ${s.configured_daily_tasks||0} 个日频任务定义。`:`${day} 数据交付：严格就绪 ${s.strictly_ready}/${s.expected} 个已到期任务；${s.recovered||0} 个由后续补采恢复；${s.not_due||0} 个任务尚未到调度或发布时间。任务行现在同时展示其输出数据集。`;
  state.today.items=view.items;state.today.page=1;renderTodayRows();
}

function renderTaskRows(){
  const query=$("taskSearch").value.trim().toLowerCase();
  const items=(state.tasks.items||[]).filter(x=>!query||[x.task_key,...(x.input_datasets||[]),...(x.output_datasets||[])].join(" ").toLowerCase().includes(query));
  const pages=Math.max(1,Math.ceil(items.length/state.tasks.size));state.tasks.page=Math.min(state.tasks.page,pages);const start=(state.tasks.page-1)*state.tasks.size,rows=items.slice(start,start+state.tasks.size);
  const chips=v=>{const a=v||[];return a.length?`${a.slice(0,4).map(x=>`<span class="dataset-chip">${esc(x)}</span>`).join("")}${a.length>4?`<span class="dataset-more">+${a.length-4}</span>`:""}`:"<span class=\"muted\">无</span>"};
  const lifecycleLabels={active:"已启用",draft:"草稿",retired:"已停用"};
  const cadenceLabels={daily:"每日",weekly:"每周",monthly:"每月",quarterly:"每季",dependency:"依赖触发",manual:"按需"};
  $("taskRows").innerHTML=rows.map(x=>`<tr><td><strong class="task-name">${esc(x.task_key)}</strong><small><span class="pill ${esc(x.lifecycle_status)}">${esc(lifecycleLabels[x.lifecycle_status]||x.lifecycle_status)}</span></small></td><td><span class="cadence-pill">${esc(cadenceLabels[x.cadence]||x.cadence||"按需")}</span><small>${esc(x.schedule_expression||x.schedule_mode||"手动 / 依赖触发")}</small></td><td>${pill(x.workflow_kind)}<small>版本 ${x.version}</small></td><td><div class="dataset-flow"><div><b>输入</b>${chips(x.input_datasets)}</div><span>→</span><div><b>输出</b>${chips(x.output_datasets)}</div></div></td><td><strong>${fmt(x.node_count)}</strong><small>个内部节点</small></td><td><button data-task="${x.task_definition_id}">查看节点</button></td></tr>`).join("")||'<tr><td colspan="6" class="empty-row">没有匹配任务</td></tr>';
  $("taskResultCount").textContent=`筛选结果 ${items.length} 个任务`;
  $("taskPage").textContent=`第 ${state.tasks.page} / ${pages} 页 · ${items.length} 个任务`;$("taskPrev").disabled=state.tasks.page===1;$("taskNext").disabled=state.tasks.page===pages;
}
async function loadTasks(reset=false){if(reset)state.tasks={page:1,size:30,items:null};if(!state.tasks.items){const p=new URLSearchParams({limit:"200"});if($("taskCadence").value)p.set("cadence",$("taskCadence").value);if($("taskKind").value)p.set("workflow_kind",$("taskKind").value);if($("taskLifecycle").value)p.set("lifecycle_status",$("taskLifecycle").value);const view=await api(`/api/v1/ops/tasks?${p}`);state.tasks.items=view.items;}renderTaskRows();}

async function loadExecutions(reset=false) {
  if(reset) state.execution={page:1,size:50,before:null,history:[],next:null,total:0};
  const p=new URLSearchParams({limit:String(state.execution.size)}); if(state.execution.before)p.set("before_id",state.execution.before); if($("executionStatus").value)p.set("status",$("executionStatus").value); if($("executionTask").value.trim())p.set("task_key",$("executionTask").value.trim());
  const view=await api(`/api/v1/ops/executions?${p}`); state.execution.next=view.page.next_cursor;state.execution.total=Number(view.page.total||0);
  $("executionRows").innerHTML=view.items.map(x=>{const r=x.resolution||{},displayStatus=x.status==="attention"&&x.is_current_scope_execution===false?"historical_attention":r.resolution_state||x.status,latest=r.latest_execution_id?`<button data-execution="${r.latest_execution_id}">最新实例</button>`:"",definition=r.action==="fix_definition"?`<button data-task="${x.task_definition_id}">查看任务</button>`:"";return `<tr><td>#${x.task_execution_id}</td><td><strong>${esc(x.task_key)}</strong><small>版本 ${x.definition_version}</small></td><td>${esc(x.purpose)}</td><td>${esc(x.observation_key)}<small>${esc(x.observation_start)} → ${esc(x.observation_end)}</small></td><td>${pill(displayStatus)}<small>${esc(x.current_node_key)}</small></td><td>${fmt(x.attempt_count)}/${fmt(x.max_attempts)}</td><td>${fmt(x.rows_fetched)} / ${fmt(x.rows_written)}</td><td><strong>${esc(r.action==="wait_upstream"?"系统自动复查":x.final_error_category||"—")}</strong><small>${esc(r.guidance||"查看运行详情")}</small></td><td class="row-actions"><button data-execution="${x.task_execution_id}">详情</button>${latest}${definition}${r.retryable?`<button class="danger" data-retry="${x.task_execution_id}" data-task-key="${esc(x.task_key)}">重试</button>`:""}</td></tr>`}).join("")||'<tr><td colspan="9">没有匹配实例</td></tr>';
  const start=state.execution.total?((state.execution.page-1)*state.execution.size)+1:0,end=Math.min(state.execution.page*state.execution.size,state.execution.total);
  $("executionPage").textContent=`第 ${state.execution.page} 页 · ${fmt(start)}–${fmt(end)} / 共 ${fmt(state.execution.total)} 条`; $("executionPrev").disabled=state.execution.page===1; $("executionNext").disabled=!state.execution.next;
}
async function showExecution(id){const view=await api(`/api/v1/ops/executions/${id}`),x=view.execution,r=x.resolution||{};$("detailTitle").textContent=`执行实例 #${id}`;const eventLabels={"node.condition.completed":"执行条件已确认","node.scope_plan.completed":"采集范围已确定","node.acquire.started":"开始采集","node.acquire.request_completed":"上游请求已完成","node.acquire.completed":"数据采集已完成","node.validate.completed":"数据校验已完成","dataset.validation.completed":"完整性证据已保存","dataset.state.updated":"数据状态已发布"};const events=(view.events||[]).map(e=>`<li><b>${esc(eventLabels[e.event_type]||e.event_type)}</b><span>${esc(e.node_key||"")} · ${new Date(e.occurred_at).toLocaleString("zh-CN",{hour12:false})}</span></li>`).join("");const nodeOrder=["condition","scope_plan","acquire","transform","validate","publish"],nodes=Object.entries(x.node_status||{}).sort((a,b)=>nodeOrder.indexOf(a[0])-nodeOrder.indexOf(b[0])).map(([key,value],i)=>`<article><span>${i+1}</span><div><strong>${esc(key)}</strong><small>${pill(value)}</small></div></article>`).join("");const issueTitle=r.action==="wait_upstream"?"为何正在等待":"为什么需要处理",status=r.resolution_state||x.status,definition=r.action==="fix_definition"?`<button data-task="${x.task_definition_id}">查看任务定义与节点</button>`:"";$("detailBody").innerHTML=`<div class="detail-grid"><article><small>任务</small><strong>${esc(x.task_key)} · 版本 ${x.definition_version}</strong></article><article><small>业务数据周期</small><strong>${esc(x.observation_start)} → ${esc(x.observation_end)}</strong></article><article><small>状态 / 当前节点</small><strong>${pill(status)} ${esc(x.current_node_key)}</strong></article><article><small>尝试</small><strong>${fmt(x.attempt_count)} / ${fmt(x.max_attempts)}</strong></article></div>${x.status==="attention"?`<div class="resolution"><strong>${issueTitle}</strong><p>${esc(x.final_error_message||x.final_error_category||"未记录明确错误")}</p><strong>下一步</strong><p>${esc(r.guidance)}</p>${definition}${r.retryable?`<button class="primary" data-retry="${id}" data-task-key="${esc(x.task_key)}">确认重试此实例</button>`:""}</div>`:""}<h3>本次执行节点</h3><div class="node-flow compact-flow">${nodes||"暂无节点状态"}</div><h3>证据时间线</h3><ol class="event-list">${events||"<li>暂无事件</li>"}</ol>`;$("detailDialog").showModal();}
async function showTask(id){const view=await api(`/api/v1/ops/tasks/${id}`),t=view.task,d=t.definition||{},nodes=d.nodes||[],lifecycle={active:"已启用",draft:"草稿",retired:"已停用"};$("detailTitle").textContent=`采集任务 · ${t.task_key}`;$("detailBody").innerHTML=`<div class="detail-grid"><article><small>类型 / 版本</small><strong>${esc(labels[t.workflow_kind]||t.workflow_kind)} · ${t.version}</strong></article><article><small>生命周期</small><strong>${esc(lifecycle[t.lifecycle_status]||t.lifecycle_status)}</strong></article><article><small>输入数据集</small><strong>${esc((d.input_datasets||[]).join("、")||"无")}</strong></article><article><small>输出数据集</small><strong>${esc((d.output_datasets||[]).join("、")||"无")}</strong></article></div><h3>内部节点</h3><div class="node-flow">${nodes.map((n,i)=>`<article><span>${i+1}</span><div><strong>${esc(n.key)}</strong><small>${esc(labels[n.kind]||n.kind)} · ${esc(n.handler_key)}</small><p>最多尝试 ${fmt(n.retry?.max_attempts||1)} 次</p></div></article>`).join("")||"暂无节点"}</div>`;$("detailDialog").showModal();}
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

const interfaceStatusLabels={active:"在用",paused:"停采·存量",no_permission:"无权限",not_scheduled:"未启用",realtime_required:"在用·实时",ant_primary:"在用·主供",adapter_pending:"未启用",public_registered:"登记能力"};
const interfaceStatusClass={active:"ready",paused:"pending",no_permission:"attention",not_scheduled:"pending",realtime_required:"ant",ant_primary:"ant",adapter_pending:"pending",public_registered:"info"};
const interfaceSourceLabels={tushare:"Tushare",financial_data:"蚂蚁",chinamoney:"中国货币网",cninfo:"巨潮互动易",sse:"上证e互动",sina:"新浪财经",chinabond:"中债",pboc:"人民银行"};
const assetClassLabels={stock:"股票·A股",hk_stock:"港股",us_stock:"美股",fund:"基金",index_etf:"指数·ETF·板块",bond:"债券",derivatives:"期权·期货",forex:"外汇",macro:"宏观",altdata:"另类数据",info:"资讯·公告",chain:"产业链·关联",quote:"行情快照",factor:"因子库",other:"其他"};
const interfaceCadenceLabels={daily:"每日",weekly:"每周",monthly:"每月",quarterly:"每季",hourly:"每小时",dependency:"依赖触发",manual:"按需",realtime:"实时",on_demand:"按需",on_demand_fallback:"按需回退"};
const equivalenceLabels={tushare_direct:"Tushare 直接等价",tushare_derived:"Tushare 确定性派生",tushare_announcement_parse:"Tushare 公告解析",financial_data_only:"蚂蚁必需"};
const acquisitionLabels={scheduled:"定时采集",realtime:"实时获取",on_demand:"按需获取",none:"不采集"};

async function loadSources(reset=false){
  const summary=await api("/api/v1/data/dependencies/summary").catch(()=>null);
  if(summary){
    const bySource=summary.by_source||{},pubSources=Object.keys(bySource).filter(k=>!["tushare","financial_data"].includes(k));
    $("sourceOverviewSources").textContent=fmt(Object.keys(bySource).length);$("sourceOverviewInterfaces").textContent=fmt(summary.interfaces);$("sourceOverviewDatasets").textContent=fmt(summary.datasets);
    const ts=Number(bySource.tushare||0),ant=Number(bySource.financial_data||0),pub=pubSources.reduce((a,k)=>a+Number(bySource[k]||0),0);
    $("sourceStrip").innerHTML=`<button type="button" class="strip-tile ts" data-strip-source="tushare"><p>Tushare <span>定时落库</span></p><strong>${fmt(ts)} <small>契约 / ${fmt(summary.tasks)} 任务</small></strong></button><button type="button" class="strip-tile ant" data-strip-source="financial_data"><p>蚂蚁 <span>查询穿透</span></p><strong>${fmt(ant)} <small>路由 / 不落业务表</small></strong></button><button type="button" class="strip-tile pub" data-strip-source="public"><p>公开来源 ×${pubSources.length} <span>证据查询</span></p><strong>${fmt(pub)} <small>端点</small></strong></button>`;
  }
  const usage=await api("/api/v1/data/sources/ant_data/usage?limit=20").catch(()=>null);
  if(usage){const u=usage.summary||{},failed=Number(u.failed||0),latestFailed=u.latest_status==="failed";$("financialRequestCount").textContent=fmt(u.requests);$("financialSuccessCount").textContent=fmt(u.successful);$("financialFailureCount").textContent=fmt(failed);$("financialResearchCount").textContent=fmt(usage.research_integration?.route_count);$("financialUsageState").className=`pill ${latestFailed?"attention":"ready"}`;$("financialUsageState").textContent=latestFailed?"最近调用失败":u.latest_status?"最近调用正常":"尚无调用";$("financialUsageSummary").textContent=`${fmt(u.rows)} 行供应商结果 · 24 小时失败 ${fmt(u.failed_last_24h)} 批 · 最近真实请求 ${u.last_requested_at?new Date(u.last_requested_at).toLocaleString("zh-CN",{hour12:false}):"尚无"} · 仅保存请求元数据，不保存原始响应`;$("financialUsageRows").innerHTML=(usage.routes||[]).map(x=>`<tr><td><code class="route-code" title="${esc(x.route)}">${esc(shortRoute(x.route))}</code></td><td>${fmt(x.batches)}</td><td>${fmt(x.completed_batches)}</td><td>${fmt(x.failed_batches)}</td><td>${x.last_requested_at?new Date(x.last_requested_at).toLocaleString("zh-CN",{hour12:false}):"—"}</td></tr>`).join("")||'<tr><td colspan="5" class="empty-row">尚无真实上游请求</td></tr>';}else{$("financialUsageState").className="pill attention";$("financialUsageState").textContent="审计不可用";$("financialUsageSummary").textContent="无法读取蚂蚁请求审计；其他数据源信息不受影响。";$("financialUsageRows").innerHTML='<tr><td colspan="5" class="empty-row">请求审计暂不可用</td></tr>';}
  if(reset){state.interfaces.page=1;state.interfaces.items=null;state.interfaces.expanded=null;state.interfaces.detailCache=new Map();}
  if(!state.interfaces.items){
    const first=await api("/api/v1/data/dependencies/interfaces?page=1&page_size=200");let items=first.items||[];const total=Number(first.total||items.length);
    for(let p=2;p<=Math.min(Math.ceil(total/200),5);p++){const view=await api(`/api/v1/data/dependencies/interfaces?page=${p}&page_size=200`);items=items.concat(view.items||[]);}
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
  let items=(state.interfaces.items||[]).filter(x=>interfaceSourceFilter(x)&&interfaceCadenceFilter(x)&&(!status||x.status===status||(status==="not_scheduled"&&x.status==="adapter_pending"))&&(!category||x.category===category)&&(!assetClass||(x.asset_class||"other")===assetClass)&&(!query||[x.key,shortRoute(x.key),x.title,x.category,...(x.datasets||[]),...(x.tables||[]),...((x.tasks||[]).map(t=>t.task_key))].join(" ").toLowerCase().includes(query)));
  const pages=Math.max(1,Math.ceil(items.length/state.interfaces.size));state.interfaces.page=Math.min(state.interfaces.page,pages);const start=(state.interfaces.page-1)*state.interfaces.size,rows=items.slice(start,start+state.interfaces.size);
  $("interfaceResult").textContent=`当前筛选 ${items.length} / ${(state.interfaces.items||[]).length} 个接口`+(state.interfaces.runtimeAvailable?"":"（运行状态不可用，仅展示契约信息）");
  const datasetChips=(list,emptyText)=>{const a=list||[];return a.length?`${a.slice(0,2).map(v=>`<button class="dataset-chip link" data-goto-service="${esc(v)}" title="在服务目录中查看 ${esc(v)}">${esc(v)}</button>`).join("")}${a.length>2?`<span class="dataset-more">+${a.length-2}</span>`:""}`:`<span class="muted">${emptyText||"—"}</span>`;};
  $("interfaceRows").innerHTML=rows.map(x=>{
    const statusPill=`<span class="pill ${esc(interfaceStatusClass[x.status]||"pending")}">${esc(interfaceStatusLabels[x.status]||x.status)}</span>`;
    const cadence=xCadence(x);
    const taskLinks=x.tasks?.length?x.tasks.map(t=>`<button class="task-link" data-task-name="${esc(t.task_key)}">${esc(t.task_key)}</button>`).join(""):"";
    const taskCell=x.tasks?.length?`${taskLinks}${x.source!=="tushare"?`<span class="acquisition-tag ${esc(x.acquisition_kind)}">${esc(acquisitionLabels[x.acquisition_kind]||x.acquisition_kind)}</span>`:""}`:(x.source==="tushare"?'<span class="muted">未调度</span>':`<span class="acquisition-tag ${esc(x.acquisition_kind)}">${esc(acquisitionLabels[x.acquisition_kind]||x.acquisition_kind)}</span>`);
    const datasetCell=x.source==="financial_data"&&!x.datasets?.length?'<span class="muted">不落业务表</span>':datasetChips(x.datasets);
    const tableCell=x.tables?.length?`<button class="table-code link" data-goto-coverage="${esc(x.tables[0])}" title="在覆盖审计中查看 ${esc(x.tables[0])}">${esc(x.tables[0])}</button>${x.tables.length>1?`<span class="dataset-more">+${x.tables.length-1}</span>`:""}`:(x.source==="financial_data"?'<span class="muted">仅请求证据</span>':'<span class="muted">—</span>');
    const assetCell=`<td><span class="asset-badge" title="资产类型">${esc(assetClassLabels[x.asset_class]||x.asset_class||"其他")}</span></td>`;
    return `<tr class="interface-row" data-interface-source="${esc(x.source)}" data-interface-key="${esc(x.key)}"><td><code class="route-code" title="${esc(x.key)}">${esc(shortRoute(x.key))}</code>${x.title?`<small class="iface-name">${esc(x.title)}</small>`:""}</td>${assetCell}<td>${esc(interfaceSourceLabels[x.source]||x.source)}</td><td>${statusPill}</td><td>${esc(cadence)}</td><td>${taskCell}</td><td>${datasetCell}</td><td>${tableCell}</td><td>${x.field_count==null?"—":fmt(x.field_count)}</td></tr>${state.interfaces.expanded===`${x.source}/${x.key}`?'<tr class="interface-detail-row"><td colspan="9" id="interfaceDetailCell">加载中…</td></tr>':""}`;
  }).join("")||'<tr><td colspan="9" class="empty-row">没有匹配接口</td></tr>';
  $("interfaceTotalHint").textContent=`共 ${fmt(items.length)} 条 · 每行可展开查看字段清单、血缘与运行状态`;
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
  parts.push(`<p class="detail-title"><code class="route-code" title="${esc(x.key)}">${esc(shortRoute(x.key))}</code>${x.title?`<b>${esc(x.title)}</b>`:""}</p>`);
  if(x.description)parts.push(`<p class="detail-desc">${esc(x.description)}</p>`);
  const fieldTable=(fields,title)=>{const rows=(fields||[]).map(f=>`<tr><td style="font-family:var(--font-mono)">${esc(f.name)}</td><td>${esc(f.type||"—")}</td><td>${esc(f.description||"—")}</td></tr>`).join("");return `<div><small class="detail-label">${esc(title)}</small><div class="table-wrap detail-mini"><table><thead><tr><th>字段</th><th>类型</th><th>说明</th></tr></thead><tbody>${rows||'<tr><td colspan="3">无</td></tr>'}</tbody></table></div></div>`;};
  if(x.source==="tushare"){
    const input=(x.input_parameters||[]).map(f=>`<tr><td style="font-family:var(--font-mono)">${esc(f.name)}</td><td>${esc(f.type||"—")}</td><td>${esc(f.required||"—")}</td><td>${esc(f.description||"—")}</td></tr>`).join("");
    parts.push(`<div><small class="detail-label">输入参数</small><div class="table-wrap detail-mini"><table><thead><tr><th>参数</th><th>类型</th><th>必填</th><th>说明</th></tr></thead><tbody>${input||'<tr><td colspan="4">无</td></tr>'}</tbody></table></div></div>`);
    parts.push(fieldTable(x.output_parameters,"可采集字段（输出）"));
    const runtime=x.runtime||{};const exec=runtime.latest_execution;const ready=runtime.ready_datasets==null?null:`${fmt(runtime.ready_datasets)} / ${fmt(runtime.datasets)}`;
    parts.push(`<div class="detail-facts"><small class="detail-label">血缘与运行状态</small><p>实现方式：${esc(x.implementation?.status||"—")}</p>${x.contract_source?`<p>官方契约：<span class="dataset-chip">${esc(x.contract_source)}</span> 字段与数据内容和官方接口一致，采集调度实际调用本端点。</p>`:""}${x.superseded_by?`<p>实际调用：<span class="dataset-chip">${esc(x.superseded_by)}</span> 本条目仅为官方契约登记，未纳入调度。</p>`:""}<p>主任务：${(x.tasks||[]).map(t=>`<b>${esc(t.task_key)}</b>（${esc(interfaceCadenceLabels[t.cadence]||t.cadence||"—")}）`).join("、")||"—"}</p><p>${exec?`最近执行：${pill(exec.status)} · 业务周期 ${esc(exec.observation_start||"—")} → ${exec.observation_end?`<b>${esc(exec.observation_end)}</b>`:"—"}`:"最近执行：暂无实例"}</p><p>${ready?`数据就绪 ${ready} · 最新数据日期 ${runtime.latest_data_date?`<b>${esc(runtime.latest_data_date)}</b>`:"—"}`:"数据就绪状态：—"}${state.interfaces.runtimeAvailable?"":"（运行状态暂不可用）"}</p>${(x.ant_full_equivalence_routes?.length||x.ant_partial_overlap_routes?.length)?`<p>蚂蚁关联：${(x.ant_full_equivalence_routes||[]).map(r=>`<span class="dataset-chip" title="${esc(r)}">${esc(shortRoute(r))}</span>`).join("")}${(x.ant_partial_overlap_routes||[]).length?`<span class="dataset-chip related">${(x.ant_partial_overlap_routes||[]).map(r=>esc(shortRoute(r))).join("、")}</span>`:""}`:""}</p></div>`);
  }else if(x.source==="financial_data"){
    parts.push(fieldTable(Object.entries(x.response_parameters||{}).map(([name,desc])=>({name,description:String(desc).split("|").pop()?.trim()||"",type:String(desc).split("|")[0]?.trim()||""})),"响应字段（供应商原生模型）"));
    const relation=(x.tushare_interfaces||[]).length?x.tushare_interfaces:x.related_tushare_interfaces||[];
    const antTasks=(x.tasks||[]).length?`<p>定时采集：${x.tasks.map(t=>`<b>${esc(t.task_key)}</b>（${esc(interfaceCadenceLabels[t.cadence]||t.cadence||"—")}）`).join("、")} → 表 ${x.tables?.map(v=>`<span class="dataset-chip">${esc(v)}</span>`).join("")||"—"}</p>`:"";
    parts.push(`<div class="detail-facts"><small class="detail-label">供给策略（已合并原「数据能力供给策略」）</small>${antTasks}<p>读取优先级：${x.preferred_read==="local_db_first"?"本地数据库优先":"蚂蚁优先"} · 语义等价：<b>${esc(equivalenceLabels[x.equivalence_class]||x.equivalence_class)}</b>（${esc(x.coverage)}）</p><p>适配器状态：<code>${esc(x.adapter_status||"—")}</code> · 对外口径：${esc(x.public_access)}</p>${relation.length?`<p>${(x.tushare_interfaces||[]).length?"对应":"局部重叠"} Tushare 接口：${relation.map(v=>`<span class="dataset-chip">${esc(v)}</span>`).join("")}</p>`:""}<p class="detail-reason">${esc(x.rationale||x.policy_reason||"")}</p></div>`);
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
  const layer=$("serviceLayer").value,query=$("serviceSearch").value.trim().toLowerCase();let items=state.services.items.filter(x=>(!layer||x.layer_id===layer)&&(!query||[x.name,x.path,...x.local_datasets,...x.upstream_sources].join(" ").toLowerCase().includes(query)));
  const pages=Math.max(1,Math.ceil(items.length/state.services.size));state.services.page=Math.min(state.services.page,pages);const start=(state.services.page-1)*state.services.size,rows=items.slice(start,start+state.services.size);
  $("serviceSummary").textContent=`共 ${items.length} 个匹配的对外 REST 入口；供应商、连接器和权限映射已从本目录移到“数据依赖”。`;
  $("serviceRows").innerHTML=rows.map(x=>{const datasets=x.local_datasets.length?`${x.local_datasets.slice(0,5).map(esc).join("、")}${x.local_datasets.length>5?` 等 ${x.local_datasets.length} 个`:""}`:`动态：${esc(x.dependency_scope)}`;return `<tr><td>${pill(x.layer_id)}<strong>${esc(x.name)}</strong></td><td><code>${esc(x.method)} ${esc(x.path)}</code></td><td>${datasets}</td><td>${esc(x.data_origin)}${x.derivation?`<small>${esc(x.derivation)}</small>`:""}</td><td>${esc(x.read_strategy)}</td></tr>`}).join("")||'<tr><td colspan="5">没有匹配服务</td></tr>';
  $("servicePage").textContent=`第 ${state.services.page} / ${pages} 页`;$('servicePrev').disabled=state.services.page===1;$('serviceNext').disabled=state.services.page===pages;
}

async function loadInvestment(){const month=$("investmentMonth").value||monthValue(),[y,m]=month.split("-").map(Number),start=`${month}-01`,end=isoDate(new Date(y,m,0));const view=await api(`/api/v1/research/investment-calendar?start_date=${start}&end_date=${end}&importance=important`);const events=view.events||view.items||[];const groups={};events.forEach(x=>(groups[String(x.event_date||x.date).slice(0,10)]??=[]).push(x));const rows=Object.entries(groups).map(([event_date,items])=>({event_date,items}));renderMonth("investmentGrid",month,rows,x=>x?`${x.items.length} 个事件`:"无重要事件");$("investmentGrid").onclick=e=>{const b=e.target.closest("[data-date]");if(!b)return;const items=groups[b.dataset.date]||[];$("investmentEvents").innerHTML=items.map(x=>`<div class="issue"><div><strong>${esc(x.event_name||x.name||x.title)}</strong><small>${esc(x.country)} · ${esc(x.event_time||x.time)} · 实际 ${esc(x.actual)}</small></div></div>`).join("")||"<p>当日无重要事件</p>";};}

const stockLineDefinitions={
  ma_5:{label:"MA5",color:"#9b7bd4"},ma_10:{label:"MA10",color:"#d19b3f"},ma_20:{label:"MA20",color:"#348fcb"},ma_60:{label:"MA60",color:"#7b8794"},
  ma_120:{label:"MA120",color:"#4d8d7c"},ma_250:{label:"MA250",color:"#6a7480"},ema_12:{label:"EMA12",color:"#35a78a"},ema_26:{label:"EMA26",color:"#2f6f9f"},ema_20:{label:"EMA20",color:"#35a78a"},ema_50:{label:"EMA50",color:"#2f6f9f"},ema_200:{label:"EMA200",color:"#17666f"},bbi:{label:"BBI",color:"#945ca8"},
  cost_20:{label:"成本20",color:"#b96a93"},cost_60:{label:"成本60",color:"#8753a6"},niumen_line:{label:"牛门线",color:"#e07a35"},niumen_confirmation_line:{label:"确认线",color:"#c94848"},
  niumen_signal_ma_10:{label:"信号MA10",color:"#e7a85c"},bollinger_upper:{label:"BOLL上轨",color:"#8795a1"},bollinger_middle:{label:"BOLL中轨",color:"#a4afb8"},bollinger_lower:{label:"BOLL下轨",color:"#8795a1"},keltner_upper:{label:"KC上轨",color:"#4d91a8"},keltner_middle:{label:"KC中轨",color:"#71aabd"},keltner_lower:{label:"KC下轨",color:"#4d91a8"}
};
const stockNumber=(value,digits=2)=>value==null||Number.isNaN(Number(value))?"—":Number(value).toLocaleString("zh-CN",{minimumFractionDigits:digits,maximumFractionDigits:digits});
const stockPercent=value=>value==null||Number.isNaN(Number(value))?"—":`${Number(value)>=0?"+":""}${stockNumber(value,2)}%`;
const stockStateLabel=value=>({bullish:"多头",bearish:"空头",mixed:"震荡",above_niumen:"站上牛门线",confirmed_breakout:"确认突破",below_niumen:"牛门线下方",normal:"常态",expanding:"放量",contracting:"缩量",accumulation:"价量偏强",distribution:"价量偏弱",neutral:"中性"}[value]||value||"—");
const stockDailyOnlyLines=new Set(["cost_20","cost_60","niumen_line","niumen_confirmation_line","niumen_signal_ma_10"]);
function stockActiveLines(){return [...state.stock.overlays].flatMap(key=>key==="bollinger"?["bollinger_upper","bollinger_middle","bollinger_lower"]:key==="keltner"?["keltner_upper","keltner_middle","keltner_lower"]:[key]).filter(key=>state.stock.timeframe==="1d"||!stockDailyOnlyLines.has(key));}
function stockVolumeScale(value){const number=Number(value)||0;if(Math.abs(number)>=100000000)return {value:number/100000000,unit:"亿手",digits:2};if(Math.abs(number)>=10000)return {value:number/10000,unit:"万手",digits:2};return {value:number,unit:"手",digits:0};}
function stockVolumeText(value,forcedUnit=null){const scale=forcedUnit==="亿手"?{value:(Number(value)||0)/100000000,unit:forcedUnit,digits:2}:forcedUnit==="万手"?{value:(Number(value)||0)/10000,unit:forcedUnit,digits:2}:forcedUnit==="手"?{value:Number(value)||0,unit:forcedUnit,digits:0}:stockVolumeScale(value);return `${stockNumber(scale.value,scale.digits)} ${scale.unit}`;}
function stockVisiblePoints(points){const viewport=state.stock.viewport;if(viewport.timeframe!==state.stock.timeframe||viewport.total!==points.length||!viewport.count){const preferred=Math.max(30,Number($("stockPoints").value)||180);viewport.timeframe=state.stock.timeframe;viewport.total=points.length;viewport.count=Math.min(preferred,points.length);viewport.start=Math.max(0,points.length-viewport.count);}viewport.count=Math.max(Math.min(viewport.count,points.length),Math.min(30,points.length));viewport.start=Math.max(0,Math.min(viewport.start,points.length-viewport.count));return points.slice(viewport.start,viewport.start+viewport.count);}
function updateStockViewportControls(points){const viewport=state.stock.viewport,pan=$("stockPan"),end=Math.min(viewport.start+viewport.count,points.length),maxStart=Math.max(0,points.length-viewport.count),first=points[viewport.start]?.trade_date,last=points[Math.max(viewport.start,end-1)]?.trade_date;pan.max=String(maxStart);pan.value=String(viewport.start);pan.disabled=viewport.count>=points.length;$("stockPanPrev").disabled=viewport.start<=0;$("stockPanNext").disabled=viewport.start>=maxStart;$("stockZoomStatus").textContent=points.length?`${first||"—"} → ${last||"—"} · ${viewport.start+1}–${end}/${points.length}`:"—";$("stockZoomIn").disabled=viewport.count<=Math.min(30,points.length);$("stockZoomOut").disabled=viewport.count>=points.length;$("stockZoomReset").disabled=viewport.start===maxStart&&viewport.count===Math.min(Math.max(30,Number($("stockPoints").value)||180),points.length);}
function zoomStockChart(direction,anchor=.5){const response=state.stock.response,data=response?.data||{},timeframe=data.timeframes?.[state.stock.timeframe];if(!timeframe)return;const points=timeframe.chart?.points||[],viewport=state.stock.viewport;stockVisiblePoints(points);const oldCount=viewport.count,newCount=direction>0?Math.max(30,Math.round(oldCount*.72)):Math.min(points.length,Math.round(oldCount/0.72));if(newCount===oldCount)return;const anchorIndex=viewport.start+oldCount*Math.max(0,Math.min(anchor,1));viewport.count=newCount;viewport.start=Math.round(anchorIndex-newCount*Math.max(0,Math.min(anchor,1)));viewport.start=Math.max(0,Math.min(viewport.start,points.length-newCount));state.stock.selectedTradeDate=null;renderStockResearch();}
function panStockChart(direction){const viewport=state.stock.viewport;if(!viewport.count)return;const maxStart=Math.max(0,viewport.total-viewport.count),step=Math.max(1,Math.round(viewport.count*.55));viewport.start=Math.max(0,Math.min(maxStart,viewport.start+direction*step));state.stock.selectedTradeDate=null;renderStockResearch();}

function stockEnsureMacd(points){
  const ema=(values,period)=>{const factor=2/(period+1),out=[];values.forEach((value,index)=>out.push(index?value*factor+out[index-1]*(1-factor):value));return out;};
  if(points.every(point=>point.macd!=null&&point.macd_signal!=null))return points;
  const closes=points.map(point=>Number(point.close)),fast=ema(closes,12),slow=ema(closes,26),dif=fast.map((value,index)=>value-slow[index]),dea=ema(dif,9);
  return points.map((point,index)=>({...point,macd:dif[index],macd_signal:dea[index],macd_histogram:dif[index]-dea[index]}));
}

function stockPath(points,key,x,y){
  let path="",drawing=false;
  points.forEach((point,index)=>{const value=Number(point[key]);if(!Number.isFinite(value)){drawing=false;return;}path+=`${drawing?"L":"M"}${x(index).toFixed(2)},${y(value).toFixed(2)} `;drawing=true;});
  return path.trim();
}

function renderStockPriceChart(points){
  const svg=$("stockPriceChart"),width=1200,height=430,margin={left:12,right:72,top:15,bottom:28},plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom;
  if(!points.length){svg.innerHTML='<text x="600" y="215" text-anchor="middle" class="axis-label">没有可展示的行情</text>';return;}
  const active=stockActiveLines();
  const values=points.flatMap(point=>[point.high,point.low,...active.map(key=>point[key])]).map(Number).filter(Number.isFinite),rawMin=Math.min(...values),rawMax=Math.max(...values),padding=Math.max((rawMax-rawMin)*.06,rawMax*.005),min=rawMin-padding,max=rawMax+padding;
  const x=index=>margin.left+(index+.5)*plotWidth/points.length,y=value=>margin.top+(max-value)/(max-min)*plotHeight,step=plotWidth/points.length,bodyWidth=Math.max(1.5,Math.min(7,step*.64));
  let markup="";
  for(let tick=0;tick<=5;tick++){const value=max-(max-min)*tick/5,py=margin.top+plotHeight*tick/5;markup+=`<line class="grid-line" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/><text class="axis-label" x="${width-margin.right+8}" y="${py+3}">${stockNumber(value,2)}</text>`;}
  const dateTicks=Math.min(6,points.length);for(let tick=0;tick<dateTicks;tick++){const index=Math.round(tick*(points.length-1)/Math.max(dateTicks-1,1));markup+=`<text class="axis-label" text-anchor="middle" x="${x(index)}" y="${height-7}">${esc(String(points[index].trade_date).slice(5,10))}</text>`;}
  points.forEach((point,index)=>{const opened=Number(point.open),closed=Number(point.close),high=Number(point.high),low=Number(point.low),up=closed>=opened,top=y(Math.max(opened,closed)),bottom=y(Math.min(opened,closed)),bodyHeight=Math.max(1,bottom-top),className=up?"candle-up":"candle-down";markup+=`<line class="${className}" x1="${x(index)}" y1="${y(high)}" x2="${x(index)}" y2="${y(low)}"/><rect class="${className}" x="${x(index)-bodyWidth/2}" y="${top}" width="${bodyWidth}" height="${bodyHeight}"/>`;});
  active.forEach(key=>{const definition=stockLineDefinitions[key],dash=key.startsWith("niumen")?' stroke-dasharray="6 4"':"";markup+=`<path class="factor-line" d="${stockPath(points,key,x,y)}" stroke="${definition.color}"${dash}/>`;});
  markup+=`<g id="stockCrosshair"></g><rect class="hit-area" x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${plotHeight}"/>`;
  svg.innerHTML=markup;
  const hit=svg.querySelector(".hit-area");
  const showPoint=(index,event=null,pinned=false)=>{const point=points[index],px=x(index),py=y(Number(point.close)),rect=svg.getBoundingClientRect();svg.querySelector("#stockCrosshair").innerHTML=`<line class="crosshair" x1="${px}" y1="${margin.top}" x2="${px}" y2="${margin.top+plotHeight}"/><line class="crosshair" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/>`;const factorRows=active.filter(key=>point[key]!=null).map(key=>{const definition=stockLineDefinitions[key];return `<span class="stock-tooltip-factor"><i style="--tip-color:${definition.color}"></i>${esc(definition.label)} ${stockNumber(point[key])}</span>`;}).join("");const tip=$("stockTooltip"),left=event?Math.min(rect.width-285,Math.max(6,event.clientX-rect.left+12)):8,top=event?Math.min(rect.height-Math.max(155,75+active.length*18),Math.max(6,event.clientY-rect.top-55)):8;tip.style.left=`${left}px`;tip.style.top=`${top}px`;tip.innerHTML=`<strong>${esc(point.trade_date)}${pinned?' <small>已选中</small>':''}</strong><div class="stock-tooltip-grid"><span>开 ${stockNumber(point.open)}</span><span>高 ${stockNumber(point.high)}</span><span>低 ${stockNumber(point.low)}</span><span>收 ${stockNumber(point.close)}</span><span>成交量 ${stockVolumeText(point.volume)}</span>${factorRows}</div>`;tip.classList.remove("hidden");};
  const pointerIndex=event=>{const rect=svg.getBoundingClientRect(),relative=(event.clientX-rect.left)/rect.width*width;return Math.max(0,Math.min(points.length-1,Math.floor((relative-margin.left)/plotWidth*points.length)));};
  hit.onpointermove=event=>{if(!state.stock.drag.active)showPoint(pointerIndex(event),event,false);};
  hit.onclick=event=>{if(state.stock.drag.moved)return;const index=pointerIndex(event);state.stock.selectedTradeDate=points[index].trade_date;showPoint(index,event,true);};
  hit.onpointerleave=()=>{const selected=points.findIndex(point=>point.trade_date===state.stock.selectedTradeDate);if(selected>=0)showPoint(selected,null,true);else{svg.querySelector("#stockCrosshair").innerHTML="";$("stockTooltip").classList.add("hidden");}};
  const selected=points.findIndex(point=>point.trade_date===state.stock.selectedTradeDate);if(selected>=0)showPoint(selected,null,true);
}

function renderStockVolumeChart(points){
  const svg=$("stockVolumeChart"),width=1200,height=128,margin={left:5,right:72,top:9,bottom:14},plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom,max=Math.max(...points.map(point=>Number(point.volume)||0),1),unit=stockVolumeScale(max).unit,step=plotWidth/Math.max(points.length,1),barWidth=Math.max(1,Math.min(7,step*.64));let markup=`<line class="grid-line" x1="${margin.left}" y1="${height-margin.bottom}" x2="${width-margin.right}" y2="${height-margin.bottom}"/>`;
  for(let tick=0;tick<=2;tick++){const value=max*(2-tick)/2,py=margin.top+plotHeight*tick/2;markup+=`<line class="grid-line" x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}"/><text class="axis-label" x="${width-margin.right+8}" y="${py+3}">${stockVolumeText(value,unit).replace(` ${unit}`,"")}</text>`;}
  points.forEach((point,index)=>{const value=Number(point.volume)||0,barHeight=value/max*plotHeight,x=margin.left+(index+.5)*step;markup+=`<rect class="${Number(point.close)>=Number(point.open)?"bar-up":"bar-down"}" x="${x-barWidth/2}" y="${height-margin.bottom-barHeight}" width="${barWidth}" height="${Math.max(1,barHeight)}" opacity=".72"/>`;});svg.innerHTML=markup;$("stockVolumeTitle").textContent=`成交量（${unit}）`;
}

function renderStockMacdChart(points){
  const svg=$("stockMacdChart"),width=1200,height=150,margin={left:5,right:72,top:10,bottom:16},plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom,values=points.flatMap(point=>[point.macd,point.macd_signal,point.macd_histogram]).map(Number).filter(Number.isFinite),extent=Math.max(...values.map(Math.abs),.01),y=value=>margin.top+(extent-value)/(2*extent)*plotHeight,x=index=>margin.left+(index+.5)*plotWidth/points.length,zero=y(0),step=plotWidth/Math.max(points.length,1),barWidth=Math.max(1,Math.min(7,step*.58));let markup=`<line class="grid-line" x1="${margin.left}" y1="${zero}" x2="${width-margin.right}" y2="${zero}"/>`;
  points.forEach((point,index)=>{const value=Number(point.macd_histogram)||0,target=y(value);markup+=`<rect class="${value>=0?"macd-positive":"macd-negative"}" x="${x(index)-barWidth/2}" y="${Math.min(zero,target)}" width="${barWidth}" height="${Math.max(1,Math.abs(zero-target))}" opacity=".65"/>`;});
  markup+=`<path class="factor-line" d="${stockPath(points,"macd",x,y)}" stroke="#348fcb"/><path class="factor-line" d="${stockPath(points,"macd_signal",x,y)}" stroke="#d19b3f"/>`;svg.innerHTML=markup;
}

function renderStockFactors(timeframe,points){
  const trend=timeframe.trend||{},momentum=timeframe.momentum||{},volatility=timeframe.volatility||{},strength=timeframe.trend_strength||{},volume=timeframe.volume_price||{},analysis=volume.analysis||{},latest=points.at(-1)||{},previous=points.at(-2)||latest,change=Number(previous.close)?(Number(latest.close)/Number(previous.close)-1)*100:null,niumen=trend.systems?.niumen_breakout||{},niumenValues=niumen.values||{},cost=analysis.transaction_cost_lines?.windows||{};
  $("stockClose").textContent=stockNumber(latest.close);$("stockChange").textContent=stockPercent(change);$("stockChange").className=change>0?"up":change<0?"down":"";$("stockDate").textContent=`${latest.trade_date||"—"} · ${state.stock.timeframe==="1d"?"日线":state.stock.timeframe==="1w"?"周线":"月线"}`;
  $("stockTrend").textContent=stockStateLabel(trend.regime);$("stockTrendDetail").textContent=`MA20 ${stockNumber(trend.moving_averages?.["20"])} · MA60 ${stockNumber(trend.moving_averages?.["60"])}`;
  const histogram=trend.macd!=null&&trend.macd_signal!=null?Number(trend.macd)-Number(trend.macd_signal):null;$("stockMacd").textContent=histogram==null?"—":histogram>=0?"多头动能":"空头动能";$("stockMacdDetail").textContent=`DIF ${stockNumber(trend.macd,3)} · DEA ${stockNumber(trend.macd_signal,3)} · 柱 ${stockNumber(histogram,3)}`;$("stockMacdLabel").textContent=`DIF ${stockNumber(trend.macd,3)} · DEA ${stockNumber(trend.macd_signal,3)}`;
  $("stockRsi").textContent=`RSI ${stockNumber(momentum.rsi_14,1)}`;$("stockKdj").textContent=`K ${stockNumber(momentum.kdj?.k,1)} · D ${stockNumber(momentum.kdj?.d,1)} · J ${stockNumber(momentum.kdj?.j,1)}`;
  if(state.stock.timeframe==="1d"){$("stockCost").textContent=`${stockNumber(cost["20_day"]?.value||latest.cost_20)} / ${stockNumber(cost["60_day"]?.value||latest.cost_60)}`;$("stockCostDistance").textContent=`距20日成本 ${stockPercent(cost["20_day"]?.distance_from_close_pct)} · 距60日成本 ${stockPercent(cost["60_day"]?.distance_from_close_pct)}`;$("stockNiumen").textContent=stockStateLabel(niumen.state);$("stockNiumenDetail").textContent=`牛门 ${stockNumber(niumenValues.niumen_line||latest.niumen_line)} · 确认 ${stockNumber(niumenValues.confirmation_line||latest.niumen_confirmation_line)}`;}else{$("stockCost").textContent="仅日线提供";$("stockCostDistance").textContent="成本线按20/60个交易日滚动计算";$("stockNiumen").textContent="仅日线提供";$("stockNiumenDetail").textContent="牛门线周期固定为交易日，不跨周期套用";}
  const regime=analysis.price_volume_regime||{},boll=volatility.bollinger_20||{},bollWidth=Number(boll.middle)?(Number(boll.upper)-Number(boll.lower))/Number(boll.middle)*100:null,supertrend=trend.systems?.supertrend_10_3||{};$("stockVolumeState").textContent=stockStateLabel(regime.classification||analysis.activity?.state);$("stockVolumeDetail").textContent=`量能 5/20 比 ${stockNumber(volume.volume_5_to_20_ratio,2)} · 最新 ${stockVolumeText(latest.volume)}`;$("stockVolumeLabel").textContent=`最新 ${stockVolumeText(latest.volume)} · 5/20 ${stockNumber(volume.volume_5_to_20_ratio,2)}`;
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

const stockModulePanels={market:"stockModuleMarket",chips:"stockModuleChips",fundamentals:"stockModuleFundamentals",events:"stockModuleEvents",sectors:"stockModuleSectors",chain:"stockModuleChain"};
const stockModuleEndpoints={chips:"chips",fundamentals:"fundamentals?periods=8&include_external=true",events:"events",sectors:"sector-context",chain:"industry-chain"};
function stockSelectedCode(){return state.stock.selected?.ts_code||state.stock.selected?.code;}
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
    const response=await api(`/api/v1/research/stocks/${encodeURIComponent(code)}/${stockModuleEndpoints[name]}`);
    if(stockSelectedCode()!==code)return;
    state.stock.modules[key]=response;
    renderStockModule(name,response);
  }catch(error){panel.innerHTML=`<div class="module-loading">加载失败：${esc(error.message)}（<button class="task-link" data-stock-module-retry="${esc(name)}">重试</button>）</div>`;}
  finally{delete state.stock.moduleBusy[key];}
}
function resetStockModules(){
  state.stock.modules={};state.stock.moduleBusy={};state.stock.module="market";
  document.querySelectorAll("[data-stock-module]").forEach(button=>button.classList.toggle("active",button.dataset.stockModule==="market"));
  Object.entries(stockModulePanels).forEach(([name,id])=>{const panel=$(id);if(!panel)return;if(name==="market"){panel.classList.remove("hidden");return;}panel.classList.add("hidden");panel.innerHTML="";});
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
  const response=state.stock.response;if(!response)return;const data=response.data||{},timeframe=data.timeframes?.[state.stock.timeframe];if(!timeframe)return;const allPoints=stockEnsureMacd(timeframe.chart?.points||[]),points=stockVisiblePoints(allPoints),instrument={...(data.instrument||{}),...(state.stock.selected||{})},quality=response.meta?.quality||{};
  $("stockEmpty").classList.add("hidden");$("stockWorkspace").classList.remove("hidden");$("stockName").textContent=instrument.name||instrument.fullname||instrument.ts_code||"未知股票";$("stockCode").textContent=instrument.ts_code||response.meta?.ts_code||"—";$("stockAvatar").textContent=(instrument.name||"股").slice(0,1);$("stockMeta").textContent=[instrument.industry,instrument.market,instrument.exchange].filter(Boolean).join(" · ")||"A股";$("stockQuality").className=`pill ${quality.status==="ready"?"ready":"attention"}`;$("stockQuality").textContent=quality.status==="ready"?"数据已核验":"数据有提示";
  renderStockWatchlist();document.querySelectorAll("[data-stock-timeframe]").forEach(button=>button.classList.toggle("active",button.dataset.stockTimeframe===state.stock.timeframe));document.querySelectorAll(".daily-only").forEach(button=>button.classList.toggle("disabled",state.stock.timeframe!=="1d"));$("stockDailyNote").classList.toggle("hidden",state.stock.timeframe!=="1d");const loadedFirst=allPoints[0]?.trade_date,loadedLast=allPoints.at(-1)?.trade_date,history=response.meta?.history||{},isDaily=state.stock.timeframe==="1d",truncated=isDaily&&history.truncated;$("stockHistoryRange").textContent=allPoints.length?`已加载 ${loadedFirst} → ${loadedLast} · ${allPoints.length} 根${truncated?" · 已达接口上限":" · 完整历史"}`:"没有可展示的历史行情";
  updateStockViewportControls(allPoints);renderStockPriceChart(points);renderStockVolumeChart(points);renderStockMacdChart(points);renderStockFactors(timeframe,allPoints);
}

async function fetchStockResearch(){
  if(!state.stock.selected)return;const code=state.stock.selected.ts_code||state.stock.selected.code,requestVersion=++state.stock.requestVersion;notice("");$("stockWorkspace").classList.add("stock-loading");try{const response=await api(`/api/v1/research/stocks/${encodeURIComponent(code)}/technicals?lookback_days=3000&chart_points=1500&include_external=false&include_realtime=false`);if(requestVersion!==state.stock.requestVersion||(state.stock.selected?.ts_code||state.stock.selected?.code)!==code)return;state.stock.response=response;state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();}catch(error){if(requestVersion===state.stock.requestVersion)notice(`个股研究加载失败：${error.message}`);}finally{if(requestVersion===state.stock.requestVersion)$("stockWorkspace").classList.remove("stock-loading");}
}

async function stockSearch(selectFirst=false){
  const query=$("stockSearch").value.trim(),suggestions=$("stockSuggestions");if(!query){suggestions.classList.add("hidden");return;}try{const result=await api(`/api/v1/research/stocks/search?${new URLSearchParams({q:query,limit:"12"})}`),items=result.data||[];if(selectFirst&&items.length){selectStock(items[0]);return;}suggestions.innerHTML=items.map(item=>`<button class="stock-suggestion" data-stock-code="${esc(item.ts_code)}"><span><strong>${esc(item.name||item.fullname)}</strong><small>${esc(item.industry||item.market||"A股")} · ${item.list_status==="L"?"上市":"历史证券"}</small></span><code>${esc(item.ts_code)}</code></button>`).join("")||'<div class="empty-state">没有找到匹配股票</div>';suggestions._items=items;suggestions.classList.remove("hidden");}catch(error){notice(`股票搜索失败：${error.message}`);}
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
  $("stockAvatar").textContent=(item.name||item.fullname||"股").slice(0,1);
  $("stockMeta").textContent=[item.industry,item.market,item.exchange].filter(Boolean).join(" · ")||"A股";
  $("stockQuality").className="pill pending";
  $("stockQuality").textContent="加载中";
  $("stockClose").textContent="加载中";
  $("stockChange").textContent="—";
  $("stockChange").className="";
  $("stockDate").textContent="正在读取长历史行情";
  ["stockPriceChart","stockVolumeChart","stockMacdChart"].forEach(id=>$(id).replaceChildren());
  [
    "stockTrend","stockTrendDetail","stockMacd","stockMacdDetail","stockMacdLabel",
    "stockRsi","stockKdj","stockCost","stockCostDistance","stockNiumen","stockNiumenDetail",
    "stockVolumeState","stockVolumeDetail","stockVolumeLabel","stockVolatility",
    "stockVolatilityDetail","stockStrength","stockStrengthDetail","stockMoneyFlow",
    "stockMoneyFlowDetail"
  ].forEach(id=>$(id).textContent="—");
  $("stockVolumeTitle").textContent="成交量";
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

async function refresh(){notice("");try{await loadOverview();const active=document.querySelector(".nav.active")?.dataset.view;if(active&&active!=="overview")await ({today:loadToday,stock:loadStockResearch,tasks:loadTasks,executions:loadExecutions,calendar:loadCalendar,coverage:loadCoverage,initialization:loadInitialization,sources:loadSources,services:loadServices,investment:loadInvestment}[active]||(()=>{}))();}catch(e){notice(`加载失败：${e.message}`);}}

document.querySelector("nav").onclick=e=>{const b=e.target.closest("[data-view]");if(b)activate(b.dataset.view)};
document.body.onclick=e=>{const moduleTab=e.target.closest("[data-stock-module]");if(moduleTab){selectStockModule(moduleTab.dataset.stockModule);return;}const moduleRetry=e.target.closest("[data-stock-module-retry]");if(moduleRetry){selectStockModule(moduleRetry.dataset.stockModuleRetry);return;}const stockPeer=e.target.closest("[data-stock-peer]");if(stockPeer){const item=state.stock.watchlist.find(row=>row.ts_code===stockPeer.dataset.stockPeer);selectStock(item||{ts_code:stockPeer.dataset.stockPeer,name:stockPeer.textContent});return;}const watchRemove=e.target.closest("[data-watch-remove]");if(watchRemove){removeStockWatchlist(watchRemove.dataset.watchRemove);return;}const watchOpen=e.target.closest("[data-watch-open]");if(watchOpen){const item=state.stock.watchlist.find(row=>row.ts_code===watchOpen.dataset.watchOpen);if(item)selectStock(item);return;}const example=e.target.closest("[data-stock-example]");if(example){$("stockSearch").value=example.dataset.stockExample;stockSearch(true);return;}const suggestion=e.target.closest("[data-stock-code]");if(suggestion){const item=($("stockSuggestions")._items||[]).find(row=>row.ts_code===suggestion.dataset.stockCode);if(item)selectStock(item);return;}const timeframe=e.target.closest("[data-stock-timeframe]");if(timeframe){state.stock.timeframe=timeframe.dataset.stockTimeframe;state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();return;}const overlay=e.target.closest("[data-stock-overlay]");if(overlay){const key=overlay.dataset.stockOverlay;state.stock.overlays.has(key)?state.stock.overlays.delete(key):state.stock.overlays.add(key);overlay.classList.toggle("active",state.stock.overlays.has(key));renderStockResearch();return;}const interfaceViewSwitch=e.target.closest("[data-interface-view]");if(interfaceViewSwitch){setInterfaceView(interfaceViewSwitch.dataset.interfaceView);return;}const taskLink=e.target.closest("[data-task-name]");if(taskLink){$("executionTask").value=taskLink.dataset.taskName;activate("executions");return;}const gotoService=e.target.closest("[data-goto-service]");if(gotoService){$("serviceSearch").value=gotoService.dataset.gotoService;activate("services");return;}const gotoCoverage=e.target.closest("[data-goto-coverage]");if(gotoCoverage){activate("coverage");return;}const stripTile=e.target.closest("[data-strip-source]");if(stripTile){const value=stripTile.dataset.stripSource;const select=$("interfaceSource");select.value=select.value===value?"":value;state.interfaces.page=1;renderInterfaceRows();document.querySelector(".source-mapping")?.scrollIntoView({behavior:"smooth",block:"start"});return;}const derivationRow=e.target.closest("[data-derivation-key]");if(derivationRow){state.derivations.expanded=state.derivations.expanded===derivationRow.dataset.derivationKey?null:derivationRow.dataset.derivationKey;renderDerivationRows();return;}const interfaceRow=e.target.closest(".interface-row");if(interfaceRow){const identity=`${interfaceRow.dataset.interfaceSource}/${interfaceRow.dataset.interfaceKey}`;state.interfaces.expanded=state.interfaces.expanded===identity?null:identity;renderInterfaceRows();return;}const retry=e.target.closest("[data-retry]");if(retry){retryExecution(retry.dataset.retry,retry.dataset.taskKey);return;}const execution=e.target.closest("[data-execution]");if(execution){showExecution(execution.dataset.execution);return;}const task=e.target.closest("[data-task]");if(task){showTask(task.dataset.task);return;}const target=e.target.closest("[data-view-target]");if(target)activate(target.dataset.viewTarget);if(!e.target.closest(".stock-search-box"))$("stockSuggestions").classList.add("hidden");};
$("sidebarToggle").onclick=()=>{const collapsed=$("sidebar").classList.toggle("collapsed");localStorage.setItem("cq-sidebar",collapsed?"collapsed":"expanded");}; $("themeToggle").onclick=()=>{document.body.classList.toggle("dark");localStorage.setItem("cq-theme",document.body.classList.contains("dark")?"dark":"light");if(state.stock.response)renderStockResearch();};
$("refreshButton").onclick=refresh; $("stockSearchButton").onclick=()=>stockSearch(true); $("stockSearch").onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();stockSearch(true);}}; $("stockSearch").oninput=()=>{clearTimeout(state.stock.searchTimer);state.stock.searchTimer=setTimeout(()=>stockSearch(false),220);}; $("stockWatchToggle").onclick=toggleStockWatchlist; $("stockReload").onclick=fetchStockResearch; $("stockPoints").onchange=()=>{state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();}; $("stockZoomIn").onclick=()=>zoomStockChart(1); $("stockZoomOut").onclick=()=>zoomStockChart(-1); $("stockZoomReset").onclick=()=>{state.stock.viewport={timeframe:null,total:0,start:0,count:0};state.stock.selectedTradeDate=null;renderStockResearch();}; $("stockPanPrev").onclick=()=>panStockChart(-1); $("stockPanNext").onclick=()=>panStockChart(1); $("stockPan").oninput=e=>{state.stock.viewport.start=Number(e.target.value)||0;state.stock.selectedTradeDate=null;renderStockResearch();}; $("stockPriceChart").addEventListener("wheel",e=>{if(!state.stock.response)return;e.preventDefault();const rect=e.currentTarget.getBoundingClientRect(),anchor=(e.clientX-rect.left)/Math.max(rect.width,1);zoomStockChart(e.deltaY<0?1:-1,anchor);},{passive:false});
const stockStage=$("stockChartStage");stockStage.onpointerdown=e=>{if(!state.stock.response||e.button!==0)return;const drag=state.stock.drag;drag.active=true;drag.moved=false;drag.startX=e.clientX;drag.startIndex=state.stock.viewport.start;drag.pointerId=e.pointerId;stockStage.setPointerCapture?.(e.pointerId);stockStage.classList.add("dragging");};stockStage.onpointermove=e=>{const drag=state.stock.drag;if(!drag.active||drag.pointerId!==e.pointerId)return;const delta=e.clientX-drag.startX;if(Math.abs(delta)<4)return;drag.moved=true;const bars=Math.round(delta/Math.max(stockStage.clientWidth,1)*state.stock.viewport.count),maxStart=Math.max(0,state.stock.viewport.total-state.stock.viewport.count),next=Math.max(0,Math.min(maxStart,drag.startIndex-bars));if(next!==state.stock.viewport.start){state.stock.viewport.start=next;state.stock.selectedTradeDate=null;renderStockResearch();}};const finishStockDrag=e=>{const drag=state.stock.drag;if(!drag.active||drag.pointerId!==e.pointerId)return;drag.active=false;stockStage.releasePointerCapture?.(e.pointerId);stockStage.classList.remove("dragging");setTimeout(()=>{drag.moved=false;},0);};stockStage.onpointerup=finishStockDrag;stockStage.onpointercancel=finishStockDrag;
$("todayDate").onchange=loadToday; $("todayQuery").onclick=()=>{state.today.page=1;renderTodayRows();}; $("todaySearch").onkeydown=e=>{if(e.key==="Enter"){state.today.page=1;renderTodayRows();}}; $("taskQuery").onclick=()=>loadTasks(true); $("taskSearch").onkeydown=e=>{if(e.key==="Enter"){state.tasks.page=1;renderTaskRows();}}; $("executionQuery").onclick=()=>loadExecutions(true); $("calendarMonth").onchange=loadCalendar; $("calendarDetailQuery").onclick=()=>{state.calendar.page=1;renderCalendarDetail();}; $("calendarDetailSearch").onkeydown=e=>{if(e.key==="Enter"){state.calendar.page=1;renderCalendarDetail();}}; $("auditAll").onclick=auditAll; $("initStartButton").onclick=startInitialization; $("interfaceQuery").onclick=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceSearch").onkeydown=e=>{if(e.key==="Enter"){state.interfaces.page=1;renderInterfaceRows();}}; $("interfaceSource").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceAssetClass").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceStatus").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceCategory").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("interfaceCadence").onchange=()=>{state.interfaces.page=1;renderInterfaceRows();}; $("lineageQuery").onclick=()=>{state.interfaces.lineagePage=1;renderFieldLineage();}; $("lineageSearch").onkeydown=e=>{if(e.key==="Enter"){state.interfaces.lineagePage=1;renderFieldLineage();}}; $("serviceQuery").onclick=()=>loadServices(true); $("investmentMonth").onchange=loadInvestment; $("detailClose").onclick=()=>$("detailDialog").close();
$("todayPrev").onclick=()=>{if(state.today.page>1){state.today.page--;renderTodayRows();}};$("todayNext").onclick=()=>{state.today.page++;renderTodayRows();};
$("executionPrev").onclick=()=>{if(state.execution.page===1)return;state.execution.before=state.execution.history.pop()||null;state.execution.page--;loadExecutions()};$("executionNext").onclick=()=>{if(!state.execution.next)return;state.execution.history.push(state.execution.before);state.execution.before=state.execution.next;state.execution.page++;loadExecutions()};
$("taskPrev").onclick=()=>{if(state.tasks.page>1){state.tasks.page--;renderTaskRows();}};$("taskNext").onclick=()=>{state.tasks.page++;renderTaskRows();};
$("calendarDetailPrev").onclick=()=>{if(state.calendar.page>1){state.calendar.page--;renderCalendarDetail();}};$("calendarDetailNext").onclick=()=>{state.calendar.page++;renderCalendarDetail();};
$("servicePrev").onclick=()=>{if(state.services.page>1){state.services.page--;loadServices();}};$("serviceNext").onclick=()=>{state.services.page++;loadServices();};
$("interfacePrev").onclick=()=>{if(state.interfaces.page>1){state.interfaces.page--;renderInterfaceRows();}};$("interfaceNext").onclick=()=>{state.interfaces.page++;renderInterfaceRows();};
$("lineagePrev").onclick=()=>{if(state.interfaces.lineagePage>1){state.interfaces.lineagePage--;renderFieldLineage();}};$("lineageNext").onclick=()=>{state.interfaces.lineagePage++;renderFieldLineage();};
$("derivationPrev").onclick=()=>{if(state.derivations.page>1){state.derivations.page--;renderDerivationRows();}};$("derivationNext").onclick=()=>{state.derivations.page++;renderDerivationRows();};
$("ondemandPrev").onclick=()=>{if(state.derivations.ondemandPage>1){state.derivations.ondemandPage--;renderOndemandRows();}};$("ondemandNext").onclick=()=>{state.derivations.ondemandPage++;renderOndemandRows();};
$("todayDate").value=isoDate(new Date());$("calendarMonth").value=monthValue();$("investmentMonth").value=monthValue();$("initEnd").value=isoDate(new Date(Date.now()-86400000));if(localStorage.getItem("cq-theme")==="dark")document.body.classList.add("dark");if(localStorage.getItem("cq-sidebar")==="collapsed")$("sidebar").classList.add("collapsed");refresh();setInterval(refresh,30000);
