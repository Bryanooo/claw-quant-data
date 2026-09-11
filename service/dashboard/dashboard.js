const state = {
  data: [], summary: {}, services: [], coverage: [], coverageSummary: {},
  initialization: null, fanoutCampaigns: [], freshness: [], delivery: null,
  calendar: null, calendarDetail: null, todayDataDetail: null, calendarMonth: null,
  selectedCalendarDate: null,
  dataHealth: {}, healthIssues: [], timer: null,
  operationalSummary: null, hasLoadedOperational: false,
  coverageRangeDataset: null, coverageDetailDataset: null,
  activeView: "today",
  sidebarCollapsed: false,
  theme: "dark",
  endpointErrors: {}, isRefreshing: false, hasLoadedSnapshot: false,
  noticeKind: null,
  snapshotGeneratedAt: null, lastSuccessfulRefresh: null,
  pages: {
    delivery: 1, calendarDetails: 1, health: 1, interfaces: 1, fanout: 1, coverage: 1,
    coveragePartitions: 1, batchChildren: 1, initializationSteps: 1, fanoutPages: 1
  },
  dialogData: {
    coveragePartitions: [], batchChildren: [], initializationSteps: [], fanoutPages: []
  }
};

try {
  state.lastSuccessfulRefresh = window.localStorage.getItem("claw-quant:last-successful-dashboard-refresh");
  state.sidebarCollapsed = window.localStorage.getItem("claw-quant:sidebar-collapsed") === "true";
  state.theme = window.localStorage.getItem("claw-quant:theme") || "dark";
} catch (_error) {
  // Private browsing and hardened browsers may disable local storage.
}

const pageSizes = {
  delivery: 15, calendarDetails: 15, health: 10, interfaces: 20, fanout: 10, coverage: 20,
  coveragePartitions: 40, batchChildren: 20, initializationSteps: 20, fanoutPages: 20
};

