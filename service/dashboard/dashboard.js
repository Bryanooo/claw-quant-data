const state = {
  data: [], summary: {}, services: [], coverage: [], coverageSummary: {},
  initialization: null, fanoutCampaigns: [], freshness: [],
  dataHealth: {}, healthIssues: [], timer: null,
  activeView: "overview",
  pages: {
    health: 1, interfaces: 1, fanout: 1, coverage: 1,
    coveragePartitions: 1, batchChildren: 1, initializationSteps: 1, fanoutPages: 1
  },
  dialogData: {
    coveragePartitions: [], batchChildren: [], initializationSteps: [], fanoutPages: []
  }
};

const pageSizes = {
  health: 10, interfaces: 20, fanout: 10, coverage: 20,
  coveragePartitions: 40, batchChildren: 20, initializationSteps: 20, fanoutPages: 20
};

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
}[char]));
const labels = {
  dedicated: "专项调度", policy: "策略队列", fanout: "全量扇出", manual: "手动",
  daily: "每日", weekly: "每周", monthly: "每月", quarterly: "每季度", manualCadence: "手动",
  complete: "严格完成", empty: "空结果", incomplete: "不完整", unverified: "未验证",
  running: "运行中", retrying: "等待重试", verifying: "完整性审计中", failed: "失败", pending: "尚未运行",
  paused: "已暂停", attention: "需要处理", success: "已结束", superseded: "已由新方案替代",
  event_driven: "按事件更新"
};
const coverageLabels = {
  trading_daily: "交易日", trading_weekly: "完整交易周", trading_monthly: "完整月份",
  report_quarterly: "财务报告期", observed_only: "仅观察", non_temporal: "无日期分区",
  complete: "日期齐全", gaps: "存在缺口", empty: "无数据", present: "有数据",
  partial: "截面不完整", missing: "缺失", pending: "等待发布", observed_only: "仅记录", unverified: "日历不足"
};
const initializationLabels = {
  awaiting_initialization: "等待初始采集", initializing: "正在初始化", daily: "日常增量模式",
  running: "运行中", paused: "已暂停", attention: "需要处理", ready: "等待激活", completed: "已完成",
  foundation: "基础依赖", core_history: "核心历史", finance_history: "财务历史",
  catalog_history: "目录历史", latest_baseline: "最新基线", fanout_baseline: "全量扇出", verification: "覆盖验收"
};
const issueLabels = {
  initialization_blocked: "历史初始化中断",
  initialization_pending: "等待初始化首采",
  collection_pending: "采集任务处理中",
  coverage_incomplete: "采集截面不完整",
  collection_incomplete: "采集结果不完整",
  execution_failure: "采集执行失败",
  collection_failed: "自动采集失败",
  manual_parameters_required: "需要受控参数",
  manual_scope_required: "需要明确采集范围",
  coverage_gap: "日期 / 截面缺口",
  stale_dataset: "数据已经过期",
  dataset_empty: "数据集为空",
  never_collected: "尚未首采",
  collection_unverified: "采集未严格验证",
  coverage_not_audited: "尚未覆盖审计",
  freshness_not_configured: "未配置时效口径"
};

function notice(message = "") {
  $("connectionNotice").textContent = message;
  $("connectionNotice").classList.toggle("hidden", !message);
}

function formatTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"
  }).format(new Date(value));
}

function statusGroup(status) {
  if (status === "complete") return "complete";
  if (status === "empty") return "empty";
  if (["running", "retrying", "verifying"].includes(status)) return "active";
  if (status === "unverified") return "unverified";
  if (["incomplete", "failed", "unresolved_failure"].includes(status)) return "attention";
  return "pending";
}

function pageRows(rows, key) {
  const pageSize = pageSizes[key];
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.pages[key] = Math.min(Math.max(state.pages[key] || 1, 1), totalPages);
  const start = (state.pages[key] - 1) * pageSize;
  const info = document.querySelector(`[data-page-info="${key}"]`);
  const range = document.querySelector(`[data-page-range="${key}"]`);
  const previous = document.querySelector(`[data-page-key="${key}"][data-page-delta="-1"]`);
  const next = document.querySelector(`[data-page-key="${key}"][data-page-delta="1"]`);
  if (info) info.textContent = `第 ${state.pages[key]} / ${totalPages} 页`;
  if (range) {
    const end = Math.min(start + pageSize, rows.length);
    range.textContent = rows.length ? `第 ${start + 1}–${end} 条，共 ${rows.length} 条` : "0 条";
  }
  if (previous) previous.disabled = state.pages[key] <= 1;
  if (next) next.disabled = state.pages[key] >= totalPages;
  return { rows: rows.slice(start, start + pageSize), start, totalPages };
}

function activateView(view) {
  state.activeView = view;
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.viewPanel !== view);
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    const selected = button.dataset.view === view;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
}

function filteredRows() {
  const query = $("searchInput").value.trim().toLowerCase();
  const cadence = $("cadenceFilter").value;
  const status = $("statusFilter").value;
  const mode = $("modeFilter").value;
  return state.data.filter((item) => {
    const completion = item.unresolved_failure
      ? "unresolved_failure"
      : (item.latest?.completion_status || "pending");
    return (!query || `${item.api_name} ${item.title} ${item.category}`.toLowerCase().includes(query))
      && (cadence === "all" || item.cadence === cadence)
      && (status === "all" || statusGroup(completion) === status)
      && (mode === "all" || item.automation_mode === mode);
  });
}

