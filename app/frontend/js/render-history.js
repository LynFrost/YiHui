function historyStatusLabel(status) {
  if (status === "all") {
    return "全部";
  }
  if (status === "success") {
    return "生成";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "running") {
    return "生成中";
  }
  if (status === "other") {
    return "其他";
  }
  return status || "未知";
}

function historyFilterLabel(value) {
  if (value === "all") {
    return "全部";
  }
  if (value === "__empty__") {
    return "未记录";
  }
  return value || "未记录";
}

function historyModeLabel(value) {
  if (value === "text_to_image") {
    return "文生图";
  }
  if (value === "image_to_image") {
    return "图生图";
  }
  if (value === "other") {
    return "其他";
  }
  return historyFilterLabel(value);
}

function historyProviderLabel(value) {
  if (value === "all") {
    return "全部";
  }
  if (value === "__empty__") {
    return "未记录";
  }
  const providerName = String(value || "");
  const displayName = providerDisplayName(providerName);
  return displayName || (providerName ? `${providerName}（历史）` : "未记录");
}

function historyTagLabel(value) {
  if (value === "all") {
    return "全部";
  }
  if (value === UNTAGGED_FILTER_VALUE || value === "__empty__") {
    return "无";
  }
  return value || "无";
}

function historySelectOptions(values, selectedValue, labelFn = historyFilterLabel) {
  const uniqueValues = new Set(["all"]);
  for (const value of values || []) {
    uniqueValues.add(String(value || "__empty__"));
  }
  if (selectedValue && !uniqueValues.has(selectedValue)) {
    uniqueValues.add(selectedValue);
  }
  return [...uniqueValues]
    .map((value) => renderSelectedOption(value, labelFn(value), selectedValue || "all"))
    .join("");
}

function historySizeSelectOptions(values, selectedValue) {
  const uniqueValues = new Set(["all"]);
  for (const value of values || []) {
    uniqueValues.add(String(value || "__empty__"));
  }
  if (selectedValue && !uniqueValues.has(selectedValue)) {
    uniqueValues.add(selectedValue);
  }
  return sortPresetSizeFilterValues(uniqueValues)
    .map((value) => renderSelectedOption(
      value,
      value === "all" || value === "__empty__" ? historyFilterLabel(value) : formatPresetSizeLabel(value),
      selectedValue || "all",
    ))
    .join("");
}

function historySelectedTagValue() {
  const tags = Array.isArray(state.history.tags) ? state.history.tags : [];
  return tags[0] || "all";
}

function renderHistoryTagFilterDropdown() {
  const selected = new Set(state.history.tags || []);
  const search = String(state.history.tag_search || "").trim().toLowerCase();
  const hasSelectedTags = (state.history.tags || []).length > 0;
  const selectedTagChips = (state.history.tags || []).map((tag) => `
    <span class="tag-filter-chip">${escapeHtml(tag === UNTAGGED_FILTER_VALUE ? "无" : tag)}</span>
  `).join("");
  const options = (state.history.filterOptions?.tags || [])
    .filter((tag) => tag !== UNTAGGED_FILTER_VALUE)
    .filter((tag) => !search || String(tag).toLowerCase().includes(search));
  const untaggedMatches = !search || "无".includes(search) || UNTAGGED_FILTER_VALUE.includes(search);
  const untaggedOption = untaggedMatches
    ? [{
      label: "无",
      value: UNTAGGED_FILTER_VALUE,
    }]
    : [];
  const optionItems = [
    ...untaggedOption,
    ...options.map((tag) => ({ label: tag, value: tag })),
  ];
  const optionHtml = optionItems.length
    ? optionItems.map((item) => {
      const tag = item.value;
      const isSelected = selected.has(tag);
      return `
        <button
          type="button"
          class="tag-filter-option ${isSelected ? "is-selected" : ""}"
          data-action="toggle-history-filter-tag"
          data-tag="${escapeHtml(tag)}"
        >
          <span>${escapeHtml(item.label)}</span>
          <span class="tag-filter-check">${isSelected ? "✓" : ""}</span>
        </button>
      `;
    }).join("")
    : `<div class="tag-filter-empty">暂无 TAG</div>`;

  return `
    <div class="tag-filter history-tag-filter is-wide">
      <div class="tag-filter-control">
        <button type="button" class="tag-filter-toggle" data-action="toggle-history-tag-filter-dropdown">
          ${hasSelectedTags ? selectedTagChips : `<span class="tag-filter-placeholder">标签筛选</span>`}
        </button>
        ${
          hasSelectedTags
            ? `<button type="button" class="tag-filter-clear" data-action="clear-history-tag-filter" aria-label="清空历史标签筛选">×</button>`
            : ""
        }
      </div>
      ${
        state.history.history_tag_dropdown_open
          ? `
            <div class="tag-filter-menu">
              <input name="history_tag_filter_search" value="${escapeHtml(state.history.tag_search || "")}" placeholder="搜索 TAG">
              <div class="tag-filter-options">
                ${optionHtml}
              </div>
            </div>
          `
          : ""
      }
    </div>
  `;
}