const $ = (id) => {
  const node = document.getElementById(id);
  if (!node) throw new Error(`控制台页面缺少 #${id} 元素，请强制刷新静态资源`);
  return node;
};
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
}[char]));
const labels = {
  dedicated: "专项调度", policy: "策略队列", fanout: "全量扇出", manual: "手动",
  daily: "每日", weekly: "每周", monthly: "每月", quarterly: "每季度", manualCadence: "手动",
  complete: "严格完成", empty: "空结果", incomplete: "不完整", unverified: "未验证",
  running: "运行中", retrying: "等待重试", verifying: "完整性审计中", failed: "失败", pending: "尚未运行",
  paused: "已暂停", attention: "需要处理", success: "已结束", superseded: "已由新方案替代",
  event_driven: "按事件更新", not_due: "等待发布时间", waiting: "等待任务生成",
  queued: "已排队", overdue: "已逾期", in_progress: "交付窗口内"
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

function notice(message = "", kind = "action") {
  state.noticeKind = message ? kind : null;
  $("connectionNotice").textContent = message;
  $("connectionNotice").classList.toggle("hidden", !message);
}

const endpointLabels = {
  delivery: "今日交付",
  calendar: "数据日历",
  preflight: "运行预检",
  health: "数据健康",
  fanout: "扇出活动"
};

function setEndpointError(source, error) {
  state.endpointErrors[source] = error.message || String(error);
}

function clearEndpointError(source) {
  delete state.endpointErrors[source];
}

function bannerFacts() {
  const healthSummary = state.dataHealth?.summary || {};
  const operational = state.operationalSummary || {};
  const operationalCounts = operational.summary || {};
  const collectionSummary = state.summary || {};
  const deliverySummary = state.delivery?.summary || {};
  const dataSummary = state.todayDataDetail?.summary || {};
  const dataItems = state.todayDataDetail?.data_items || [];
  const unhealthyServices = state.services.length
    ? state.services.filter((item) => item.status !== "healthy")
    : (operational.unhealthy_services || []).map((component) => ({ component, status: "unhealthy" }));
  return {
    unhealthyServices,
    unresolved: Number(operationalCounts.unresolved_failures ?? healthSummary.unresolved_failures ?? collectionSummary.unresolved_failures ?? 0),
    critical: Math.max(Number(healthSummary.critical_issue_count || 0), operational.status === "critical" ? 1 : 0),
    confirmedData: Number(healthSummary.confirmed_data_issue_count || 0),
    deliveryAttention: Number(deliverySummary.attention || 0),
    overdue: Number(deliverySummary.overdue || 0),
    active: Number(operationalCounts.running_interfaces ?? collectionSummary.running ?? 0) +
      Number(operationalCounts.pending_interfaces ?? collectionSummary.pending ?? 0) +
      Number(deliverySummary.queued || 0) + Number(deliverySummary.running || 0),
    unknown: Number(healthSummary.unknown_issue_count || 0),
    dataStatus: dataSummary.status,
    dataAudited: Number(dataSummary.audited_present || 0),
    dataMonitored: Number(dataSummary.monitored_datasets || 0),
    dataIssues: Number(dataSummary.audited_issues || 0),
    dataWaiting: dataItems.filter((item) =>
      item.validation_status === "unverified" && !item.attention
    ).length,
    initializationStatus: operational.history?.status || (state.dataHealth?.initialization?.active || {}).status
  };
}

function renderOperationsBanner() {
  const banner = $("operationsBanner");
  const label = $("operationsBannerLabel");
  const title = $("operationsBannerTitle");
  const detail = $("operationsBannerDetail");
  const freshness = $("operationsBannerFreshness");
  const errors = Object.entries(state.endpointErrors);
  const facts = bannerFacts();
  let status = "loading";
  let labelText = "正在检查";
  let titleText = "正在建立系统运行快照";
  let detailText = "正在核对服务、今日交付、历史失败与数据缺口。";

  if (errors.length || navigator.onLine === false) {
    status = "offline";
    labelText = "服务失联";
    titleText = "控制台无法取得完整运行状态，页面数据可能已经过期";
    detailText = errors.length
      ? `读取失败：${errors.map(([source, message]) => `${endpointLabels[source] || source}（${message}）`).join("；")}`
      : "浏览器当前处于离线状态，无法连接本地数据服务。";
  } else if (state.hasLoadedOperational || state.hasLoadedSnapshot) {
    const trueIssueCount = Math.max(
      facts.critical,
      facts.confirmedData,
      facts.dataIssues,
      facts.unresolved,
      facts.deliveryAttention
    );
    if (facts.unhealthyServices.length || trueIssueCount || facts.overdue || ["attention", "paused"].includes(facts.initializationStatus)) {
      status = "critical";
      labelText = "需要处理";
      titleText = `发现 ${trueIssueCount || facts.unhealthyServices.length || 1} 个已确认运行问题`;
      const parts = [];
      if (facts.unhealthyServices.length) parts.push(facts.unhealthyServices.map((item) =>
        `${item.label || item.component}：${item.diagnostic || "心跳异常"}；${item.action || "请进入异常中心查看"}`
      ).join(" · "));
      if (facts.unresolved) parts.push(`${facts.unresolved} 个未恢复采集失败`);
      if (facts.deliveryAttention) parts.push(`今日 ${facts.deliveryAttention} 项真实异常`);
      if (facts.dataIssues) parts.push(`今日 ${facts.dataIssues} 个数据集确认缺失或不完整`);
      if (facts.overdue) parts.push(`${facts.overdue} 项交付逾期`);
      if (["attention", "paused"].includes(facts.initializationStatus)) parts.push("历史初始化阻塞或暂停");
      detailText = parts.join(" · ") || "异常中心已有可定位证据。";
    } else if (facts.active || facts.unknown || facts.initializationStatus === "running") {
      status = "warning";
      labelText = "处理中";
      titleText = "系统在线，仍有采集或完整性核验正在进行";
      detailText = `${facts.active} 项排队/运行 · ${facts.unknown} 项完整性待确认${facts.initializationStatus === "running" ? " · 历史初始化进行中" : ""}`;
    } else if (facts.dataWaiting && facts.dataMonitored) {
      status = "healthy";
      labelText = "正常推进";
      titleText = `今日数据已通过 ${facts.dataAudited}/${facts.dataMonitored} 项严格审计`;
      const due = state.delivery?.summary;
      detailText = `${facts.dataWaiting} 项等待上游约定发布时间，当前不判为缺失` +
        (due ? ` · 今日任务交付 ${due.completed_due || 0}/${due.due_now || 0}` : "");
    } else {
      status = "healthy";
      labelText = "运行正常";
      titleText = "未发现服务故障、未恢复失败或逾期交付";
      const due = state.delivery?.summary;
      detailText = due
        ? `今日任务交付 ${due.completed_due || 0}/${due.due_now || 0} · 已确认数据问题 0`
        : "服务、任务和数据完整性检查均已通过。";
    }
  }

  banner.className = `operations-banner status-${status}`;
  label.textContent = labelText;
  title.textContent = titleText;
  detail.textContent = detailText;
  document.body.classList.toggle("is-offline", status === "offline");
  freshness.textContent = state.lastSuccessfulRefresh
    ? `上次完整快照 ${formatTime(state.lastSuccessfulRefresh)}`
    : "尚无成功快照";
  $("operationsIssuesButton").textContent = status === "critical" ? "立即处理" : "查看异常";
}

async function loadOperationalSummary() {
  try {
    const response = await fetch("/api/v1/data-health/summary");
    if (!response.ok) throw new Error(`运行预检接口返回 ${response.status}`);
    state.operationalSummary = await response.json();
    state.hasLoadedOperational = true;
    clearEndpointError("preflight");
    $("lastUpdated").textContent = `运行预检更新于 ${formatTime(state.operationalSummary.generated_at)} · 正在加载完整数据明细`;
    renderOperationsBanner();
    return true;
  } catch (error) {
    state.hasLoadedOperational = false;
    setEndpointError("preflight", error);
    renderOperationsBanner();
    return false;
  }
}

function formatTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"
  }).format(new Date(value));
}

function formatClock(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit", minute: "2-digit", hour12: false
  }).format(new Date(value));
}

function shanghaiToday() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit"
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function currentCalendarMonth() {
  return shanghaiToday().slice(0, 7);
}

function calendarMonthRange(monthKey) {
  const [year, month] = monthKey.split("-").map(Number);
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return {
    startDate: `${year}-${String(month).padStart(2, "0")}-01`,
    endDate: `${year}-${String(month).padStart(2, "0")}-${String(days).padStart(2, "0")}`
  };
}

function shiftCalendarMonth(delta) {
  const [year, month] = state.calendarMonth.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, month - 1 + delta, 1));
  state.calendarMonth = `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}`;
  state.selectedCalendarDate = null;
  state.calendarDetail = null;
  state.pages.calendarDetails = 1;
  loadCalendar().then(renderOperationsBanner);
}