function render() {
  const rows = filteredRows();
  const page = pageRows(rows, "interfaces");
  const end = Math.min(page.start + page.rows.length, rows.length);
  $("resultCount").textContent = rows.length
    ? `显示 ${page.start + 1}–${end}，共 ${rows.length} 个接口`
    : "0 个接口";
  $("interfaceTabCount").textContent = `${state.data.length} 个接口`;
  if (!rows.length) {
    $("interfaceRows").innerHTML = '<tr><td colspan="7" class="empty-state">没有符合筛选条件的接口</td></tr>';
    return;
  }
  $("interfaceRows").innerHTML = page.rows.map((item) => {
    const latest = item.latest || {};
    const completion = latest.completion_status || "pending";
    const unresolved = item.unresolved_failure;
    const isBatch = latest.job_kind === "batch";
    const isCampaign = latest.source === "fanout_campaign";
    const canRetry = latest.source === "queue" && latest.status === "failed" && !isBatch;
    const batch = latest.batch;
    const campaign = latest.campaign;
    const batchProgress = unresolved
      ? `仍缺 ${unresolved.period_key || unresolved.expected_for || "历史周期"} · ${unresolved.error_message || "尚未恢复"}`
      : campaign
      ? `实体 ${campaign.completed_offset}/${campaign.universe_total} · 分页 ${campaign.pages_completed}/${campaign.pages_created}`
      : batch
      ? `子任务 ${batch.succeeded}/${batch.total} 成功 · ${batch.failed} 失败 · ${batch.queued + batch.running} 待处理`
      : (latest.completion_reason || item.automatic_reason);
    const fetched = latest.rows_fetched == null ? "—" : Number(latest.rows_fetched).toLocaleString();
    const stored = latest.rows_inserted == null ? "—" : Number(latest.rows_inserted).toLocaleString();
    return `<tr>
      <td><span class="api-name">${escapeHtml(item.api_name)}</span><span class="api-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</span></td>
      <td><span class="pill">${labels[item.automation_mode] || item.automation_mode}</span></td>
      <td><span>${labels[item.cadence] || item.cadence}</span><span class="completion-reason">${escapeHtml(latest.period_key || item.automatic_reason)}</span></td>
      <td><span class="pill status-${unresolved ? "failed" : completion}">${unresolved ? "历史缺口" : (labels[completion] || completion)}</span><span class="completion-reason">${escapeHtml(batchProgress)}</span></td>
      <td class="number">${fetched} / ${stored}<span class="completion-reason">获取 / 新增</span></td>
      <td>${formatTime(latest.finished_at)}<span class="completion-reason">${latest.attempt ? `第 ${latest.attempt} 次尝试` : "—"}</span></td>
      <td>${isCampaign
        ? `<button class="row-action" data-fanout-detail="${latest.id}">查看活动</button>`
        : isBatch
        ? `<button class="row-action" data-batch="${latest.id}">查看批次</button>`
        : `<button class="row-action" data-retry="${latest.id || ""}" ${canRetry ? "" : "disabled"}>重试</button>`}</td>
    </tr>`;
  }).join("");
}

function renderSummary(summary) {
  $("automatedCount").textContent = summary.automated ?? "—";
  $("completeCount").textContent = summary.complete ?? "—";
  $("runningCount").textContent = summary.running ?? "—";
  $("attentionCount").textContent = summary.attention ?? "—";
  $("manualAttentionCount").textContent = summary.manual_attention ?? "—";
  $("unverifiedCount").textContent = summary.unverified ?? "—";
  $("emptyCount").textContent = summary.empty ?? "—";
  $("coverageText").textContent = summary.collectable
    ? `${summary.automated} / ${summary.collectable} 个有权限接口`
    : "等待加载";
}

function filteredHealthIssues() {
  const selected = $("dataIssueFilter").value;
  if (selected === "all") return state.healthIssues;
  if (selected === "confirmed") {
    return state.healthIssues.filter((item) => item.confidence === "confirmed");
  }
  if (selected === "missing") {
    return state.healthIssues.filter((item) => [
      "dataset_empty", "never_collected", "manual_parameters_required",
      "manual_scope_required"
    ].includes(item.kind));
  }
  return state.healthIssues.filter((item) => item.confidence === "unknown");
}