function renderHistoryProviderOptions() {
  const selectedValue = state.history.provider || "all";
  return providerFilterOptionEntries(state.history.filterOptions?.providers || [], selectedValue, { emptyLabel: "未记录" })
    .map((option) => renderSelectedOption(option.value, option.label, selectedValue))
    .join("");
}

function renderHistorySizeOptions() {
  const selectedValue = state.history.size || "all";
  return historySizeSelectOptions(state.history.filterOptions?.sizes || [], selectedValue);
}

function renderHistoryStatusOptions() {
  return [
    ["all", historyStatusLabel("all")],
    ["running", historyStatusLabel("running")],
    ["failed", historyStatusLabel("failed")],
    ["success", historyStatusLabel("success")],
    ["other", historyStatusLabel("other")],
  ]
    .map(([value, label]) => renderSelectedOption(value, label, state.history.status || "all"))
    .join("");
}

function renderHistoryNumberTypeOptions() {
  return [
    ["all", "全部"],
    ["#", "#"],
    ["H", "H"],
  ]
    .map(([value, label]) => renderSelectedOption(value, label, state.history.number_type || "all"))
    .join("");
}

function formatDuration(ms) {
  const value = Number(ms || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }
  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }
  return `${(value / 1000).toFixed(2)} s`;
}

function formatListBlock(value) {
  const items = Array.isArray(value) ? value.filter(Boolean) : [];
  return items.length ? items.join("\n") : "";
}

function formatParamsBlock(value) {
  if (!value || typeof value !== "object") {
    return "{}";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    return "{}";
  }
}

function renderHistoryTextBox(kind, text, extraClass = "", displayText = null) {
  const value = String(text || "");
  const visibleValue = displayText === null ? value : String(displayText || "");
  return `
    <div
      class="history-text-box ${extraClass}"
      tabindex="0"
      role="textbox"
      aria-readonly="true"
      data-history-popover-source
      data-history-popover-kind="${escapeHtml(kind)}"
      data-history-popover-text="${escapeHtml(value)}"
    >${escapeHtml(visibleValue)}</div>
  `;
}

function historyVisibleErrorText(text) {
  return String(text || "")
    .split(/\r?\n/)
    .slice(-3)
    .join("\n");
}

function renderHistoryCopyButton(record, field, label, disabled = false) {
  const disabledAttrs = disabled ? ` disabled aria-disabled="true"` : "";
  return `
    <button
      type="button"
      data-action="copy-history-field"
      data-history-id="${escapeHtml(record.id || "")}"
      data-history-field="${escapeHtml(field)}"
      ${disabledAttrs}
    >${escapeHtml(label)}</button>
  `;
}

function historyAttemptRecords(record) {
  const retries = Array.isArray(record.retry_records) ? record.retry_records : [];
  return [...retries, record].filter(Boolean);
}

function renderHistorySubmitTimes(record) {
  const attempts = historyAttemptRecords(record)
    .map((item, index) => {
      const label = attemptsLabel(index + 1);
      return item.started_at ? `${label} ${formatDate(item.started_at)}` : "";
    })
    .filter(Boolean);
  if (attempts.length <= 1) {
    return "";
  }
  return `<span class="history-retry-times" title="${escapeHtml(attempts.join("\n"))}">${escapeHtml(attempts.join(" / "))}</span>`;
}

function attemptsLabel(index) {
  return `提交${index}`;
}

function historyErrorRecords(record) {
  return historyAttemptRecords(record)
    .map((item) => ({
      id: item.id,
      started_at: item.started_at,
      error_message: item.error_message || "",
    }))
    .filter((item) => String(item.error_message || "").trim());
}

function renderHistoryErrorButtons(record) {
  const errors = historyErrorRecords(record);
  if (!errors.length) {
    return renderHistoryCopyButton(record, "error", "错误", true);
  }
  if (errors.length === 1 && !(record.retry_records || []).length) {
    return renderHistoryCopyButton(record, "error", "错误", false);
  }
  return errors
    .map((error, index) => renderHistoryCopyButton(record, `error:${index}`, `错误${index + 1}`, false))
    .join("");
}