function renderCalendar() {
  const payload = state.calendar;
  if (!payload) return;
  const summary = payload.summary || {};
  $("calendarMonthPicker").value = state.calendarMonth;
  if (payload.observed_min_date) $("calendarMonthPicker").min = payload.observed_min_date.slice(0, 7);
  if (payload.observed_max_date) $("calendarMonthPicker").max = payload.observed_max_date.slice(0, 7);
  $("calendarSummary").textContent =
    `按数据事实：${summary.complete_days || 0} 天通过当前规则严格审计 · ${summary.observed_days || 0} 天已有数据待完整审计 · ` +
    `${summary.in_progress_days || 0} 天采集/核验中 · ${summary.issue_days || 0} 天确认异常；历史范围 ${payload.observed_min_date || "—"} 至 ${payload.observed_max_date || "—"}`;
  $("calendarTabCount").textContent = summary.issue_days
    ? `${summary.issue_days} 天异常`
    : `${summary.complete_days || 0} 天完成`;
  const firstDay = new Date(`${payload.start_date}T00:00:00+08:00`).getDay();
  const leading = (firstDay + 6) % 7;
  const today = shanghaiToday();
  const statusCopy = {
    complete: "严格完成", observed: "已有数据", in_progress: "核验中", issue: "确认异常",
    untracked: "无数据事实", future: "未来"
  };
  const cells = Array.from({ length: leading }, () => '<span class="calendar-spacer" aria-hidden="true"></span>');
  for (const day of payload.days || []) {
    const completed = Number(day.audited_present ?? day.completed_total ?? 0);
    const total = Number(day.monitored_datasets ?? day.total ?? 0);
    const evidence = day.status === "untracked"
      ? "没有物理分区或当前审计证据"
      : day.status === "issue"
      ? `${day.audited_issues || day.attention || 0} 个数据集确认异常`
      : day.status === "observed"
      ? `${day.observed_datasets || 0} 个数据集 · ${Number(day.observed_rows || 0).toLocaleString()} 行`
      : total ? `${completed}/${total} 个数据集审计通过` : "没有物理数据事实";
    cells.push(`<button type="button" class="calendar-day status-${day.status}${day.data_date === state.selectedCalendarDate ? " is-selected" : ""}${day.data_date === today ? " is-today" : ""}" data-calendar-date="${day.data_date}" aria-label="数据日期 ${day.data_date} ${statusCopy[day.status] || day.status}">
      <span class="calendar-date">${Number(day.data_date.slice(-2))}</span>
      <strong>${statusCopy[day.status] || day.status}</strong>
      <small>${escapeHtml(evidence)}</small>
    </button>`);
  }
  $("calendarGrid").innerHTML = cells.join("");
}

function filteredCalendarDetailRows() {
  const rows = state.calendarDetail?.data_items || [];
  const filter = $("calendarDetailFilter").value;
  if (filter === "attention") return rows.filter((item) => item.attention);
  if (filter === "unverified") return rows.filter((item) =>
    ["observed", "unverified"].includes(item.validation_status));
  if (filter === "complete") return rows.filter((item) => item.validation_status === "present");
  return rows;
}

function renderCalendarDetail() {
  const payload = state.calendarDetail;
  if (!payload) return;
  const summary = payload.summary || {};
  const rows = filteredCalendarDetailRows();
  const page = pageRows(rows, "calendarDetails");
  $("calendarDetailTitle").textContent = `${payload.data_date} 数据事实明细`;
  $("calendarDetailSummary").textContent =
    `物理存在 ${summary.observed_datasets || 0}/${summary.monitored_datasets || 0} · ` +
    `当前规则审计通过 ${summary.audited_present || 0}/${summary.monitored_datasets || 0} · ` +
    `确认异常 ${summary.audited_issues || 0} · 任务旁证 ${summary.task_completed || 0}/${summary.task_total || 0}`;
  $("calendarDetailResultCount").textContent = rows.length
    ? `显示 ${page.start + 1}–${Math.min(page.start + page.rows.length, rows.length)}，共 ${rows.length} 个数据集`
    : "0 个数据集";
  if (!rows.length) {
    $("calendarDetailRows").innerHTML = '<tr><td colspan="7" class="empty-state">该日期没有物理数据或适用的严格数据要求</td></tr>';
    return;
  }
  $("calendarDetailRows").innerHTML = page.rows.map((item) => {
    const status = item.validation_status || "unverified";
    const validationLabel = item.availability_state === "waiting_publication"
      ? "等待上游发布"
      : item.availability_state === "waiting_recheck"
      ? "等待自动复查"
      : coverageLabels[status] || (status === "observed" ? "已有数据 / 待审计" : status);
    const task = item.task || {};
    const taskStatus = task.delivery_status || "pending";
    const entityEvidence = item.entity_count == null
      ? "该规则只校验日期分区"
      : `${Number(item.entity_count).toLocaleString()} / ${item.expected_entity_count == null ? "—" : Number(item.expected_entity_count).toLocaleString()} 个实体`;
    const ratio = item.entity_coverage_ratio == null ? "" : ` · ${(Number(item.entity_coverage_ratio) * 100).toFixed(1)}%`;
    const taskEvidence = task.api_name
      ? `${labels[taskStatus] || taskStatus} · 执行日 ${(task.business_dates || []).join("、") || "—"}`
      : "无同期任务记录（不影响物理数据事实）";
    return `<tr class="${item.attention ? "delivery-row-attention" : ""}">
      <td><span class="api-name">${escapeHtml(item.dataset_name)}</span><span class="api-title">上游 ${escapeHtml(item.api_name)}</span></td>
      <td class="number">${Number(item.row_count || 0).toLocaleString()} 行<span class="completion-reason">数据日期 ${escapeHtml(item.data_date)}</span></td>
      <td><span class="pill coverage-${status}">${validationLabel}</span><span class="completion-reason">${item.audit_checked_at ? `审计 ${formatTime(item.audit_checked_at)}` : "无当前规则版本审计"}</span></td>
      <td>${escapeHtml(entityEvidence)}${escapeHtml(ratio)}</td>
      <td><span class="pill status-${taskStatus}">${labels[taskStatus] || taskStatus}</span><span class="completion-reason">${escapeHtml(taskEvidence)}</span></td>
      <td>${escapeHtml(item.description || "—")}</td>
      <td>${escapeHtml(item.action || "—")}</td>
    </tr>`;
  }).join("");
}