function renderDataHealth() {
  const health = state.dataHealth;
  const summary = health.summary || {};
  const history = health.history || {};
  const rows = filteredHealthIssues();
  const page = pageRows(rows, "health");
  $("datasetsWithDataCount").textContent = summary.datasets_with_data ?? "—";
  $("backfillPendingCount").textContent = summary.backfill_pending_interfaces ?? "—";
  $("verifiedEmptyInterfaceCount").textContent = summary.verified_empty_interfaces ?? "—";
  $("confirmedDataIssueCount").textContent = summary.confirmed_data_issue_count ?? "—";
  $("dataHealthSummary").textContent =
    `${summary.fresh_datasets ?? 0}/${summary.datasets ?? 0} 个数据集已证明新鲜 · ` +
    `${summary.event_driven_datasets ?? 0} 个按事件更新 · ` +
    `${summary.scope_required_interfaces ?? 0} 个接口需要人工限定范围 · ` +
    `${summary.scheduled_unaudited_datasets ?? 0} 个周期数据集待审计 · ` +
    `${summary.missing_partitions ?? 0} 个日期缺失 · ` +
    `${summary.partial_partitions ?? 0} 个截面不完整`;

  const historyNode = $("historyHealth");
  historyNode.className = `history-health status-${health.status || "warning"}`;
  if (history.initialization_id) {
    const phase = initializationLabels[history.phase_name] || history.phase_name || "未知阶段";
    const total = history.phase_logical_total_steps ?? history.phase_planned_steps ?? 0;
    const materialized = history.phase_materialized_steps ?? history.phase_planned_steps ?? 0;
    historyNode.innerHTML = `<strong>历史初始化 #${history.initialization_id}</strong><span>${escapeHtml(history.history_start || "?")} → ${escapeHtml(history.history_end || "?")} · 第 ${history.phase_index || "?"}/${history.phase_total || "?"} 阶段 ${escapeHtml(phase)} · 当前阶段已完成 ${Number(history.phase_completed_steps || 0).toLocaleString()}/${Number(total).toLocaleString()}，已生成 ${Number(materialized).toLocaleString()}，失败 ${Number(history.phase_failed_steps || 0).toLocaleString()}。这不是全流程完成率。</span>`;
  } else {
    historyNode.innerHTML = `<strong>历史初始化</strong><span>${escapeHtml(history.message || "尚无初始化记录")}</span>`;
  }

  const end = Math.min(page.start + page.rows.length, rows.length);
  $("dataHealthResultCount").textContent = rows.length
    ? `显示 ${page.start + 1}–${end}，共 ${rows.length} 个问题`
    : "0 个问题";
  $("healthTabCount").textContent = `${summary.confirmed_issue_count ?? 0} 个已确认问题`;
  if (!rows.length) {
    $("dataHealthRows").innerHTML = '<tr><td colspan="5" class="empty-state">当前筛选下没有数据问题</td></tr>';
    return;
  }
  $("dataHealthRows").innerHTML = page.rows.map((item) => `<tr>
    <td><span class="issue-resource severity-${item.severity}">${escapeHtml(item.resource)}</span><span class="completion-reason">${escapeHtml(item.resource_type)}</span></td>
    <td><span class="issue-kind">${escapeHtml(issueLabels[item.kind] || item.kind)}</span><span class="pill status-${item.severity === "critical" ? "failed" : item.severity === "warning" ? "incomplete" : item.severity === "info" ? "pending" : "verifying"}">${item.confidence === "confirmed" ? "已确认" : item.confidence === "planned" ? "已纳入计划" : item.confidence === "configuration" ? "待配置" : "完整性未知"}</span></td>
    <td>${escapeHtml(item.scope || "—")}</td>
    <td>${escapeHtml(item.detail || "—")}</td>
    <td><span>${escapeHtml(item.action || "—")}</span>${item.partition_details ? `<button class="row-action health-detail-action" data-health-coverage-detail="${escapeHtml(item.dataset || item.resource)}">查看日期</button>` : ""}</td>
  </tr>`).join("");
}

async function loadDataHealth() {
  $("refreshButton").disabled = true;
  try {
    const response = await fetch("/api/v1/data-health");
    if (!response.ok) throw new Error(`数据健康接口返回 ${response.status}`);
    const payload = await response.json();
    state.dataHealth = payload;
    state.healthIssues = payload.issues || [];
    state.freshness = payload.freshness || [];
    state.data = payload.collection?.interfaces || [];
    state.summary = payload.collection?.summary || {};
    state.services = payload.collection?.services || [];
    state.coverage = payload.coverage?.datasets || [];
    state.coverageSummary = payload.coverage?.summary || {};
    renderSummary(state.summary);
    render();
    renderCoverage();
    renderInitialization(payload.initialization);
    renderDataHealth();
    notice("");
    const services = state.services.map((item) =>
      `${item.component}:${item.status === "healthy" ? "正常" : "异常"}`
    ).join(" · ");
    $("lastUpdated").textContent = `更新于 ${formatTime(payload.generated_at)}${services ? ` · ${services}` : ""}`;
  } catch (error) {
    notice(`暂时无法读取数据健康状态：${error.message}`);
  } finally {
    $("refreshButton").disabled = false;
  }
}

async function loadOverview() {
  $("refreshButton").disabled = true;
  try {
    const response = await fetch("/api/v1/collection-overview");
    if (!response.ok) throw new Error(`状态接口返回 ${response.status}`);
    const payload = await response.json();
    state.data = payload.interfaces;
    state.summary = payload.summary;
    state.services = payload.services || [];
    renderSummary(payload.summary);
    render();
    notice("");
    const services = state.services.map((item) => {
      const queued = item.queue?.queued;
      const backlog = queued ? `,排队${queued}` : "";
      return `${item.component}:${item.status === "healthy" ? "正常" : "异常"}${backlog}`;
    }).join(" · ");
    const workloads = (payload.fanout_workloads || []).map((item) => {
      const label = item.workload === "historical" ? "历史补采" : "日常扇出";
      return `${label}:活动${item.active_campaigns || 0},排队${item.queued || 0}`;
    }).join(" · ");
    $("lastUpdated").textContent = `更新于 ${formatTime(payload.generated_at)}${workloads ? ` · ${workloads}` : ""}${services ? ` · ${services}` : ""}`;
  } catch (error) {
    notice(`暂时无法读取采集状态：${error.message}`);
  } finally {
    $("refreshButton").disabled = false;
  }
}

