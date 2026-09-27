function renderTagFilterDropdown() {
  const selected = new Set(state.filters.tags || []);
  const search = String(state.filters.tag_search || "").trim().toLowerCase();
  const hasSelectedTags = (state.filters.tags || []).length > 0;
  const selectedTagChips = (state.filters.tags || []).map((tag) => `
    <span class="tag-filter-chip">${escapeHtml(tag === UNTAGGED_FILTER_VALUE ? "无" : tag)}</span>
  `).join("");
  const options = (state.tagOptions || []).filter((tag) =>
    !search || tag.toLowerCase().includes(search),
  );
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
          data-action="toggle-filter-tag"
          data-tag="${escapeHtml(tag)}"
        >
          <span>${escapeHtml(item.label)}</span>
          <span class="tag-filter-check">${isSelected ? "✓" : ""}</span>
        </button>
      `;
    }).join("")
    : `<div class="tag-filter-empty">暂无 TAG</div>`;

  return `
    <div class="tag-filter">
      <div class="tag-filter-control">
        <button type="button" class="tag-filter-toggle" data-action="toggle-tag-filter-dropdown">
          ${hasSelectedTags ? selectedTagChips : `<span class="tag-filter-placeholder">标签筛选</span>`}
        </button>
      </div>
      ${
        state.filters.tag_dropdown_open
          ? `
            <div class="tag-filter-menu">
              <input name="tag_filter_search" value="${escapeHtml(state.filters.tag_search || "")}" placeholder="搜索 TAG">
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

function renderModeFilterOptions() {
  return `
    ${renderSelectedOption("all", "全部", state.filters.mode_filter)}
    ${renderSelectedOption("text_to_image", "文生图", state.filters.mode_filter)}
    ${renderSelectedOption("image_to_image", "图生图", state.filters.mode_filter)}
    ${renderSelectedOption("has_output", "有输出", state.filters.mode_filter)}
    ${renderSelectedOption("no_output", "无输出", state.filters.mode_filter)}
  `;
}

function renderProviderFilterOptions() {
  const selectedValue = state.filters.provider || "all";
  return providerFilterOptionEntries(state.filters.filterOptions?.providers || [], selectedValue)
    .map((option) => renderSelectedOption(option.value, option.label, selectedValue))
    .join("");
}

function renderSaveStatusFilterDropdown() {
  const selectedStatuses = normalizeSavedStatuses(state.filters.statuses, state.filters.status);
  const selected = new Set(selectedStatuses);
  const options = [
    { value: "all", label: saveStatusFilterLabel("all") },
    { value: "running", label: saveStatusFilterLabel("running") },
    { value: "prepared", label: saveStatusFilterLabel("prepared") },
    { value: "failed", label: saveStatusFilterLabel("failed") },
    { value: "generated", label: saveStatusFilterLabel("generated") },
    { value: "other", label: saveStatusFilterLabel("other") },
  ];
  const chips = selectedStatuses.map((status) => `
    <span class="tag-filter-chip">${escapeHtml(saveStatusFilterLabel(status))}</span>
  `).join("");
  const optionHtml = options.map(({ value, label }) => {
    const isSelected = value === "all" ? selectedStatuses.length === 0 : selected.has(value);
    return `
      <button
        type="button"
        class="tag-filter-option ${isSelected ? "is-selected" : ""}"
        data-action="toggle-save-status-filter"
        data-status="${escapeHtml(value)}"
      >
        <span>${escapeHtml(label)}</span>
        <span class="tag-filter-check">${isSelected ? "✓" : ""}</span>
      </button>
    `;
  }).join("");

  return `
    <div class="tag-filter save-status-filter">
      <div class="tag-filter-control">
        <button type="button" class="tag-filter-toggle" data-action="toggle-save-status-filter-dropdown">
          ${selectedStatuses.length ? chips : `<span class="tag-filter-placeholder">全部</span>`}
        </button>
      </div>
      ${
        state.filters.status_dropdown_open
          ? `
            <div class="tag-filter-menu save-status-filter-menu">
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

function renderSaveStatusFilterOptions() {
  return [
    ["all", saveStatusFilterLabel("all")],
    ["running", saveStatusFilterLabel("running")],
    ["prepared", saveStatusFilterLabel("prepared")],
    ["failed", saveStatusFilterLabel("failed")],
    ["generated", saveStatusFilterLabel("generated")],
    ["other", saveStatusFilterLabel("other")],
  ];
}

function saveStatusFilterLabel(value) {
  if (value === "all") {
    return "全部";
  }
  if (value === "prepared") {
    return "准备";
  }
  if (value === "generated") {
    return "生成";
  }
  if (value === "failed") {
    return "失败";
  }
  if (value === "running") {
    return "生成中";
  }
  if (value === "other") {
    return "其他";
  }
  return value || "未记录";
}

function saveFilterLabel(value) {
  if (value === "all") {
    return "全部";
  }
  if (value === "__empty__") {
    return "未记录";
  }
  return value || "未记录";
}

function renderSaveFilterOptions(values, selectedValue) {
  const uniqueValues = new Set(["all"]);
  for (const value of values || []) {
    uniqueValues.add(String(value || "__empty__"));
  }
  if (selectedValue && !uniqueValues.has(selectedValue)) {
    uniqueValues.add(selectedValue);
  }
  return [...uniqueValues]
    .map((value) => renderSelectedOption(value, saveFilterLabel(value), selectedValue || "all"))
    .join("");
}

function renderSaveSizeFilterOptions(values, selectedValue) {
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
      value === "all" || value === "__empty__" ? saveFilterLabel(value) : formatPresetSizeLabel(value),
      selectedValue || "all",
    ))
    .join("");
}

function currentPageSelectableIds() {
  return (state.instances || [])
    .filter((item) => !item.pending && item.generation_status !== "running")
    .map((item) => String(item.id));
}

function runningInstanceKey(item) {
  const taskId = item?.generation_task_id || item?.task_id || "";
  const outputIndex = item?.generation_output_index || item?.output_index || 1;
  return taskId ? `${taskId}:${outputIndex}` : "";
}

function pendingMergeKey(item) {
  return runningInstanceKey(item);
}

function startedAtMsFromIso(value) {
  const timestamp = Date.parse(value || "");
  if (!Number.isFinite(timestamp)) {
    return performance.now();
  }
  return performance.now() - Math.max(0, Date.now() - timestamp);
}

function pendingDisplayTime(item) {
  const values = [
    item?.generation_started_at,
    item?.created_at,
  ];
  for (const value of values) {
    const timestamp = Date.parse(value || "");
    if (Number.isFinite(timestamp)) {
      return timestamp;
    }
  }
  const startedAtMs = Number.parseFloat(item?.started_at_ms || "");
  if (Number.isFinite(startedAtMs)) {
    return Date.now() - Math.max(0, performance.now() - startedAtMs);
  }
  return 0;
}

function comparePendingInstancesForDisplay(left, right) {
    const timeDelta = pendingDisplayTime(right) - pendingDisplayTime(left);
    if (timeDelta) {
      return timeDelta;
    }
    const rightKey = runningInstanceKey(right);
    const leftKey = runningInstanceKey(left);
    return rightKey.localeCompare(leftKey, "zh-Hans-CN", { numeric: true });
}

function sortPendingInstancesForDisplay(items) {
  return [...(items || [])].sort(comparePendingInstancesForDisplay);
}

function mergePendingWithInstances(pendingInstances, realInstances) {
  const cancellingIds = state.cancellingGenerationTaskIds instanceof Set
    ? state.cancellingGenerationTaskIds
    : new Set();
  const pendingByKey = new Map();
  const mergedPending = [];
  for (const pending of pendingInstances || []) {
    const key = pendingMergeKey(pending);
    if (key) {
      pendingByKey.set(key, pending);
    }
  }
  const consumedKeys = new Set();
  const normalInstances = [];
  for (const instance of realInstances || []) {
    if (instance.generation_status === "running") {
      const key = pendingMergeKey(instance);
      const pending = key ? pendingByKey.get(key) : null;
      if (pending) {
        if (key && pending.started_at_ms) {
          state.pendingStartedAtByKey.set(key, pending.started_at_ms);
        }
        consumedKeys.add(key);
        mergedPending.push({
          ...pending,
          ...instance,
          pending: true,
          cancelling: cancellingIds.has(String(instance.generation_task_id || pending.generation_task_id || pending.task_id || ""))
            || Boolean(pending.cancelling),
          started_at_ms: pending.started_at_ms || startedAtMsFromIso(instance.generation_started_at),
        });
      } else {
        const startedAtMs = key && state.pendingStartedAtByKey.has(key)
          ? state.pendingStartedAtByKey.get(key)
          : startedAtMsFromIso(instance.generation_started_at);
        if (key) {
          state.pendingStartedAtByKey.set(key, startedAtMs);
        }
        mergedPending.push({
          ...instance,
          pending: true,
          cancelling: cancellingIds.has(String(instance.generation_task_id || instance.task_id || "")),
          started_at_ms: startedAtMs,
        });
      }
    } else {
      normalInstances.push(instance);
    }
  }
  for (const pending of pendingInstances || []) {
    const key = pendingMergeKey(pending);
    if (!key || !consumedKeys.has(key)) {
      mergedPending.push(pending);
    }
  }
  return [...sortPendingInstancesForDisplay(mergedPending), ...normalInstances];
}

function renderPendingProcessInstances(pendingInstances) {
  return mergePendingWithInstances(
    (pendingInstances || []).filter((item) => !Number.isFinite(Number(item?.id))),
    [],
  );
}

function renderBatchToolbar() {
  const isThumbnailView = state.saveViewMode === "thumbnail";
  const selectedCount = state.selectedInstanceIds?.size || 0;
  const selectableCount = currentPageSelectableIds().length;
  const disabled = selectedCount <= 0 ? "disabled" : "";
  const undoDisabled = (state.undoStack || []).length ? "" : "disabled";
  const redoDisabled = (state.redoStack || []).length ? "" : "disabled";
  return `
    <div class="batch-toolbar" data-batch-toolbar>
      <button type="button" data-action="select-current-page" ${selectableCount ? "" : "disabled"}>全选</button>
      <button type="button" data-action="clear-selection" ${disabled}>取消</button>
      <span class="batch-count">已选 ${escapeHtml(selectedCount)}</span>
      <button type="button" data-action="batch-add-tags" ${disabled}>添加标签</button>
      <button type="button" data-action="batch-move-instances" ${disabled}>移动</button>
      <button type="button" class="danger" data-action="batch-delete-instances" ${disabled}>删除</button>
      <button type="button" data-action="batch-submit-instances" ${disabled}>提交</button>
      <button type="button" data-action="batch-copy-instances" ${disabled}>复制</button>
      <button type="button" class="thumbnail-view-button ${isThumbnailView ? "is-active" : ""}" data-action="toggle-thumbnail-view">${isThumbnailView ? "列表" : "缩略图"}</button>
      <button type="button" data-action="path-replace">路径替换</button>
      <div class="save-toolbar-pagination">
        <button type="button" class="undo-redo-button" data-action="undo-last-action" ${undoDisabled}>撤销</button>
        <button type="button" class="undo-redo-button" data-action="redo-last-action" ${redoDisabled}>重做</button>
        <span class="save-total">总数 <strong>${escapeHtml(state.total || 0)}</strong></span>
        <button type="button" data-action="save-page-first" ${state.filters.page <= 1 ? "disabled" : ""}>首页</button>
        <button type="button" data-action="save-page-prev" ${state.filters.page <= 1 ? "disabled" : ""}>上一页</button>
        <span>第 ${escapeHtml(state.filters.page || 1)} / ${escapeHtml(Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50))))} 页</span>
        <button type="button" data-action="save-page-next" ${(state.filters.page || 1) >= Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50))) ? "disabled" : ""}>下一页</button>
        <button type="button" data-action="save-page-last" ${(state.filters.page || 1) >= Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50))) ? "disabled" : ""}>尾页</button>
      </div>
    </div>
  `;
}

function renderInstanceThumbnailTile(instance) {
  const pending = Boolean(instance.pending);
  const selectable = !pending && instance.generation_status !== "running";
  const id = String(instance.id || "");
  const selected = selectable && state.selectedInstanceIds?.has(id);
  const path = instance.output_image_path || "";
  const failed = instance.generation_status === "failed";
  const pendingKey = pending ? runningInstanceKey(instance) : "";
  const pendingStartMs = pending
    ? (instance.started_at_ms || state.pendingStartedAtByKey.get(pendingKey) || performance.now())
    : "";
  const stateClass = pending
    ? "is-pending"
    : path
      ? "has-image"
      : failed
        ? "is-failed"
        : "is-empty";
  const selectedClass = selected ? " is-selected" : "";
  const selectionControl = selectable
    ? `
      <label class="thumbnail-select" data-skip-batch-save="true" title="选择实例" aria-label="选择实例">
        <input type="checkbox" data-action="toggle-select-instance" data-id="${escapeHtml(id)}" ${selected ? "checked" : ""}>
      </label>
    `
    : "";
  const pendingAttrs = pending
    ? ` data-pending-elapsed-key="${escapeHtml(pendingKey)}" data-pending-start-ms="${escapeHtml(pendingStartMs)}"`
    : "";
  const fallbackText = pending
    ? pendingStatusText(instance, pendingStartMs)
    : failed
      ? "失败"
      : "无输出";

  if (!path) {
    return `
      <div class="save-thumbnail-tile ${stateClass}${selectedClass}" aria-label="${escapeHtml(fallbackText)}">
        ${selectionControl}
        <span${pendingAttrs}>${escapeHtml(fallbackText)}</span>
      </div>
    `;
  }

  return `
    <div class="save-thumbnail-tile ${stateClass}${selectedClass}">
      ${selectionControl}
      <button
        type="button"
        class="thumbnail-image-button"
        data-image-path="${escapeHtml(path)}"
        data-lazy-image-path="${escapeHtml(path)}"
        aria-label="查看输出图"
      >
        <img src="${escapeHtml(thumbnailUrl(path))}" alt="${escapeHtml(path)}" loading="lazy" decoding="async">
      </button>
    </div>
  `;
}

function renderThumbnailSaveGrid(processInstances, formalInstances) {
  const items = [...(processInstances || []), ...(formalInstances || [])];
  const tiles = items.map((instance) => renderInstanceThumbnailTile(instance)).join("");
  return `
    <div class="save-thumbnail-grid">
      ${tiles || `<div class="empty-state">暂无实例</div>`}
    </div>
  `;
}

function renderSaveArea() {
  const totalPages = Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50)));
  const layout = currentSaveLayout();
  const isThumbnailView = state.saveViewMode === "thumbnail";
  const pendingInstances = state.pendingInstances || [];
  const realInstances = state.instances || [];
  // 已有数据库实例的生成中状态保持在原列表位置；底部只显示没有稳定实例 ID 的临时占位。
  const formalInstances = realInstances;
  const processInstances = renderPendingProcessInstances(pendingInstances);
  processInstances.sort(comparePendingInstancesForDisplay);
  const processCards = processInstances.map((instance) => renderInstanceCard({
    ...instance,
    display_index: "",
  })).join("");
  // 生成中实例不参与正式分页，只追加在当前页底部，避免挤掉已保存实例和编号。
  const cards = formalInstances.map((instance) => renderInstanceCard(instance)).join("");
  const needsPlaceholder = layout === "double" && formalInstances.length % 2 === 1;

  return `
    <section class="save-area save-layout-${escapeHtml(layout)} ${isThumbnailView ? "is-thumbnail-view" : ""}" data-save-area>
      <form class="save-toolbar" data-save-toolbar>
        <div class="save-toolbar-main-row">
          <label class="toolbar-field save-search-field">
            <span>搜索提示词</span>
            <div class="toolbar-input-row">
              <div class="toolbar-search-wrap">
                <input name="q" value="${escapeHtml(state.filters.q)}">
                <button type="button" class="prompt-clear search-prompt-clear" data-action="clear-prompt-search" data-skip-batch-save="true" aria-label="清空搜索提示词">×</button>
              </div>
              <button type="button" data-action="apply-prompt-search">搜索</button>
            </div>
          </label>
          <label class="toolbar-field toolbar-field-sort">
            <span>排序</span>
            <select name="sort">
              ${renderSelectedOption("number_desc", "编号 从大到小", state.filters.sort)}
              ${renderSelectedOption("number_asc", "编号 从小到大", state.filters.sort)}
              ${renderSelectedOption("created_desc", "最新优先", state.filters.sort)}
              ${renderSelectedOption("created_asc", "最早优先", state.filters.sort)}
              ${renderSelectedOption("prompt_asc", "提示词 A-Z", state.filters.sort)}
              ${renderSelectedOption("prompt_desc", "提示词 Z-A", state.filters.sort)}
              ${renderSelectedOption("provider_asc", "Provider A-Z", state.filters.sort)}
              ${renderSelectedOption("provider_desc", "Provider Z-A", state.filters.sort)}
            </select>
          </label>
          <label class="toolbar-field toolbar-field-small">
            <span>每页数量</span>
            <select name="per_page">
              ${renderSelectedOption("10", "10", String(state.filters.per_page))}
              ${renderSelectedOption("20", "20", String(state.filters.per_page))}
              ${renderSelectedOption("50", "50", String(state.filters.per_page))}
              ${renderSelectedOption("100", "100", String(state.filters.per_page))}
              ${renderSelectedOption("200", "200", String(state.filters.per_page))}
            </select>
          </label>
          <label class="toolbar-field toolbar-field-layout">
            <span>显示方式</span>
            <select name="save_layout" ${isThumbnailView ? "disabled" : ""}>
              ${renderSelectedOption("single", "单列", layout)}
              ${renderSelectedOption("double", "双列", layout)}
            </select>
          </label>
        </div>
        <div class="save-toolbar-filter-row">
          <div class="toolbar-field toolbar-field-tags">
            <span>
              标签
              ${(state.filters.tags || []).length ? `<button type="button" class="filter-label-clear" data-action="clear-tag-filter" data-skip-batch-save="true" aria-label="清空标签筛选">×</button>` : ""}
            </span>
            <div class="toolbar-input-row">
              ${renderTagFilterDropdown()}
            </div>
          </div>
          <div class="toolbar-field toolbar-field-small">
            <span>
              状态
              ${normalizeSavedStatuses(state.filters.statuses, state.filters.status).length ? `<button type="button" class="filter-label-clear" data-action="clear-save-status-filter" data-skip-batch-save="true" aria-label="清空状态筛选">×</button>` : ""}
            </span>
            <input type="hidden" name="status" value="${escapeHtml((state.filters.statuses || [])[0] || "all")}">
            ${renderSaveStatusFilterDropdown()}
          </div>
          <label class="toolbar-field toolbar-field-provider-filter">
            <span>Provider</span>
            <select name="provider">
              ${renderProviderFilterOptions()}
            </select>
          </label>
          <label class="toolbar-field toolbar-field-small">
            <span>尺寸</span>
            <select name="size">
              ${renderSaveSizeFilterOptions(state.filters.filterOptions?.sizes || [], state.filters.size || "all")}
            </select>
          </label>
          <label class="toolbar-field toolbar-field-mode-filter">
            <span>模式</span>
            <select name="mode_filter">
              ${renderModeFilterOptions()}
            </select>
          </label>
          <label class="toolbar-field toolbar-field-call-method">
            <span>调用方式</span>
            <select name="call_method">
              ${renderSaveFilterOptions(state.filters.filterOptions?.call_methods || [], state.filters.call_method || "all")}
            </select>
          </label>
          <label class="toolbar-field toolbar-field-model">
            <span>model</span>
            <select name="model">
              ${renderSaveFilterOptions(state.filters.filterOptions?.models || [], state.filters.model || "all")}
            </select>
          </label>
        </div>
      </form>
      ${renderNodeControls()}
      ${renderBatchToolbar()}
      ${
        isThumbnailView
          ? renderThumbnailSaveGrid(processInstances, formalInstances)
          : ""
      }
      ${
        isThumbnailView
          ? ""
          : `
            <div class="save-list ${saveLayoutClass()}">
              ${cards || `<div class="empty-state">暂无实例</div>`}
              ${needsPlaceholder ? `<div class="instance-card instance-card-placeholder" aria-hidden="true"></div>` : ""}
            </div>
          `
      }
      ${
        !isThumbnailView && processInstances.length
          ? `
            <section class="pending-section">
              <div class="pending-list ${saveLayoutClass()}">
                ${processCards}
              </div>
            </section>
          `
          : ""
      }
    </section>
  `;
}


Object.assign(globalThis, {
  renderTagFilterDropdown,
  renderModeFilterOptions,
  renderProviderFilterOptions,
  renderSaveStatusFilterDropdown,
  renderSaveStatusFilterOptions,
  saveStatusFilterLabel,
  saveFilterLabel,
  renderSaveFilterOptions,
  renderSaveSizeFilterOptions,
  currentPageSelectableIds,
  runningInstanceKey,
  pendingMergeKey,
  pendingDisplayTime,
  comparePendingInstancesForDisplay,
  sortPendingInstancesForDisplay,
  mergePendingWithInstances,
  renderBatchToolbar,
  renderInstanceThumbnailTile,
  renderThumbnailSaveGrid,
  renderSaveArea,
});