async function loadCalendarDetail(dataDate) {
  if (!dataDate) return false;
  try {
    const response = await fetch(`/api/v1/delivery/data-calendar/${dataDate}`);
    if (!response.ok) throw new Error(`日期明细接口返回 ${response.status}`);
    state.calendarDetail = await response.json();
    state.selectedCalendarDate = dataDate;
    state.pages.calendarDetails = 1;
    renderCalendar();
    renderCalendarDetail();
    return true;
  } catch (error) {
    notice(`无法读取数据日期 ${dataDate} 的交付明细：${error.message}`, "load-error");
    return false;
  }
}

async function loadCalendar() {
  state.calendarMonth ||= currentCalendarMonth();
  const { startDate, endDate } = calendarMonthRange(state.calendarMonth);
  try {
    const response = await fetch(`/api/v1/delivery/data-calendar?start_date=${startDate}&end_date=${endDate}`);
    if (!response.ok) throw new Error(`数据日历接口返回 ${response.status}`);
    state.calendar = await response.json();
    const available = state.calendar.days || [];
    const preferred = available.find((item) => item.data_date === shanghaiToday())
      || available.find((item) => item.status === "issue") || available[0];
    if (!available.some((item) => item.data_date === state.selectedCalendarDate)) {
      state.selectedCalendarDate = preferred?.data_date || null;
    }
    renderCalendar();
    if (state.selectedCalendarDate) await loadCalendarDetail(state.selectedCalendarDate);
    clearEndpointError("calendar");
    return true;
  } catch (error) {
    setEndpointError("calendar", error);
    return false;
  }
}

function filteredDeliveryRows() {
  const rows = state.delivery?.items || [];
  const filter = $("deliveryStatusFilter").value;
  if (filter === "attention") return rows.filter((item) => item.attention);
  if (filter === "active") return rows.filter((item) =>
    ["queued", "running", "retrying", "verifying", "unverified"].includes(item.delivery_status));
  if (filter === "upcoming") return rows.filter((item) =>
    ["not_due", "waiting"].includes(item.delivery_status));
  if (filter === "complete") return rows.filter((item) =>
    ["complete", "empty"].includes(item.delivery_status));
  return rows;
}

function renderDelivery() {
  const payload = state.delivery;
  if (!payload) return;
  const summary = payload.summary || {};
  const rows = filteredDeliveryRows();
  const page = pageRows(rows, "delivery");
  const duePercent = Math.round(Number(summary.due_progress_ratio || 0) * 100);
  const totalPercent = Math.round(Number(summary.total_progress_ratio || 0) * 100);
  $("deliveryDueProgress").textContent = `${summary.completed_due ?? 0} / ${summary.due_now ?? 0}`;
  $("deliveryTotalProgress").textContent = `${summary.completed_total ?? 0} / ${summary.total ?? 0}`;
  $("deliveryActiveCount").textContent = Number(summary.queued || 0) + Number(summary.running || 0);
  $("deliveryUnverifiedCount").textContent = summary.unverified ?? 0;
  $("deliveryAttentionCount").textContent = summary.attention ?? 0;
  $("deliveryNextTime").textContent = formatClock(summary.next_scheduled_for);
  $("deliveryDueBar").style.width = `${Math.min(duePercent, 100)}%`;
  $("deliveryTotalBar").style.width = `${Math.min(totalPercent, 100)}%`;
  $("deliveryDuePercent").textContent = `${duePercent}%`;
  $("deliveryTotalPercent").textContent = `${totalPercent}%`;
  $("deliverySummary").textContent =
    `${payload.business_date} · 当前应执行 ${summary.due_now || 0} 项，严格交付 ${summary.completed_due || 0} 项` +
    ` · ${summary.not_due || 0} 项尚未到发布时间 · ${summary.overdue || 0} 项逾期`;
  $("todayTabCount").textContent = summary.attention
    ? `${summary.attention} 项异常`
    : `${summary.completed_due || 0}/${summary.due_now || 0} 已交付`;
  const end = Math.min(page.start + page.rows.length, rows.length);
  $("deliveryResultCount").textContent = rows.length
    ? `显示 ${page.start + 1}–${end}，共 ${rows.length} 项计划`
    : "0 项计划";
  if (!rows.length) {
    $("deliveryRows").innerHTML = '<tr><td colspan="6" class="empty-state">当前筛选下没有交付计划</td></tr>';
    return;
  }
  $("deliveryRows").innerHTML = page.rows.map((item) => {
    const target = item.period_key || item.expected_for || "—";
    const fetched = item.rows_fetched == null ? "—" : Number(item.rows_fetched).toLocaleString();
    const stored = item.rows_inserted == null ? "—" : Number(item.rows_inserted).toLocaleString();
    const finish = item.finished_at ? formatTime(item.finished_at) : "尚未完成";
    const status = item.delivery_status || "pending";
    const source = { dedicated: "专项调度", policy: "策略队列", fanout: "全量扇出" }[item.source_type] || item.source_type;
    const evidence = item.error_message || (
      status === "not_due" ? "尚未到计划发布时间" :
      status === "waiting" ? "已到计划时间，仍在允许交付窗口内" :
      status === "overdue" ? "超过交付截止时间且没有可验证结果" :
      status === "empty" ? "请求已穷尽并验证为空" :
      status === "complete" ? (item.on_time ? "按时通过完整性验证" : "已恢复并通过完整性验证") :
      "任务正在处理或等待完整性证据"
    );
    return `<tr class="${item.attention ? "delivery-row-attention" : ""}">
      <td class="number">${formatClock(item.scheduled_for)}<span class="completion-reason">${source}</span></td>
      <td><span class="api-name">${escapeHtml(item.api_name)}</span><span class="api-title">${escapeHtml(item.title)}</span></td>
      <td><span>${escapeHtml(target)}</span><span class="completion-reason">${labels[item.cadence] || item.cadence}</span></td>
      <td><span class="pill status-${status}">${labels[status] || status}</span><span class="completion-reason">${escapeHtml(evidence)}</span></td>
      <td class="number">${fetched} / ${stored}<span class="completion-reason">获取 / 写入</span></td>
      <td>${finish}<span class="completion-reason">截止 ${formatTime(item.due_at)}</span></td>
    </tr>`;
  }).join("");
}