function renderInitialization(payload) {
  state.initialization = payload;
  const runtime = payload.runtime;
  const campaign = payload.active;
  const latest = payload.latest;
  const background = runtime.mode === "daily" && Boolean(campaign);
  const mode = background
    ? "日常增量模式（历史补采并行）"
    : (initializationLabels[runtime.mode] || runtime.mode);
  const action = $("initializationActionButton");
  $("initializationDetailButton").disabled = !(campaign || latest);
  if (!campaign) {
    $("initializationSummary").textContent = runtime.mode === "daily" && latest
      ? `初始采集 #${latest.initialization_id} 已完成（${latest.history_start} 至 ${latest.history_end}），Scheduler 正在执行日常增量更新。`
      : runtime.mode === "daily"
      ? "当前为日常增量模式；这是升级实例，尚无独立的初始化活动记录。"
      : "尚未执行初始采集；日常调度会保持暂停。";
    $("initializationProgress").classList.add("hidden");
    action.textContent = runtime.mode === "daily" ? "重新初始化" : "开始初始化";
    action.dataset.action = "start";
    action.disabled = false;
    $("initializationProfile").disabled = false;
    return;
  }
  const phase = initializationLabels[campaign.phase_name] || campaign.phase_name;
  const status = initializationLabels[campaign.status] || campaign.status;
  const logicalTotal = campaign.logical_total_steps ?? campaign.planned_steps ?? 0;
  const materialized = campaign.materialized_steps ?? campaign.planned_steps ?? 0;
  const percent = logicalTotal
    ? Math.round(campaign.completed_steps / logicalTotal * 100)
    : 0;
  $("initializationSummary").textContent = `${mode} · 第 ${campaign.phase_index}/${campaign.phase_total} 阶段：${phase} · ${status} · 当前阶段已完成 ${Number(campaign.completed_steps || 0).toLocaleString()}/${Number(logicalTotal).toLocaleString()}，已生成 ${Number(materialized).toLocaleString()}（不是全流程完成率）`;
  $("initializationProgress").classList.remove("hidden");
  $("initializationProgress").title = `当前阶段逻辑进度 ${percent}%；后续阶段不计入该比例`;
  $("initializationProgressBar").style.width = `${Math.min(100, percent)}%`;
  $("initializationProfile").value = campaign.profile;
  $("initializationProfile").disabled = true;
  if (campaign.status === "running") {
    action.textContent = "暂停初始化";
    action.dataset.action = "pause";
  } else if (["paused", "attention"].includes(campaign.status)) {
    action.textContent = campaign.status === "attention" ? "重试失败步骤" : "继续初始化";
    action.dataset.action = "resume";
  } else if (campaign.status === "ready") {
    action.textContent = "启用日常更新";
    action.dataset.action = "activate";
  } else {
    action.disabled = true;
  }
}

async function loadInitialization() {
  try {
    const response = await fetch("/api/v1/initialization");
    if (!response.ok) throw new Error(`初始化接口返回 ${response.status}`);
    renderInitialization(await response.json());
  } catch (error) {
    notice(`暂时无法读取初始化状态：${error.message}`);
  }
}

async function initializationAction() {
  const payload = state.initialization;
  const campaign = payload?.active;
  const action = $("initializationActionButton").dataset.action || "start";
  const messages = {
    start: `确认开始“${$("initializationProfile").selectedOptions[0].textContent}”初始采集？任务将在后台分阶段执行。${payload?.runtime?.mode === "daily" ? "现有日常增量调度会继续运行。" : "首次初始化验收完成前，日常增量调度暂不启动。"}${$("initializationProfile").value === "full" ? " 全部历史会生成数万条任务，可能运行数小时至数天，并占用大量存储。" : ""}`,
    pause: "确认暂停初始化协调？已经进入队列或正在运行的子任务不会被强行中断。",
    resume: "确认继续初始化？失败步骤会使用新的幂等轮次重新提交。",
    activate: "确认切换到日常增量模式？之后 Scheduler 将恢复周期任务。"
  };
  if (!window.confirm(messages[action])) return;
  const button = $("initializationActionButton");
  button.disabled = true;
  try {
    let url = "/api/v1/initialization";
    const options = { method: "POST", headers: {} };
    if (action === "start") {
      options.headers["Content-Type"] = "application/json";
      options.headers["Idempotency-Key"] = `dashboard-initialization-${Date.now()}`;
      options.body = JSON.stringify({
        profile: $("initializationProfile").value,
        auto_activate: true
      });
    } else {
      url += `/${campaign.initialization_id}/${action}`;
    }
    const response = await fetch(url, options);
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || `初始化操作返回 ${response.status}`);
    }
    notice(action === "start" ? "初始采集已创建，将按阶段异步执行。" : "初始化状态已更新。");
    await loadDataHealth();
  } catch (error) {
    notice(`初始化操作失败：${error.message}`);
  } finally {
    button.disabled = false;
  }
}

