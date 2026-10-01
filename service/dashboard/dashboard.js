const $ = (id) => document.getElementById(id);
const state = { execution: { page: 1, before: null, history: [], next: null }, services: { page: 1, size: 20, items: null }, sourceDependency: { page: 1, size: 20, view: null }, initId: null };
const labels = {queued:"排队",running:"运行",retrying:"重试",validating:"校验",publishing:"发布",success:"成功",attention:"需处理",not_dispatched:"未派发",not_due:"尚未到发布时间",complete:"完整",empty_verified:"已验证为空",gaps:"缺失",partial:"不完整",indeterminate:"待确认"};
const fmt = (v) => Number(v || 0).toLocaleString();
const esc = (v) => String(v ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pill = (v) => `<span class="pill ${esc(v)}">${esc(labels[v] || v)}</span>`;
const isoDate = (d) => d.toISOString().slice(0,10);
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
  const names={overview:"V2 数据总览",today:"今日交付",executions:"执行实例",calendar:"数据日历",coverage:"覆盖审计",initialization:"数据初始化",sources:"数据源",services:"服务目录",investment:"投资日历"};
  $("pageTitle").textContent=names[name];
  ({today:loadToday,executions:loadExecutions,calendar:loadCalendar,coverage:loadCoverage,initialization:loadInitialization,sources:loadSources,services:loadServices,investment:loadInvestment}[name]||(()=>{}))();
}