async function loadDelivery() {
  try {
    const today = shanghaiToday();
    const [response, dataResponse] = await Promise.all([
      fetch("/api/v1/delivery/today"),
      fetch(`/api/v1/delivery/data-calendar/${today}`)
    ]);
    if (!response.ok) throw new Error(`今日交付接口返回 ${response.status}`);
    if (!dataResponse.ok) throw new Error(`今日数据事实接口返回 ${dataResponse.status}`);
    state.delivery = await response.json();
    state.todayDataDetail = await dataResponse.json();
    renderDelivery();
    renderAutomationExplanation();
    clearEndpointError("delivery");
    return true;
  } catch (error) {
    setEndpointError("delivery", error);
    return false;
  }
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

function setSidebarCollapsed(collapsed, persist = true) {
  state.sidebarCollapsed = Boolean(collapsed);
  document.body.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);
  const toggle = $("sidebarToggle");
  const label = state.sidebarCollapsed ? "展开侧栏" : "收起侧栏";
  toggle.setAttribute("aria-expanded", String(!state.sidebarCollapsed));
  toggle.setAttribute("aria-label", label);
  toggle.title = label;
  if (!persist) return;
  try {
    window.localStorage.setItem("claw-quant:sidebar-collapsed", String(state.sidebarCollapsed));
  } catch (_error) {
    // The layout remains usable when local storage is unavailable.
  }
}

function setTheme(theme, persist = true) {
  state.theme = theme === "light" ? "light" : "dark";
  const isDark = state.theme === "dark";
  document.body.classList.toggle("theme-dark", isDark);
  document.querySelector('meta[name="color-scheme"]')?.setAttribute("content", isDark ? "dark" : "light");
  $("themeToggle").setAttribute("aria-pressed", String(isDark));
  $("themeToggle").setAttribute("aria-label", isDark ? "切换浅色模式" : "切换暗黑模式");
  $("themeToggle").title = isDark ? "切换浅色模式" : "切换暗黑模式";
  $("themeLabel").textContent = isDark ? "浅色模式" : "暗黑模式";
  $("themeIcon").textContent = isDark ? "☀" : "☾";
  if (!persist) return;
  try {
    window.localStorage.setItem("claw-quant:theme", state.theme);
  } catch (_error) {
    // Theme switching remains available without persistence.
  }
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
    const retryJobId = unresolved?.job_id || latest.id;
    const canRetry = Boolean(unresolved?.job_id) || (latest.source === "queue" && latest.status === "failed" && !isBatch);
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
        : `<button class="row-action" data-retry="${retryJobId || ""}" ${canRetry ? "" : "disabled"}>重试</button>`}</td>
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
  renderAutomationExplanation();
}