function renderInitializationSteps() {
  const steps = state.dialogData.initializationSteps;
  const page = pageRows(steps, "initializationSteps");
  $("initializationSteps").innerHTML = steps.length ? page.rows.map((step) => {
      const isFanout = step.resource_type === "fanout";
      const resource = isFanout
        ? `扇出活动 #${step.fanout_campaign_id} · 实体 ${step.fanout_completed_offset || 0}/${step.fanout_universe_total || "?"} · 分页 ${step.fanout_pages_completed || 0}/${step.fanout_pages_created || 0}`
        : step.resource_type === "collection"
        ? `采集任务 #${step.collection_job_id}`
        : `覆盖审计 #${step.coverage_job_id}`;
      const error = step.collection_error || step.fanout_error;
      const rows = isFanout ? step.fanout_rows_inserted : step.rows_inserted;
      return `
      <article class="batch-child">
        <div><strong>${escapeHtml(step.step_key)}</strong><small>${escapeHtml(resource)}</small>${error ? `<small class="error-text">${escapeHtml(error)}</small>` : ""}</div>
        <div class="batch-child-state"><span class="pill status-${step.state === "complete" ? "complete" : step.state === "failed" ? "failed" : "running"}">${step.state === "complete" ? "完成" : step.state === "failed" ? "失败" : "处理中"}</span><span>${Number(rows || 0).toLocaleString()} 行</span>${isFanout ? `<button class="row-action" data-fanout-detail="${step.fanout_campaign_id}">查看活动</button>` : ""}</div>
      </article>`;
    }).join("") : '<p class="empty-state">当前阶段尚未生成步骤</p>';
}

async function showInitializationSteps() {
  const campaign = state.initialization?.active || state.initialization?.latest;
  if (!campaign) return;
  $("initializationDialogTitle").textContent = `初始化 #${campaign.initialization_id} · ${initializationLabels[campaign.phase_name] || campaign.phase_name}`;
  $("initializationSteps").innerHTML = '<p class="empty-state">正在读取…</p>';
  $("initializationDialog").showModal();
  try {
    const response = await fetch(`/api/v1/initialization/${campaign.initialization_id}/steps?limit=2000`);
    if (!response.ok) throw new Error(`步骤接口返回 ${response.status}`);
    state.dialogData.initializationSteps = await response.json();
    state.pages.initializationSteps = 1;
    renderInitializationSteps();
  } catch (error) {
    state.dialogData.initializationSteps = [];
    pageRows([], "initializationSteps");
    $("initializationSteps").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  }
}

function renderFanoutCampaigns() {
  const page = pageRows(state.fanoutCampaigns, "fanout");
  $("fanoutCampaignSummary").textContent = state.fanoutCampaigns.length
    ? `${state.fanoutCampaigns.length} 个最近活动；进度只统计已严格验证的分页`
    : "尚无全量扇出活动";
  $("fanoutResultCount").textContent = state.fanoutCampaigns.length
    ? `显示 ${page.start + 1}–${Math.min(page.start + page.rows.length, state.fanoutCampaigns.length)}，共 ${state.fanoutCampaigns.length} 个活动`
    : "0 个活动";
  $("fanoutTabCount").textContent = `${state.fanoutCampaigns.length} 个最近活动`;
  if (!state.fanoutCampaigns.length) {
    $("fanoutCampaignRows").innerHTML = '<tr><td colspan="7" class="empty-state">尚无全量扇出活动</td></tr>';
    return;
  }
  $("fanoutCampaignRows").innerHTML = page.rows.map((campaign) => {
    const total = Number(campaign.universe_total || 0);
    const completed = Number(campaign.completed_offset || 0);
    const percent = total ? Math.min(Math.round(completed / total * 100), 100) : 0;
    const canPause = campaign.status === "running";
    const canResume = ["paused", "attention"].includes(campaign.status);
    return `<tr>
      <td><span class="api-name">${escapeHtml(campaign.api_name)}</span><span class="api-title">活动 #${campaign.campaign_id} · ${labels[campaign.cadence] || campaign.cadence} ${escapeHtml(campaign.period_key || "按需")} · ${escapeHtml(campaign.universe_source || "等待冻结依赖宇宙")}</span></td>
      <td><span class="pill status-${campaign.completion_status}">${labels[campaign.completion_status] || campaign.completion_status}</span><span class="completion-reason">${escapeHtml(campaign.error_message || labels[campaign.status] || campaign.status)}</span></td>
      <td class="number">${completed.toLocaleString()} / ${total ? total.toLocaleString() : "—"}<span class="completion-reason">已验证实体 · ${percent}%</span></td>
      <td class="number">${Number(campaign.pages_completed || 0)} / ${Number(campaign.pages_created || 0)}<span class="completion-reason">已验证 / 已生成</span></td>
      <td class="number">${Number(campaign.rows_fetched || 0).toLocaleString()} / ${Number(campaign.rows_inserted || 0).toLocaleString()}<span class="completion-reason">获取 / 新增</span></td>
      <td>${formatTime(campaign.finished_at || campaign.updated_at)}</td>
      <td class="campaign-actions"><button class="row-action" data-fanout-detail="${campaign.campaign_id}">查看</button><button class="row-action" data-fanout-action="${canPause ? "pause" : "resume"}" data-fanout-id="${campaign.campaign_id}" ${canPause || canResume ? "" : "disabled"}>${canPause ? "暂停" : "继续"}</button></td>
    </tr>`;
  }).join("");
}