async function loadOverview() {
  const health = await api("/api/v1/ops/data-health");
  const s=health.summary;
  $("metricActive").textContent=fmt(s.active_task_instances); $("metricAttention").textContent=fmt(s.attention_task_instances);
  $("metricReady").textContent=`${fmt(s.ready_dataset_states)} / ${fmt(s.latest_dataset_states)}`; $("metricMissing").textContent=fmt(s.missing_partitions);
  const banner=$("healthBanner"); banner.className=`health-banner ${health.status}`;
  banner.innerHTML=`<div><small>V2 系统状态</small><strong>${health.status==="healthy"?"数据链路健康":health.status==="critical"?"存在必须处理的问题":"仍有采集或核验进行中"}</strong><p>活动实例 ${fmt(s.active_task_instances)} · 需处理 ${fmt(s.attention_task_instances)} · 未就绪状态 ${fmt(s.not_ready_dataset_states)}</p></div>`;
  $("issueList").innerHTML=health.issues.length?health.issues.map(x=>`<div class="issue ${x.severity}"><div><strong>${esc(x.dataset)} · ${esc(x.observation_key)}</strong><small>${esc(x.status)} · ${esc(x.action)}</small></div>${x.source_execution_id?`<button data-execution="${x.source_execution_id}">实例 #${x.source_execution_id}</button>`:""}</div>`).join(""):'<p>当前没有 V2 数据状态异常。</p>';
  $("updatedAt").textContent=`更新于 ${new Date(health.generated_at).toLocaleTimeString("zh-CN")}`;
}

async function loadToday() {
  const day=$("todayDate").value||isoDate(new Date());
  const view=await api(`/api/v1/ops/orchestration-v2/today?data_date=${day}`), s=view.summary;
  $("todayExpected").textContent=fmt(s.expected); $("todayReady").textContent=fmt(s.strictly_ready); $("todayActive").textContent=fmt(s.active); $("todayProblem").textContent=fmt(s.attention+s.not_dispatched);
  $("todaySummary").textContent=`${day} 数据交付：严格就绪 ${s.strictly_ready}/${s.expected} 个已到期任务；${s.recovered||0} 个由后续补采恢复；${s.not_due||0} 个次晨发布任务尚未到期。执行实例失败不再覆盖已修复的数据状态。`;
  $("todayRows").innerHTML=view.items.map(x=>`<tr><td><strong>${esc(x.task_key)}</strong></td><td>${esc(x.observation_key)}</td><td>${pill(x.execution_status||x.status)}</td><td>${esc(x.current_node_key)}</td><td>${pill(x.delivery_status||"attention")} · ${fmt(x.ready_datasets)} / ${fmt(x.datasets)}${x.problem_datasets?` · <b>${fmt(x.problem_datasets)} 异常</b>`:""}</td><td>${fmt(x.rows_written)} / ${fmt(x.rows_fetched)}</td><td>${x.task_execution_id?`<button data-execution="${x.task_execution_id}">详情</button>`:"—"}</td></tr>`).join("")||'<tr><td colspan="7">没有应执行任务</td></tr>';
}

async function loadExecutions(reset=false) {
  if(reset) state.execution={page:1,before:null,history:[],next:null};
  const p=new URLSearchParams({limit:"50"}); if(state.execution.before)p.set("before_id",state.execution.before); if($("executionStatus").value)p.set("status",$("executionStatus").value); if($("executionTask").value.trim())p.set("task_key",$("executionTask").value.trim());
  const view=await api(`/api/v1/ops/orchestration-v2/executions?${p}`); state.execution.next=view.page.next_cursor;
  $("executionRows").innerHTML=view.items.map(x=>`<tr><td>#${x.task_execution_id}</td><td><strong>${esc(x.task_key)}</strong><small>v${x.definition_version}</small></td><td>${esc(x.purpose)}</td><td>${esc(x.observation_key)}<small>${esc(x.observation_start)} → ${esc(x.observation_end)}</small></td><td>${pill(x.status)}<small>${esc(x.current_node_key)}</small></td><td>${fmt(x.attempt)}/${fmt(x.max_attempts)}</td><td>${fmt(x.rows_written)}</td><td>${esc(x.failure_category||"")}</td><td><button data-execution="${x.task_execution_id}">详情</button></td></tr>`).join("")||'<tr><td colspan="9">没有匹配实例</td></tr>';
  $("executionPage").textContent=`第 ${state.execution.page} 页`; $("executionPrev").disabled=state.execution.page===1; $("executionNext").disabled=!state.execution.next;
}
async function showExecution(id){const view=await api(`/api/v1/ops/orchestration-v2/executions/${id}`);$("detailTitle").textContent=`V2 执行实例 #${id}`;$("detailBody").textContent=JSON.stringify(view,null,2);$("detailDialog").showModal();}

function renderMonth(gridId, month, rows, detail) {
  const [y,m]=month.split("-").map(Number), first=new Date(y,m-1,1), last=new Date(y,m,0), offset=(first.getDay()+6)%7, byDay=new Map(rows.map(x=>[String(x.data_date||x.event_date).slice(0,10),x])); let html="";
  for(let i=0;i<offset;i++)html+='<div class="day outside"></div>';
  for(let d=1;d<=last.getDate();d++){const key=`${y}-${String(m).padStart(2,"0")}-${String(d).padStart(2,"0")}`,x=byDay.get(key);let cls="none",text="无 V2 状态";if(x){if(Number(x.problems)>0){cls="problem";text=`${x.problems} 个问题`;}else if(Number(x.active)>0){cls="active";text=`${x.active} 进行中`;}else{cls="complete";text=`${x.ready}/${x.dataset_states} 就绪`;}}html+=`<button class="day ${cls}" data-date="${key}"><b>${d}</b><small>${esc(detail?detail(x):text)}</small></button>`;}
  $(gridId).innerHTML=html;
}
async function loadCalendar(){const month=$("calendarMonth").value||monthValue(),[y,m]=month.split("-").map(Number),start=`${month}-01`,end=isoDate(new Date(y,m,0));const view=await api(`/api/v1/ops/orchestration-v2/data-calendar?start_date=${start}&end_date=${end}`);renderMonth("calendarGrid",month,view.days);}

async function loadCoverage(){const view=await api("/api/v1/ops/coverage");const s=view.summary;$("coverageSummary").textContent=`${s.audited}/${s.auditable} 已审计 · ${s.with_gaps} 个数据集有缺口 · 缺失 ${fmt(s.missing_partitions)} 个周期`;$("coverageRows").innerHTML=view.datasets.map(x=>{const a=x.latest||{};return `<tr><td><strong>${esc(x.dataset)}</strong></td><td>${esc(x.strategy)}</td><td>${pill(a.status||"unaudited")}</td><td>${esc(a.start_date)} → ${esc(a.end_date)}</td><td>${fmt(a.missing_partitions)}</td><td>${fmt(a.partial_partitions)}</td><td>${x.repairable?"V2":"仅诊断"}</td></tr>`}).join("");}
async function auditAll(){await api("/api/v1/ops/coverage/audits",{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":`dashboard-audit-${Date.now()}`},body:JSON.stringify({datasets:null,all_datasets:true,start_date:null,end_date:null})});notice("已提交全部数据集严格审计；缺口会通过 V2 修复链路处理。");loadCoverage();}

async function loadInitialization(){const view=await api("/api/v1/ops/initialization");const c=view.latest;state.initId=c?.initialization_id||null;$("initializationState").innerHTML=c?`<strong>#${c.initialization_id} · ${esc(c.status)}</strong><p>阶段：${esc(c.phase_name)} · 完成 ${fmt(c.completed_steps)}/${fmt(c.planned_steps)} · 失败 ${fmt(c.failed_steps)}</p>`:"尚未运行 V2 初始化";if(!c){$("initializationRows").innerHTML="";return;}const rows=await api(`/api/v1/ops/initialization/${c.initialization_id}/steps?limit=500`);$("initializationRows").innerHTML=rows.map(x=>`<tr><td>${esc(x.resource_type)}</td><td>${esc(x.task_key||x.dataset_name)}</td><td>${esc(x.observation_key||x.start_date)} → ${esc(x.observation_end||x.end_date)}</td><td>${pill(x.status)}</td><td>${fmt(x.attempt)}/${fmt(x.max_attempts)}</td><td>${esc(x.failure_category||x.error_message||"")}</td></tr>`).join("");}
async function startInitialization(){if(!confirm("确认使用 V2 对全部业务数据做严格审计，并只补采确认缺失的周期？"))return;const body={profile:$("initProfile").value,history_start:$("initStart").value||null,history_end:$("initEnd").value||null,auto_activate:true};await api("/api/v1/ops/initialization",{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":`dashboard-v2-init-${body.profile}-${body.history_start}-${body.history_end}`},body:JSON.stringify(body)});notice("V2 初始化已启动。");loadInitialization();}

async function loadSources(reset=false){
  const sources=await api("/api/v1/data/sources");$("sourceCards").innerHTML=sources.items.map(x=>`<article class="source"><h3>${esc(x.display_name)}</h3><p>${esc(x.source_id)} · ${x.acquisition_modes.map(esc).join(" / ")}</p><dl><dt>端点</dt><dd>${fmt(x.endpoint_count)}</dd><dt>凭据</dt><dd>${x.credential_required?"环境变量":"无需"}</dd><dt>地址</dt><dd>${esc(x.base_url)}</dd><dt>类型</dt><dd>${esc(x.source_kind)}</dd></dl></article>`).join("");
  if(reset){state.sourceDependency.page=1;state.sourceDependency.view=null;}
  if(!state.sourceDependency.view)state.sourceDependency.view=await api("/api/v1/data/source-priorities");const view=state.sourceDependency.view,s=view.summary;
  $("sourceRouteCount").textContent=fmt(s.routes);$("sourceRequiredCount").textContent=fmt(s.financial_data_required_now);$("sourceRealtimeCount").textContent=fmt(s.financial_data_realtime_required);$("sourceNoLocalCount").textContent=fmt(s.financial_data_primary_no_local_canonical);
  const category=$("sourceDependencyClass").value,query=$("sourceDependencySearch").value.trim().toLowerCase();let items=view.items.filter(x=>(!category||x.dependency_class===category)&&(!query||[x.route,...x.local_datasets].join(" ").toLowerCase().includes(query)));const pages=Math.max(1,Math.ceil(items.length/state.sourceDependency.size));state.sourceDependency.page=Math.min(state.sourceDependency.page,pages);const start=(state.sourceDependency.page-1)*state.sourceDependency.size,rows=items.slice(start,start+state.sourceDependency.size);
  const classLabels={financial_data_realtime_required:"实时必须依赖",financial_data_primary_no_local_canonical:"无本地规范等价",local_first_canonical_fallback_ready:"本地优先，可回退",local_overlap_adapter_pending:"本地重叠，适配待完成"};
  $("sourceDependencyRows").innerHTML=rows.map(x=>`<tr><td><code>${esc(x.route)}</code></td><td>${esc(classLabels[x.dependency_class]||x.dependency_class)}</td><td>${x.requires_financial_data?"是":"否"}</td><td>${x.local_datasets.length?x.local_datasets.map(esc).join("、"):"—"}</td><td>${esc(x.public_access)}</td><td>${esc(x.adapter_status)}</td></tr>`).join("")||'<tr><td colspan="6">没有匹配路由</td></tr>';
  $("sourceDependencyPage").textContent=`第 ${state.sourceDependency.page} / ${pages} 页 · ${items.length} 条`;$('sourceDependencyPrev').disabled=state.sourceDependency.page===1;$('sourceDependencyNext').disabled=state.sourceDependency.page===pages;
}

async function loadServices(reset=false){
  if(reset){state.services.page=1;state.services.items=null;}
  if(!state.services.items){const view=await api("/api/v1/catalog");state.services.items=view.layers.flatMap(layer=>layer.endpoints.map(endpoint=>({...endpoint,layer_id:layer.id,layer_title:layer.title})));}
  const layer=$("serviceLayer").value,query=$("serviceSearch").value.trim().toLowerCase();let items=state.services.items.filter(x=>(!layer||x.layer_id===layer)&&(!query||[x.name,x.path,...x.local_datasets,...x.upstream_sources].join(" ").toLowerCase().includes(query)));
  const pages=Math.max(1,Math.ceil(items.length/state.services.size));state.services.page=Math.min(state.services.page,pages);const start=(state.services.page-1)*state.services.size,rows=items.slice(start,start+state.services.size);
  $("serviceSummary").textContent=`共 ${items.length} 个匹配入口；研究服务只读取本地规范数据，Financial Data 仅在规范层适配器通过后按缺失切片受控回退。`;
  $("serviceRows").innerHTML=rows.map(x=>{const datasets=x.local_datasets.length?`${x.local_datasets.slice(0,5).map(esc).join("、")}${x.local_datasets.length>5?` 等 ${x.local_datasets.length} 个`:""}`:`动态：${esc(x.dependency_scope)}`;const fallback=x.fallback_routes.length?`${x.fallback_routes.slice(0,2).map(esc).join("、")}${x.fallback_routes.length>2?` 等 ${x.fallback_routes.length} 个`:""}`:"不查询";return `<tr><td>${pill(x.layer_id)}<strong>${esc(x.name)}</strong><small>${esc(x.data_origin)}${x.derivation?` · ${esc(x.derivation)}`:""}</small></td><td><code>${esc(x.method)} ${esc(x.path)}</code></td><td>${datasets}</td><td>${x.upstream_sources.map(esc).join(" / ")||"系统元数据"}</td><td>${esc(x.read_strategy)}</td><td>${fallback}</td></tr>`}).join("")||'<tr><td colspan="6">没有匹配服务</td></tr>';
  $("servicePage").textContent=`第 ${state.services.page} / ${pages} 页`;$('servicePrev').disabled=state.services.page===1;$('serviceNext').disabled=state.services.page===pages;
}

async function loadInvestment(){const month=$("investmentMonth").value||monthValue(),[y,m]=month.split("-").map(Number),start=`${month}-01`,end=isoDate(new Date(y,m,0));const view=await api(`/api/v1/research/investment-calendar?start_date=${start}&end_date=${end}&importance=important`);const events=view.events||view.items||[];const groups={};events.forEach(x=>(groups[String(x.event_date||x.date).slice(0,10)]??=[]).push(x));const rows=Object.entries(groups).map(([event_date,items])=>({event_date,items}));renderMonth("investmentGrid",month,rows,x=>x?`${x.items.length} 个事件`:"无重要事件");$("investmentGrid").onclick=e=>{const b=e.target.closest("[data-date]");if(!b)return;const items=groups[b.dataset.date]||[];$("investmentEvents").innerHTML=items.map(x=>`<div class="issue"><div><strong>${esc(x.event_name||x.name||x.title)}</strong><small>${esc(x.country)} · ${esc(x.event_time||x.time)} · 实际 ${esc(x.actual)}</small></div></div>`).join("")||"<p>当日无重要事件</p>";};}

async function refresh(){notice("");try{await loadOverview();const active=document.querySelector(".nav.active")?.dataset.view;if(active&&active!=="overview")await ({today:loadToday,executions:loadExecutions,calendar:loadCalendar,coverage:loadCoverage,initialization:loadInitialization,sources:loadSources,services:loadServices,investment:loadInvestment}[active]||(()=>{}))();}catch(e){notice(`加载失败：${e.message}`);}}

document.querySelector("nav").onclick=e=>{const b=e.target.closest("[data-view]");if(b)activate(b.dataset.view)};
document.body.onclick=e=>{const b=e.target.closest("[data-execution]");if(b)showExecution(b.dataset.execution)};
$("sidebarToggle").onclick=()=>$("sidebar").classList.toggle("collapsed"); $("themeToggle").onclick=()=>{document.body.classList.toggle("dark");localStorage.setItem("cq-theme",document.body.classList.contains("dark")?"dark":"light")};
$("refreshButton").onclick=refresh; $("todayDate").onchange=loadToday; $("executionQuery").onclick=()=>loadExecutions(true); $("calendarMonth").onchange=loadCalendar; $("auditAll").onclick=auditAll; $("initStartButton").onclick=startInitialization; $("sourceDependencyQuery").onclick=()=>loadSources(true); $("serviceQuery").onclick=()=>loadServices(true); $("investmentMonth").onchange=loadInvestment; $("detailClose").onclick=()=>$("detailDialog").close();
$("executionPrev").onclick=()=>{if(state.execution.page===1)return;state.execution.before=state.execution.history.pop()||null;state.execution.page--;loadExecutions()};$("executionNext").onclick=()=>{if(!state.execution.next)return;state.execution.history.push(state.execution.before);state.execution.before=state.execution.next;state.execution.page++;loadExecutions()};
$("servicePrev").onclick=()=>{if(state.services.page>1){state.services.page--;loadServices();}};$("serviceNext").onclick=()=>{state.services.page++;loadServices();};
$("sourceDependencyPrev").onclick=()=>{if(state.sourceDependency.page>1){state.sourceDependency.page--;loadSources();}};$("sourceDependencyNext").onclick=()=>{state.sourceDependency.page++;loadSources();};
$("todayDate").value=isoDate(new Date());$("calendarMonth").value=monthValue();$("investmentMonth").value=monthValue();$("initEnd").value=isoDate(new Date(Date.now()-86400000));if(localStorage.getItem("cq-theme")==="dark")document.body.classList.add("dark");refresh();setInterval(refresh,30000);