function renderAutomationExplanation() {
  const automated = Number(state.summary?.automated || 0);
  const dailyRequirements = Number(state.todayDataDetail?.summary?.task_total || 0);
  const taskPlans = Number(state.delivery?.summary?.total || 0);
  if (!automated || !state.todayDataDetail || !state.delivery) return;
  const notDaily = Math.max(automated - dailyRequirements, 0);
  $("automationExplanation").textContent =
    `${automated} 个接口具备自动编排能力；今日 ${dailyRequirements} 个接口产生日频数据要求，` +
    `${notDaily} 个属于周/月/季周期或共享同一专项任务，不应每天重复采集。今日共 ${taskPlans} 次任务计划，包含分时采集与 T+1 复核。`;
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
  renderServiceDiagnostics();

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
    <td><span>${escapeHtml(item.action || "—")}</span><div class="health-actions">${item.job_id ? `<button class="row-action" data-health-retry="${Number(item.job_id)}">重试任务 #${Number(item.job_id)}</button>` : ""}${item.partition_details ? `<button class="row-action" data-health-coverage-detail="${escapeHtml(item.dataset || item.resource)}">查看日期</button>` : ""}</div></td>
  </tr>`).join("");
}

function renderServiceDiagnostics() {
  const node = $("serviceDiagnostics");
  const unhealthy = state.services.filter((item) => item.status !== "healthy");
  if (!unhealthy.length) {
    node.className = "service-diagnostics is-healthy";
    node.innerHTML = `<strong>基础服务全部在线</strong><span>调度、Worker、审计与备份心跳均在阈值内。</span>`;
    return;
  }
  node.className = "service-diagnostics has-issues";
  node.innerHTML = unhealthy.map((item) => `<article>
    <div><strong>${escapeHtml(item.label || item.component)}</strong><span>${escapeHtml(item.diagnostic || "服务心跳异常")}</span></div>
    <p>${escapeHtml(item.action || "检查对应容器日志和进程状态")}</p>
  </article>`).join("");
}

async function loadDataHealth() {
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
    state.snapshotGeneratedAt = payload.generated_at;
    clearEndpointError("health");
    return true;
  } catch (error) {
    setEndpointError("health", error);
    return false;
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
    notice(`暂时无法读取采集状态：${error.message}`, "load-error");
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
  const workRange = $("initializationWorkRange");
  $("initializationDetailButton").disabled = !(campaign || latest);
  if (!campaign) {
    $("initializationSummary").textContent = runtime.mode === "daily" && latest
      ? `初始采集 #${latest.initialization_id} 已完成（${latest.history_start} 至 ${latest.history_end}），Scheduler 正在执行日常增量更新。`
      : runtime.mode === "daily"
      ? "当前为日常增量模式；这是升级实例，尚无独立的初始化活动记录。"
      : "尚未执行初始采集；日常调度会保持暂停。";
    $("initializationProgress").classList.add("hidden");
    workRange.classList.add("hidden");
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
  const window = campaign.work_window || {};
  const activeRange = window.active_start && window.active_end
    ? `${window.active_start} → ${window.active_end}`
    : "当前没有已入队的日期任务";
  const materializedRange = window.materialized_start && window.materialized_end
    ? `${window.materialized_start} → ${window.materialized_end}`
    : "无日期型步骤";
  const resources = (window.resources || [])
    .filter((item) => Number(item.queued || 0) + Number(item.running || 0) > 0)
    .map((item) => item.resource)
    .join("、") || "—";
  workRange.innerHTML = `<span><strong>总目标</strong> ${escapeHtml(campaign.history_start)} → ${escapeHtml(campaign.history_end)}</span><span><strong>已生成日期范围</strong> ${escapeHtml(materializedRange)}</span><span><strong>当前工作范围</strong> ${escapeHtml(activeRange)}</span><span><strong>队列</strong> ${Number(window.running || 0).toLocaleString()} 运行 / ${Number(window.queued || 0).toLocaleString()} 等待</span><span><strong>正在处理</strong> ${escapeHtml(resources)}</span>`;
  workRange.classList.remove("hidden");
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
    notice(`暂时无法读取初始化状态：${error.message}`, "load-error");
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
    clearEndpointError("fanout");
    return true;
  } catch (error) {
    setEndpointError("fanout", error);
    return false;
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
  syncCoverageRangeDatasets();
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
      <td class="campaign-actions"><button class="row-action" data-coverage-detail="${escapeHtml(item.dataset)}" data-coverage-status="${status === "gaps" ? "problem" : ""}" ${item.auditable ? "" : "disabled"}>查看日期</button>${item.repairable ? `<button class="row-action" data-coverage-range="${escapeHtml(item.dataset)}">指定补采</button>` : ""}</td>
    </tr>`;
  }).join("");
}

function dateDaysBefore(value, days) {
  const parsed = new Date(`${value}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() - days);
  return parsed.toISOString().slice(0, 10);
}

function selectedCoverageDataset() {
  return state.coverage.find((item) => item.dataset === $("coverageRangeDataset").value);
}

function setCoverageRangeDataset(dataset, forceDates = false) {
  const item = state.coverage.find((candidate) => candidate.dataset === dataset);
  if (!item) return;
  $("coverageRangeDataset").value = dataset;
  const changed = state.coverageRangeDataset !== dataset;
  state.coverageRangeDataset = dataset;
  if (changed || forceDates || !$("coverageRangeStart").value || !$("coverageRangeEnd").value) {
    const end = item.latest?.end_date || new Date().toISOString().slice(0, 10);
    $("coverageRangeEnd").value = end;
    $("coverageRangeStart").value = dateDaysBefore(end, 90);
  }
  $("coverageRangeHint").textContent = item.repairable
    ? `${item.dataset} 支持安全补采。审计异步识别真实缺口；补采只处理该范围内已确认的 missing / partial 日期，写入采用幂等 UPSERT。单次范围最长 10 年。`
    : `${item.dataset} 只能审计，尚无无需猜测参数范围的安全补采器。`;
  $("coverageRangeRepairButton").disabled = !item.repairable;
}

function syncCoverageRangeDatasets() {
  const datasets = state.coverage
    .filter((item) => item.repairable)
    .sort((left, right) => {
      if (left.dataset === "stock_daily") return -1;
      if (right.dataset === "stock_daily") return 1;
      return left.dataset.localeCompare(right.dataset);
    });
  const select = $("coverageRangeDataset");
  const selected = datasets.some((item) => item.dataset === state.coverageRangeDataset)
    ? state.coverageRangeDataset
    : datasets[0]?.dataset;
  select.innerHTML = datasets.map((item) => `<option value="${escapeHtml(item.dataset)}">${escapeHtml(item.dataset)}</option>`).join("");
  if (selected) setCoverageRangeDataset(selected);
}

function coverageRangeValues() {
  const dataset = $("coverageRangeDataset").value;
  const startDate = $("coverageRangeStart").value;
  const endDate = $("coverageRangeEnd").value;
  if (!dataset || !startDate || !endDate) throw new Error("请选择数据集、开始日期和结束日期");
  if (startDate > endDate) throw new Error("开始日期不能晚于结束日期");
  const days = (new Date(`${endDate}T00:00:00Z`) - new Date(`${startDate}T00:00:00Z`)) / 86400000;
  if (days > 3660) throw new Error("单次审计或补采范围不能超过 10 年");
  return { dataset, startDate, endDate };
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
    notice(`暂时无法读取覆盖审计：${error.message}`, "load-error");
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

async function runCoverageRangeAudit() {
  let range;
  try {
    range = coverageRangeValues();
  } catch (error) {
    notice(error.message);
    return;
  }
  if (!window.confirm(`确认审计 ${range.dataset} 在 ${range.startDate} → ${range.endDate} 的日期覆盖？该操作只读取本地业务表，不调用 Tushare。`)) return;
  const button = $("coverageRangeAuditButton");
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/coverage/audits", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `dashboard-range-audit-${Date.now()}`
      },
      body: JSON.stringify({
        datasets: [range.dataset],
        start_date: range.startDate,
        end_date: range.endDate
      })
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || `范围审计返回 ${response.status}`);
    }
    notice(`${range.dataset} 的范围审计已进入队列；完成后“查看已知缺口”会显示准确日期。`);
    window.setTimeout(loadDataHealth, 1500);
  } catch (error) {
    notice(`无法审计指定范围：${error.message}`);
  } finally {
    button.disabled = false;
  }
}