async function loadFanoutCampaigns() {
  try {
    const response = await fetch("/api/v1/collection-fanout-campaigns?limit=50");
    if (!response.ok) throw new Error(`扇出活动接口返回 ${response.status}`);
    state.fanoutCampaigns = await response.json();
    renderFanoutCampaigns();
  } catch (error) {
    notice(`暂时无法读取全量扇出活动：${error.message}`);
  }
}

function renderFanoutPages() {
  const pages = state.dialogData.fanoutPages;
  const page = pageRows(pages, "fanoutPages");
  $("fanoutPages").innerHTML = pages.length ? page.rows.map((item) => `
      <article class="batch-child">
        <div><strong>第 ${Number(item.page_index) + 1} 页 · 批次 #${item.batch_job_id}</strong><small>实体 ${item.entity_offset} → ${item.next_offset} · ${item.entities_selected} 个</small>${item.error_message ? `<small class="error-text">${escapeHtml(item.error_message)}</small>` : ""}</div>
        <div class="batch-child-state"><span class="pill status-${item.batch_completion_status}">${labels[item.batch_completion_status] || item.batch_completion_status}</span><span>${Number(item.rows_inserted || 0).toLocaleString()} 行</span><button class="row-action" data-batch="${item.batch_job_id}">查看子任务</button></div>
      </article>`).join("") : '<p class="empty-state">活动尚未生成分页</p>';
}

async function showFanoutCampaign(campaignId) {
  $("fanoutDialogTitle").textContent = `全量扇出活动 #${campaignId}`;
  $("fanoutPages").innerHTML = '<p class="empty-state">正在读取…</p>';
  if (!$("fanoutDialog").open) $("fanoutDialog").showModal();
  try {
    const response = await fetch(`/api/v1/collection-fanout-campaigns/${campaignId}`);
    if (!response.ok) throw new Error(`活动明细返回 ${response.status}`);
    const campaign = await response.json();
    $("fanoutDialogTitle").textContent = `${campaign.api_name} · 活动 #${campaign.campaign_id}`;
    state.dialogData.fanoutPages = campaign.pages || [];
    state.pages.fanoutPages = 1;
    renderFanoutPages();
  } catch (error) {
    state.dialogData.fanoutPages = [];
    pageRows([], "fanoutPages");
    $("fanoutPages").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  }
}

async function fanoutAction(campaignId, action, button) {
  const wording = action === "pause" ? "暂停" : "继续";
  if (!window.confirm(`确认${wording}全量扇出活动 #${campaignId}？当前正在运行的子任务不会被强制中断。`)) return;
  button.disabled = true;
  try {
    const response = await fetch(`/api/v1/collection-fanout-campaigns/${campaignId}/${action}`, { method: "POST" });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || `活动操作返回 ${response.status}`);
    }
    notice(`全量扇出活动 #${campaignId} 已${wording}。`);
    await Promise.all([loadFanoutCampaigns(), loadDataHealth()]);
  } catch (error) {
    notice(`无法${wording}活动：${error.message}`);
    button.disabled = false;
  }
}

async function retryJob(jobId, button) {
  if (!window.confirm("确认重新执行这个失败任务？任务会进入持久化队列，并可能调用上游接口。")) {
    return;
  }
  button.disabled = true;
  try {
    const response = await fetch(`/api/v1/collection-jobs/${jobId}/retry`, {
      method: "POST",
      headers: {
        "Idempotency-Key": `dashboard-retry-${jobId}-${Date.now()}`
      }
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || `重试返回 ${response.status}`);
    }
    notice("重试任务已进入持久化队列。");
    await loadDataHealth();
  } catch (error) {
    notice(`无法重试：${error.message}`);
    button.disabled = false;
  }
}

function renderBatchChildren() {
  const children = state.dialogData.batchChildren;
  const page = pageRows(children, "batchChildren");
  if (!children.length) {
    $("batchChildren").innerHTML = '<p class="empty-state">这个批次没有子任务</p>';
    return;
  }
  $("batchChildren").innerHTML = page.rows.map((child) => `
    <article class="batch-child">
      <div>
        <strong>#${child.job_id} · ${escapeHtml(child.api_name || child.task_name)}</strong>
        <small>${escapeHtml(JSON.stringify(child.parameters?.parameters || child.parameters))}</small>
      </div>
      <div class="batch-child-state">
        <span class="pill status-${child.completion_status}">${labels[child.completion_status] || child.completion_status}</span>
        <span>${Number(child.rows_inserted || 0).toLocaleString()} 行</span>
        <button class="row-action" data-batch-retry="${child.job_id}" ${child.status === "failed" ? "" : "disabled"}>重试</button>
      </div>
    </article>`).join("");
}