function renderHistoryErrors(record) {
  const errors = historyErrorRecords(record);
  if (!errors.length) {
    return "";
  }
  return `
    <div class="history-error">
      ${errors
        .map((error, index) => {
          const visibleErrorText = historyVisibleErrorText(error.error_message || "");
          const label = errors.length > 1 ? `<div class="history-error-label">错误${index + 1}</div>` : "";
          return `
            <div class="history-error-item">
              ${label}
              ${renderHistoryTextBox("error", error.error_message || "", "history-error-box", visibleErrorText)}
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function historySummaryText(record, params, count) {
  const items = [
    ["模式", historyModeLabel(record.mode || "")],
    ["Provider", historyProviderLabel(record.provider_key || "")],
    ["调用方式", record.openai_call_method || ""],
    ["model", params.model || ""],
    ["尺寸", formatPresetSizeLabel(record.resolved_size || params.resolved_size || "")],
    ["数量", count || ""],
  ];
  return items
    .filter(([, value]) => String(value || "").trim())
    .map(([label, value]) => `${label}：${value}`)
    .join("  ");
}

function renderHistoryRecord(record, index) {
  const params = record.params || {};
  const outputPaths = record.output_image_paths || record.output_image_paths_json || [];
  const summaryRecord = {
    ...record,
    provider_key: params.provider_key || record.provider_key || "",
    adapter: params.adapter || record.adapter || "",
    openai_call_method: params.openai_call_method || record.openai_call_method || "",
    resolved_size: params.resolved_size || record.resolved_size || "",
  };
  const status = record.status || "";
  const statusClass = status ? `is-${status}` : "";
  const count = params.n || params.count || "";
  const promptText = record.prompt || "";
  const paramsText = formatParamsBlock(params);
  const outputText = formatListBlock(outputPaths);
  const summaryText = historySummaryText(summaryRecord, params, count);
  const instanceNumber = Number(record.instance_number || 0);
  const displayNumber = record.instance_number_label || (instanceNumber > 0
    ? `#${String(instanceNumber).padStart(4, "0")}`
    : (record.history_number_label || `H${String(record.history_number || record.display_index || index + 1).padStart(4, "0")}`));

  return `
    <article class="history-record ${escapeHtml(statusClass)}">
      <div class="history-meta">
        <strong>${escapeHtml(displayNumber)}</strong>
        <span class="history-status ${escapeHtml(statusClass)}">${escapeHtml(historyStatusLabel(status))}</span>
        <time>${escapeHtml(formatDate(record.started_at))}</time>
        <span>${escapeHtml(formatDuration(record.duration_ms))}</span>
        <button type="button" data-action="bring-history-to-operation" data-history-id="${escapeHtml(record.id || "")}">带入</button>
        <span class="history-copy-actions">
          ${renderHistoryCopyButton(record, "prompt", "指令")}
          ${renderHistoryCopyButton(record, "params", "参数")}
          ${renderHistoryErrorButtons(record)}
        </span>
        ${renderHistorySubmitTimes(record)}
      </div>
      <div class="history-content-grid">
        <div class="history-prompt-cell">
          ${renderHistoryTextBox("prompt", promptText, "history-prompt-box")}
        </div>
        <div class="history-json-cell">
          ${renderHistoryTextBox("params", paramsText, "history-json-box")}
        </div>
        <div class="history-small-cell">
          <div class="history-facts history-param-summary">${escapeHtml(summaryText)}</div>
          ${
            outputText
              ? `<div
                  class="history-output-paths"
                  data-history-popover-source
                  data-history-popover-kind="output-path"
                  data-history-popover-text="${escapeHtml(outputText)}"
                >输出：${escapeHtml(outputText)}</div>`
              : ""
          }
        </div>
      </div>
      ${renderHistoryErrors(record)}
    </article>
  `;
}

function renderHistoryPage() {
  const totalPages = Math.max(1, Math.ceil((state.history.total || 0) / (state.history.per_page || 50)));
  const currentPage = Math.min(Math.max(1, state.history.page || 1), totalPages);
  const records = state.history.items || [];
  const cleanupRunning = Boolean(state.history.cleanup?.running);
  app.innerHTML = `
    <section class="panel history-panel">
      <div class="panel-header history-top-row">
        <form class="history-toolbar history-inline-toolbar" data-history-toolbar>
          <div class="history-toolbar-main-row">
            <label class="toolbar-field history-search-field">
              <span>提示词</span>
              <input name="history_q" value="${escapeHtml(state.history.q || "")}" placeholder="搜索提示词">
            </label>
            <div class="toolbar-actions">
              <button type="button" data-action="refresh-history">刷新</button>
            </div>
          </div>
          <div class="history-toolbar-filter-row">
            <div class="toolbar-field history-select-field history-tag-filter-field">
              <span>标签</span>
              ${renderHistoryTagFilterDropdown()}
            </div>
            <label class="toolbar-field toolbar-field-small">
              <span>状态</span>
              <select name="history_status">
                ${renderHistoryStatusOptions()}
              </select>
            </label>
            <label class="toolbar-field history-select-field">
              <span>Provider</span>
              <select name="history_provider">
                ${renderHistoryProviderOptions()}
              </select>
            </label>
            <label class="toolbar-field toolbar-field-small">
              <span>尺寸</span>
              <select name="history_size">
                ${renderHistorySizeOptions()}
              </select>
            </label>
            <label class="toolbar-field toolbar-field-small">
              <span>模式</span>
              <select name="history_mode">
                ${historySelectOptions(state.history.filterOptions?.modes || [], state.history.mode || "all", historyModeLabel)}
              </select>
            </label>
            <label class="toolbar-field history-select-field">
              <span>调用方式</span>
              <select name="history_call_method">
                ${historySelectOptions(state.history.filterOptions?.call_methods || [], state.history.call_method || "all")}
              </select>
            </label>
            <label class="toolbar-field history-select-field">
              <span>model</span>
              <select name="history_model">
                ${historySelectOptions(state.history.filterOptions?.models || [], state.history.model || "all")}
              </select>
            </label>
            <label class="toolbar-field toolbar-field-small">
              <span>编号</span>
              <select name="history_number_type">
                ${renderHistoryNumberTypeOptions()}
              </select>
            </label>
          </div>
          <div class="history-toolbar-date-row">
            <div class="history-date-pagination-group">
              <label class="toolbar-field history-date-field">
                <span>开始日期</span>
                <input type="date" name="history_start_date" value="${escapeHtml(state.history.start_date || "")}">
              </label>
              <label class="toolbar-field history-date-field">
                <span>结束日期</span>
                <input type="date" name="history_end_date" value="${escapeHtml(state.history.end_date || "")}">
              </label>
              <label class="toolbar-field toolbar-field-small history-per-page-field">
                <span>每页数量</span>
                <select name="history_per_page">
                  ${renderSelectedOption("10", "10", String(state.history.per_page))}
                  ${renderSelectedOption("20", "20", String(state.history.per_page))}
                  ${renderSelectedOption("50", "50", String(state.history.per_page))}
                  ${renderSelectedOption("100", "100", String(state.history.per_page))}
                  ${renderSelectedOption("200", "200", String(state.history.per_page))}
                </select>
              </label>
            </div>
            <div class="history-right-tools">
              <div class="save-total history-page-summary">
                <span>总数</span>
                <strong>${escapeHtml(state.history.total || 0)}</strong>
                <span>· 第 ${escapeHtml(currentPage)} / ${escapeHtml(totalPages)} 页</span>
              </div>
              <div class="save-pagination history-page-actions">
                <button type="button" data-action="history-page-first" ${currentPage <= 1 ? "disabled" : ""}>首页</button>
                <button type="button" data-action="history-page-prev" ${currentPage <= 1 ? "disabled" : ""}>上一页</button>
                <button type="button" data-action="history-page-next" ${currentPage >= totalPages ? "disabled" : ""}>下一页</button>
                <button type="button" data-action="history-page-last" ${currentPage >= totalPages ? "disabled" : ""}>尾页</button>
              </div>
            </div>
          </div>
        </form>
      </div>
      <div class="message ${state.history.error ? "is-error" : state.history.loading ? "is-loading" : ""}" data-message>
        ${escapeHtml(state.history.error || (state.history.loading ? "加载中" : ""))}
      </div>
      <div class="history-list">
        ${records.length ? records.map((record, index) => renderHistoryRecord(record, index)).join("") : `<div class="empty-state">暂无历史记录</div>`}
      </div>
    </section>
  `;
}


Object.assign(globalThis, {
  historyStatusLabel,
  formatDuration,
  formatListBlock,
  formatParamsBlock,
  renderHistoryTextBox,
  historyVisibleErrorText,
  renderHistoryCopyButton,
  historyAttemptRecords,
  attemptsLabel,
  renderHistorySubmitTimes,
  historyErrorRecords,
  renderHistoryErrorButtons,
  renderHistoryErrors,
  historySummaryText,
  historyFilterLabel,
  historyTagLabel,
  historySelectOptions,
  historySelectedTagValue,
  renderHistoryTagFilterDropdown,
  renderHistoryProviderOptions,
  renderHistorySizeOptions,
  renderHistoryStatusOptions,
  renderHistoryRecord,
  renderHistoryPage,
});