async function runCoverageRangeRepair() {
  let range;
  try {
    range = coverageRangeValues();
  } catch (error) {
    notice(error.message);
    return;
  }
  if (!window.confirm(`确认补采 ${range.dataset} 在 ${range.startDate} → ${range.endDate} 内已经审计确认的缺失或不完整日期？未审计日期、非交易日和正常日期不会生成任务。`)) return;
  const button = $("coverageRangeRepairButton");
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/coverage/repairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset: range.dataset,
        start_date: range.startDate,
        end_date: range.endDate
      })
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error?.message || `范围补采返回 ${response.status}`);
    }
    const body = await response.json();
    notice(body.eligible
      ? `找到 ${body.eligible} 个已确认缺口，新增 ${body.created} 个幂等补采任务；其余任务已存在或正在执行。`
      : "该范围内没有已审计确认的缺口；如尚未审计，请先点击“审计此范围”。");
    await loadDataHealth();
  } catch (error) {
    notice(`无法补采指定范围：${error.message}`);
  } finally {
    button.disabled = false;
  }
}

function renderCoveragePartitions() {
  const partitions = state.dialogData.coveragePartitions;
  const page = pageRows(partitions, "coveragePartitions");
  if (!partitions.length) {
    $("coveragePartitions").innerHTML = '<p class="empty-state">当前条件没有分区记录</p>';
    return;
  }
  $("coveragePartitions").innerHTML = page.rows.map((item) => `
    <div class="partition-item partition-${item.status}">
      <strong>${escapeHtml(item.partition_date)}</strong>
      <span>${coverageLabels[item.status] || item.status}</span>
      <small>${Number(item.row_count).toLocaleString()} 行 · ${item.entity_count ?? "—"}/${item.expected_entity_count ?? "—"} 个标的</small>
    </div>`).join("");
}

async function showCoverageDetail(dataset, options = {}) {
  state.coverageDetailDataset = dataset;
  $("coverageDialogTitle").textContent = `${dataset} · 日期分区`;
  $("coverageDetailStart").value = options.startDate ?? "";
  $("coverageDetailEnd").value = options.endDate ?? "";
  $("coverageDetailStatus").value = options.status ?? "problem";
  $("coveragePartitions").innerHTML = '<p class="empty-state">正在读取…</p>';
  if (!$("coverageDialog").open) $("coverageDialog").showModal();
  await loadCoveragePartitions();
}

async function loadCoveragePartitions() {
  const dataset = state.coverageDetailDataset;
  if (!dataset) return;
  try {
    const query = new URLSearchParams({ limit: "1000" });
    if ($("coverageDetailStart").value) query.set("start_date", $("coverageDetailStart").value);
    if ($("coverageDetailEnd").value) query.set("end_date", $("coverageDetailEnd").value);
    if ($("coverageDetailStatus").value) query.set("status", $("coverageDetailStatus").value);
    const response = await fetch(`/api/v1/coverage/datasets/${encodeURIComponent(dataset)}/partitions?${query}`);
    if (!response.ok) throw new Error(`日期明细返回 ${response.status}`);
    const payload = await response.json();
    state.dialogData.coveragePartitions = payload.partitions || [];
    state.pages.coveragePartitions = 1;
    if (!state.dialogData.coveragePartitions.length) {
      pageRows([], "coveragePartitions");
      const onlyProblems = $("coverageDetailStatus").value === "problem";
      const audit = payload.range_audit;
      const message = audit?.status === "unverified"
        ? "该范围执行过审计，但基础日历不足，暂时不能准确判断缺失。"
        : audit
        ? (onlyProblems ? "该范围已经完整审计，没有发现缺失或截面不完整日期。" : "该范围已经审计，但当前条件没有分区记录。")
        : "尚无一次审计完整覆盖该查询范围，请先在主页面提交范围审计。";
      $("coveragePartitions").innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
    } else {
      renderCoveragePartitions();
    }
  } catch (error) {
    state.dialogData.coveragePartitions = [];
    pageRows([], "coveragePartitions");
    $("coveragePartitions").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  }
}

async function refreshAll() {
  if (state.isRefreshing) return;
  state.isRefreshing = true;
  $("refreshButton").disabled = true;
  renderOperationsBanner();
  try {
    const results = await Promise.all([
      loadOperationalSummary(), loadDelivery(), loadCalendar(), loadDataHealth(), loadFanoutCampaigns()
    ]);
    state.hasLoadedSnapshot = results.every(Boolean);
    if (state.hasLoadedSnapshot) {
      if (state.noticeKind === "load-error") notice("");
      state.lastSuccessfulRefresh = state.snapshotGeneratedAt || new Date().toISOString();
      try {
        window.localStorage.setItem("claw-quant:last-successful-dashboard-refresh", state.lastSuccessfulRefresh);
      } catch (_error) {
        // The health banner still works without persistence.
      }
      const services = state.services.map((item) =>
        `${item.component}:${item.status === "healthy" ? "正常" : "异常"}`
      ).join(" · ");
      $("lastUpdated").textContent = `更新于 ${formatTime(state.lastSuccessfulRefresh)}${services ? ` · ${services}` : ""}`;
    } else {
      $("lastUpdated").textContent = state.lastSuccessfulRefresh
        ? `连接异常 · 上次完整更新 ${formatTime(state.lastSuccessfulRefresh)}`
        : "连接异常 · 尚无完整快照";
    }
  } finally {
    state.isRefreshing = false;
    $("refreshButton").disabled = false;
    renderOperationsBanner();
  }
}