async function showBatch(jobId) {
  $("batchDialogTitle").textContent = `批次 #${jobId} · 子任务`;
  $("batchChildren").innerHTML = '<p class="empty-state">正在读取…</p>';
  if (!$("batchDialog").open) $("batchDialog").showModal();
  try {
    const response = await fetch(`/api/v1/collection-jobs?parent_job_id=${jobId}&limit=200`);
    if (!response.ok) throw new Error(`批次明细返回 ${response.status}`);
    state.dialogData.batchChildren = await response.json();
    state.pages.batchChildren = 1;
    renderBatchChildren();
  } catch (error) {
    state.dialogData.batchChildren = [];
    pageRows([], "batchChildren");
    $("batchChildren").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  }
}

async function dispatchLatest() {
  if (!window.confirm("确认生成最近日、周、月和季度的补采任务？已有任务会通过幂等机制自动跳过。")) {
    return;
  }
  $("dispatchButton").disabled = true;
  try {
    const response = await fetch("/api/v1/collection-dispatch", {
      method: "POST"
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || `补采返回 ${response.status}`);
    }
    const body = await response.json();
    notice(body.total ? `已生成 ${body.total} 个补采任务。` : "最近周期任务均已存在，无需重复生成。");
    await loadDataHealth();
  } catch (error) {
    notice(`无法生成补采任务：${error.message}`);
  } finally {
    $("dispatchButton").disabled = false;
  }
}

function renderCoverage() {
  const summary = state.coverageSummary;
  const page = pageRows(state.coverage, "coverage");
  $("coverageSummary").textContent = summary.audited == null
    ? "等待首次审计"
    : `${summary.classified}/${summary.datasets} 已分类 · ${summary.audited} 已审计 · ${summary.missing_partitions} 个缺失 · ${summary.partial_partitions || 0} 个截面不完整`;
  $("coverageResultCount").textContent = state.coverage.length
    ? `显示 ${page.start + 1}–${Math.min(page.start + page.rows.length, state.coverage.length)}，共 ${state.coverage.length} 个数据集`
    : "0 个数据集";
  $("coverageTabCount").textContent = `${state.coverage.length} 个数据集`;
  if (!state.coverage.length) {
    $("coverageRows").innerHTML = '<tr><td colspan="7" class="empty-state">暂无覆盖规则</td></tr>';
    return;
  }
  $("coverageRows").innerHTML = page.rows.map((item) => {
    const latest = item.latest;
    const coverage = latest?.coverage_ratio == null
      ? "—"
      : `${(Number(latest.coverage_ratio) * 100).toFixed(1)}%`;
    const range = latest ? `${latest.start_date} → ${latest.end_date}` : "尚未审计";
    const status = latest?.status || "pending";
    const partitionCounts = !latest
      ? "—"
      : (item.detects_missing_partitions
        ? `${latest.present_partitions} / ${latest.expected_partitions}`
        : `${latest.observed_partitions} / —`);
    const partitionCaption = item.coverage_level === "not_applicable"
      ? "无日期分区"
      : (item.detects_missing_partitions ? "存在 / 应有" : "已观察 / 应有");
    const recentMissing = item.recent_missing?.length
      ? item.recent_missing.join("、")
      : (item.coverage_level === "not_applicable" ? "不适用" : (item.detects_missing_partitions ? "—" : "不推断缺口"));
    return `<tr>
      <td><span class="api-name">${escapeHtml(item.dataset)}</span><span class="api-title">${escapeHtml(item.description)}</span></td>
      <td><span class="pill">${coverageLabels[item.strategy] || item.strategy}</span></td>
      <td>${escapeHtml(range)}</td>
      <td><span class="pill coverage-${status}">${coverageLabels[status] || status}</span><span class="completion-reason">${coverage}</span></td>
      <td class="number">${partitionCounts}<span class="completion-reason">${partitionCaption}</span></td>
      <td><span class="missing-dates">${escapeHtml(recentMissing)}</span></td>
      <td><button class="row-action" data-coverage-detail="${escapeHtml(item.dataset)}" ${item.auditable ? "" : "disabled"}>查看日期</button></td>
    </tr>`;
  }).join("");
}

async function loadCoverage() {
  try {
    const response = await fetch("/api/v1/coverage");
    if (!response.ok) throw new Error(`覆盖接口返回 ${response.status}`);
    const payload = await response.json();
    state.coverage = payload.datasets;
    state.coverageSummary = payload.summary;
    renderCoverage();
  } catch (error) {
    notice(`暂时无法读取覆盖审计：${error.message}`);
  }
}

async function runCoverageAudit() {
  if (!window.confirm("确认检查已配置自动覆盖规则的数据集？审计只读取业务表，不会调用 Tushare。")) {
    return;
  }
  $("coverageAuditButton").disabled = true;
  try {
    const response = await fetch("/api/v1/coverage/audits", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `dashboard-coverage-${Date.now()}`
      },
      body: "{}"
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || `覆盖审计返回 ${response.status}`);
    }
    const body = await response.json();
    notice(`已生成 ${body.created} 个覆盖审计任务，Auditor 将异步处理。`);
    window.setTimeout(loadDataHealth, 1500);
  } catch (error) {
    notice(`无法生成覆盖审计：${error.message}`);
  } finally {
    $("coverageAuditButton").disabled = false;
  }
}

function renderCoveragePartitions() {
  const partitions = state.dialogData.coveragePartitions;
  const page = pageRows(partitions, "coveragePartitions");
  if (!partitions.length) {
    $("coveragePartitions").innerHTML = '<p class="empty-state">尚未执行覆盖审计</p>';
    return;
  }
  $("coveragePartitions").innerHTML = page.rows.map((item) => `
    <div class="partition-item partition-${item.status}">
      <strong>${escapeHtml(item.partition_date)}</strong>
      <span>${coverageLabels[item.status] || item.status}</span>
      <small>${Number(item.row_count).toLocaleString()} 行 · ${item.entity_count ?? "—"}/${item.expected_entity_count ?? "—"} 个标的</small>
    </div>`).join("");
}

async function showCoverageDetail(dataset) {
  $("coverageDialogTitle").textContent = `${dataset} · 日期分区`;
  $("coveragePartitions").innerHTML = '<p class="empty-state">正在读取…</p>';
  $("coverageDialog").showModal();
  try {
    const response = await fetch(`/api/v1/coverage/datasets/${encodeURIComponent(dataset)}/partitions?limit=400`);
    if (!response.ok) throw new Error(`日期明细返回 ${response.status}`);
    const payload = await response.json();
    state.dialogData.coveragePartitions = payload.partitions || [];
    state.pages.coveragePartitions = 1;
    renderCoveragePartitions();
  } catch (error) {
    state.dialogData.coveragePartitions = [];
    pageRows([], "coveragePartitions");
    $("coveragePartitions").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  }
}

async function refreshAll() {
  await Promise.all([loadDataHealth(), loadFanoutCampaigns()]);
}

$("refreshButton").addEventListener("click", refreshAll);
$("dispatchButton").addEventListener("click", dispatchLatest);
$("coverageAuditButton").addEventListener("click", runCoverageAudit);
$("initializationActionButton").addEventListener("click", initializationAction);
$("initializationDetailButton").addEventListener("click", showInitializationSteps);
$("dataIssueFilter").addEventListener("change", () => {
  state.pages.health = 1;
  renderDataHealth();
});
document.querySelector(".console-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (button) activateView(button.dataset.view);
});
document.querySelector(".console-tabs").addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
  const tabs = [...document.querySelectorAll("[data-view]")];
  const current = tabs.indexOf(event.target.closest("[data-view]"));
  if (current < 0) return;
  event.preventDefault();
  const direction = event.key === "ArrowRight" ? 1 : -1;
  const next = tabs[(current + direction + tabs.length) % tabs.length];
  activateView(next.dataset.view);
  next.focus();
});
$("dataHealthRows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-health-coverage-detail]");
  if (button) showCoverageDetail(button.dataset.healthCoverageDetail);
});
["searchInput", "cadenceFilter", "statusFilter", "modeFilter"].forEach((id) => {
  $(id).addEventListener(id === "searchInput" ? "input" : "change", () => {
    state.pages.interfaces = 1;
    render();
  });
});
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-page-key]");
  if (!button || button.disabled) return;
  const key = button.dataset.pageKey;
  const renderers = {
    health: renderDataHealth,
    interfaces: render,
    fanout: renderFanoutCampaigns,
    coverage: renderCoverage,
    coveragePartitions: renderCoveragePartitions,
    batchChildren: renderBatchChildren,
    initializationSteps: renderInitializationSteps,
    fanoutPages: renderFanoutPages
  };
  state.pages[key] += Number(button.dataset.pageDelta);
  renderers[key]?.();
});
$("interfaceRows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-retry]");
  if (button && !button.disabled) retryJob(button.dataset.retry, button);
  const batchButton = event.target.closest("[data-batch]");
  if (batchButton) showBatch(batchButton.dataset.batch);
  const campaignButton = event.target.closest("[data-fanout-detail]");
  if (campaignButton) showFanoutCampaign(campaignButton.dataset.fanoutDetail);
});
$("batchChildren").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-batch-retry]");
  if (!button || button.disabled) return;
  await retryJob(button.dataset.batchRetry, button);
  const jobId = $("batchDialogTitle").textContent.match(/#(\d+)/)?.[1];
  if (jobId) await showBatch(jobId);
});
$("initializationSteps").addEventListener("click", (event) => {
  const button = event.target.closest("[data-fanout-detail]");
  if (button) showFanoutCampaign(button.dataset.fanoutDetail);
});
$("fanoutCampaignRows").addEventListener("click", (event) => {
  const detail = event.target.closest("[data-fanout-detail]");
  if (detail) showFanoutCampaign(detail.dataset.fanoutDetail);
  const action = event.target.closest("[data-fanout-action]");
  if (action && !action.disabled) {
    fanoutAction(action.dataset.fanoutId, action.dataset.fanoutAction, action);
  }
});
$("fanoutPages").addEventListener("click", (event) => {
  const button = event.target.closest("[data-batch]");
  if (button) showBatch(button.dataset.batch);
});
$("coverageRows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-coverage-detail]");
  if (button) showCoverageDetail(button.dataset.coverageDetail);
});
$("coverageDialogClose").addEventListener("click", () => $("coverageDialog").close());
$("batchDialogClose").addEventListener("click", () => $("batchDialog").close());
$("initializationDialogClose").addEventListener("click", () => $("initializationDialog").close());
$("fanoutDialogClose").addEventListener("click", () => $("fanoutDialog").close());

activateView(state.activeView);
refreshAll();
state.timer = window.setInterval(refreshAll, 30000);