$("refreshButton").addEventListener("click", refreshAll);
$("dispatchButton").addEventListener("click", dispatchLatest);
$("coverageAuditButton").addEventListener("click", runCoverageAudit);
$("coverageRangeDataset").addEventListener("change", (event) => setCoverageRangeDataset(event.target.value, true));
$("coverageRangeInspectButton").addEventListener("click", () => {
  try {
    const range = coverageRangeValues();
    showCoverageDetail(range.dataset, { startDate: range.startDate, endDate: range.endDate, status: "problem" });
  } catch (error) {
    notice(error.message);
  }
});
$("coverageRangeAuditButton").addEventListener("click", runCoverageRangeAudit);
$("coverageRangeRepairButton").addEventListener("click", runCoverageRangeRepair);
$("coverageDetailQueryButton").addEventListener("click", loadCoveragePartitions);
$("initializationActionButton").addEventListener("click", initializationAction);
$("initializationDetailButton").addEventListener("click", showInitializationSteps);
$("dataIssueFilter").addEventListener("change", () => {
  state.pages.health = 1;
  renderDataHealth();
});
$("deliveryStatusFilter").addEventListener("change", () => {
  state.pages.delivery = 1;
  renderDelivery();
});
$("calendarDetailFilter").addEventListener("change", () => {
  state.pages.calendarDetails = 1;
  renderCalendarDetail();
});
$("calendarPrevious").addEventListener("click", () => shiftCalendarMonth(-1));
$("calendarNext").addEventListener("click", () => shiftCalendarMonth(1));
$("calendarToday").addEventListener("click", () => {
  state.calendarMonth = currentCalendarMonth();
  state.selectedCalendarDate = null;
  loadCalendar().then(renderOperationsBanner);
});
$("calendarMonthPicker").addEventListener("change", (event) => {
  if (!event.target.value) return;
  state.calendarMonth = event.target.value;
  state.selectedCalendarDate = null;
  state.calendarDetail = null;
  state.pages.calendarDetails = 1;
  loadCalendar().then(renderOperationsBanner);
});
$("calendarGrid").addEventListener("click", (event) => {
  const button = event.target.closest("[data-calendar-date]");
  if (button) loadCalendarDetail(button.dataset.calendarDate);
});
$("calendarDetailRows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-calendar-retry]");
  if (button && !button.disabled) retryJob(button.dataset.calendarRetry, button);
});
document.querySelector(".console-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (button) activateView(button.dataset.view);
});
document.querySelector(".console-tabs").addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
  const tabs = [...document.querySelectorAll("[data-view]")];
  const current = tabs.indexOf(event.target.closest("[data-view]"));
  if (current < 0) return;
  event.preventDefault();
  const direction = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1;
  const next = tabs[(current + direction + tabs.length) % tabs.length];
  activateView(next.dataset.view);
  next.focus();
});
$("sidebarToggle").addEventListener("click", () => setSidebarCollapsed(!state.sidebarCollapsed));
$("themeToggle").addEventListener("click", () => setTheme(state.theme === "dark" ? "light" : "dark"));
$("dataHealthRows").addEventListener("click", (event) => {
  const retryButton = event.target.closest("[data-health-retry]");
  if (retryButton && !retryButton.disabled) retryJob(retryButton.dataset.healthRetry, retryButton);
  const button = event.target.closest("[data-health-coverage-detail]");
  if (button) showCoverageDetail(button.dataset.healthCoverageDetail);
});
$("operationsIssuesButton").addEventListener("click", () => {
  activateView("overview");
  document.querySelector("[data-view-panel=\"overview\"]")?.scrollIntoView({ behavior: "smooth", block: "start" });
});
window.addEventListener("online", refreshAll);
window.addEventListener("offline", renderOperationsBanner);
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
    delivery: renderDelivery,
    calendarDetails: renderCalendarDetail,
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
  if (button) {
    const item = state.coverage.find((candidate) => candidate.dataset === button.dataset.coverageDetail);
    showCoverageDetail(button.dataset.coverageDetail, {
      startDate: item?.latest?.start_date || "",
      endDate: item?.latest?.end_date || "",
      status: button.dataset.coverageStatus || ""
    });
  }
  const rangeButton = event.target.closest("[data-coverage-range]");
  if (rangeButton && !rangeButton.disabled) {
    setCoverageRangeDataset(rangeButton.dataset.coverageRange, true);
    $("coverageRangeDataset").focus();
  }
});
$("coverageDialogClose").addEventListener("click", () => $("coverageDialog").close());
$("batchDialogClose").addEventListener("click", () => $("batchDialog").close());
$("initializationDialogClose").addEventListener("click", () => $("initializationDialog").close());
$("fanoutDialogClose").addEventListener("click", () => $("fanoutDialog").close());

setTheme(state.theme, false);
setSidebarCollapsed(state.sidebarCollapsed, false);
activateView(state.activeView);
renderOperationsBanner();
refreshAll();
state.timer = window.setInterval(refreshAll, 30000);
