function ensureSelectedInstanceIds() {
  if (!(state.selectedInstanceIds instanceof Set)) {
    state.selectedInstanceIds = new Set();
  }
  return state.selectedInstanceIds;
}

function clearCurrentPageSelection() {
  ensureSelectedInstanceIds().clear();
  resetSelectionAnchor();
}

function resetSelectionAnchor() {
  state.lastSelectedInstanceId = "";
}

function pruneSelectionToCurrentPage() {
  const selected = ensureSelectedInstanceIds();
  const currentIds = new Set(currentPageSelectableIds());
  for (const id of [...selected]) {
    if (!currentIds.has(String(id))) {
      selected.delete(id);
    }
  }
  if (state.lastSelectedInstanceId && !currentIds.has(String(state.lastSelectedInstanceId))) {
    resetSelectionAnchor();
  }
}

function selectRangeToInstance(instanceId) {
  const id = String(instanceId || "");
  const selectableIds = currentPageSelectableIds();
  const anchor = String(state.lastSelectedInstanceId || "");
  const targetIndex = selectableIds.indexOf(id);
  const anchorIndex = selectableIds.indexOf(anchor);
  if (targetIndex < 0 || anchorIndex < 0) {
    return false;
  }
  const selected = ensureSelectedInstanceIds();
  const start = Math.min(anchorIndex, targetIndex);
  const end = Math.max(anchorIndex, targetIndex);
  for (const rangeId of selectableIds.slice(start, end + 1)) {
    selected.add(String(rangeId));
  }
  return true;
}

function toggleSelectInstance(instanceId, options = {}) {
  const id = String(instanceId || "");
  if (!id) {
    return;
  }
  const selectableIds = currentPageSelectableIds();
  if (!selectableIds.includes(id)) {
    return;
  }
  const selected = ensureSelectedInstanceIds();
  if (options.shiftKey && selectRangeToInstance(id)) {
    state.lastSelectedInstanceId = id;
    renderManagerIfActive();
    return;
  }
  if (selected.has(id)) {
    selected.delete(id);
  } else {
    selected.add(id);
  }
  state.lastSelectedInstanceId = id;
  renderManagerIfActive();
}

function toggleSelectInstanceFromZone(instanceId, options = {}) {
  toggleSelectInstance(instanceId, options);
}

function selectCurrentPageInstances() {
  const selected = ensureSelectedInstanceIds();
  const ids = currentPageSelectableIds();
  for (const id of ids) {
    selected.add(String(id));
  }
  state.lastSelectedInstanceId = ids.length ? String(ids[ids.length - 1]) : "";
  renderManagerIfActive();
}

function selectedInstanceIds() {
  return [...ensureSelectedInstanceIds()]
    .map((id) => Number.parseInt(id, 10))
    .filter((id) => Number.isFinite(id) && id > 0);
}

function hasSelectedInstances() {
  return ensureSelectedInstanceIds().size > 0;
}

function cloneManagerSessionState() {
  return {
    filters: JSON.parse(JSON.stringify(state.filters || {})),
    nodeFilter: JSON.parse(JSON.stringify(state.nodeFilter || { path: [{ selection: "all", node_id: null }] })),
    settingsSaveLayout: state.settings?.save_layout || "double",
    instances: JSON.parse(JSON.stringify(state.instances || [])),
    nodes: JSON.parse(JSON.stringify(state.nodes || [])),
    tagOptions: [...(state.tagOptions || [])],
    total: state.total || 0,
    selectedIds: [...ensureSelectedInstanceIds()],
    pendingInstances: JSON.parse(JSON.stringify(state.pendingInstances || [])),
  };
}

async function createSessionSnapshot() {
  const data = await api("/api/session-snapshot", { method: "POST" });
  return {
    backend: data.snapshot,
    ui: cloneManagerSessionState(),
  };
}

async function restoreSessionSnapshot(snapshot) {
  if (!snapshot?.backend) {
    throw new Error("会话快照无效");
  }
  await api("/api/session-restore", {
    method: "POST",
    body: { snapshot: snapshot.backend },
  });
  const ui = snapshot.ui || {};
  state.filters = JSON.parse(JSON.stringify(ui.filters || state.filters));
  state.nodeFilter = JSON.parse(JSON.stringify(ui.nodeFilter || state.nodeFilter));
  state.pendingInstances = JSON.parse(JSON.stringify(ui.pendingInstances || []));
  state.total = ui.total || 0;
  state.tagOptions = [...(ui.tagOptions || state.tagOptions || [])];
  await loadNodes();
  await loadInstances();
  await loadTags();
  if (state.settings) {
    state.settings.save_layout = ui.settingsSaveLayout || state.settings.save_layout || "double";
  }
  state.editing.clear();
  state.selectedInstanceIds = new Set((ui.selectedIds || []).map((id) => String(id)));
  pruneSelectionToCurrentPage();
  persistUiState();
  renderManagerIfActive();
}

async function pushUndoSnapshot(label) {
  const snapshot = await createSessionSnapshot();
  state.undoStack = [...(state.undoStack || []), { label, snapshot }];
  state.redoStack = [];
}

async function runUndoableAction(label, action) {
  const beforeSnapshot = await createSessionSnapshot();
  const result = await action();
  state.undoStack = [...(state.undoStack || []), { label, snapshot: beforeSnapshot }];
  state.redoStack = [];
  return result;
}

async function undoLastAction() {
  const undoStack = state.undoStack || [];
  if (!undoStack.length) {
    return;
  }
  const current = await createSessionSnapshot();
  const entry = undoStack[undoStack.length - 1];
  state.undoStack = undoStack.slice(0, -1);
  state.redoStack = [...(state.redoStack || []), { label: entry.label, snapshot: current }];
  await restoreSessionSnapshot(entry.snapshot);
  setMessage(`已撤销：${entry.label}`, "success");
}

async function redoLastAction() {
  const redoStack = state.redoStack || [];
  if (!redoStack.length) {
    return;
  }
  const current = await createSessionSnapshot();
  const entry = redoStack[redoStack.length - 1];
  state.redoStack = redoStack.slice(0, -1);
  state.undoStack = [...(state.undoStack || []), { label: entry.label, snapshot: current }];
  await restoreSessionSnapshot(entry.snapshot);
  setMessage(`已还原：${entry.label}`, "success");
}

function splitTagText(value) {
  return String(value || "")
    .split(/[,，;；\n]/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function chooseBatchTags(title, actionLabel) {
  return new Promise((resolve) => {
    document.querySelector("[data-batch-tag-dialog]")?.remove();
    const selected = new Set();
    const dialog = document.createElement("div");
    dialog.className = "modal-backdrop";
    dialog.dataset.batchTagDialog = "true";
    dialog.dataset.skipBatchSave = "true";

    const renderSelected = () => {
      const selectedBox = dialog.querySelector("[data-selected-tags]");
      if (!selectedBox) {
        return;
      }
      selectedBox.innerHTML = [...selected]
        .map((tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`)
        .join("") || `<span class="tag-placeholder">未选择 TAG</span>`;
      dialog.querySelectorAll("[data-batch-tag-choice]").forEach((button) => {
        button.classList.toggle("is-selected", selected.has(button.dataset.tag || ""));
      });
    };

    const close = (result = []) => {
      dialog.remove();
      resolve(result);
    };

    const tagButtons = (state.tagOptions || [])
      .map((tag) => `
        <button type="button" class="tag-selector-option" data-batch-tag-choice="true" data-tag="${escapeHtml(tag)}">
          ${escapeHtml(tag)}
        </button>
      `)
      .join("") || `<div class="tag-selector-empty">暂无已有 TAG</div>`;

    dialog.innerHTML = `
      <div class="modal batch-tag-modal" role="dialog" aria-modal="true">
        <div class="modal-title-row">
          <h2>${escapeHtml(title)}</h2>
          <span>已选 ${escapeHtml(selectedInstanceIds().length)} 条</span>
        </div>
        <div class="batch-tag-selected" data-selected-tags></div>
        <div class="tag-selector-menu is-static">
          ${tagButtons}
        </div>
        <label class="field">
          <span>新加 TAG</span>
          <input data-batch-new-tags placeholder="多个 TAG 可用逗号分隔">
        </label>
        <div class="actions">
          <button type="button" class="primary" data-batch-confirm>${escapeHtml(actionLabel)}</button>
          <button type="button" data-batch-cancel>取消</button>
        </div>
      </div>
    `;
    document.body.appendChild(dialog);
    renderSelected();

    dialog.addEventListener("click", (event) => {
      if (event.target === dialog || event.target.closest("[data-batch-cancel]")) {
        close([]);
        return;
      }
      const choice = event.target.closest("[data-batch-tag-choice]");
      if (choice) {
        const tag = choice.dataset.tag || "";
        if (selected.has(tag)) {
          selected.delete(tag);
        } else if (tag) {
          selected.add(tag);
        }
        renderSelected();
        return;
      }
      if (event.target.closest("[data-batch-confirm]")) {
        const inputTags = splitTagText(dialog.querySelector("[data-batch-new-tags]")?.value || "");
        close([...new Set([...selected, ...inputTags])]);
      }
    });
    dialog.querySelector("[data-batch-new-tags]")?.focus();
  });
}

async function batchAddTags() {
  const ids = selectedInstanceIds();
  if (!ids.length) {
    return;
  }
  const tags = await chooseBatchTags("批量添加标签", "添加");
  if (!tags.length) {
    return;
  }
  try {
    setMessage("");
    await runUndoableAction("批量添加标签", async () => {
      await api("/api/instances/batch/tags/add", {
        method: "POST",
        body: { ids, tags },
      });
    });
    clearCurrentPageSelection();
    await refreshInstances("已批量添加标签", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function batchRemoveTags() {
  const ids = selectedInstanceIds();
  if (!ids.length) {
    return;
  }
  const tags = await chooseBatchTags("批量删除标签", "删除");
  if (!tags.length) {
    return;
  }
  try {
    setMessage("");
    await runUndoableAction("批量删除标签", async () => {
      await api("/api/instances/batch/tags/remove", {
        method: "POST",
        body: { ids, tags },
      });
    });
    clearCurrentPageSelection();
    await refreshInstances("已批量删除标签", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function batchDeleteInstances() {
  const ids = selectedInstanceIds();
  if (!ids.length) {
    return;
  }
  const confirmed = window.confirm(`确认删除已选 ${ids.length} 个实例？\n这只会删除软件数据库中的实例记录，不会删除电脑上的图片文件。`);
  if (!confirmed) {
    return;
  }
  try {
    setMessage("");
    await runUndoableAction("批量删除实例", async () => {
      await api("/api/instances/batch/delete", {
        method: "POST",
        body: { ids },
      });
    });
    clearCurrentPageSelection();
    state.editing.clear();
    await refreshInstances("已批量删除", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function batchMoveInstances() {
  const ids = selectedInstanceIds();
  if (!ids.length) {
    return;
  }
  const nodeId = await chooseMoveNode("批量移动");
  if (nodeId === undefined) {
    return;
  }
  try {
    setMessage("");
    await runUndoableAction("批量移动实例", async () => {
      await api("/api/instances/batch/move", {
        method: "POST",
        body: { ids, node_id: nodeId },
      });
    });
    clearCurrentPageSelection();
    await refreshInstances("已批量移动", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function copyInstanceToPreparedPayload(item) {
  const params = item?.generation_params && typeof item.generation_params === "object"
    ? { ...item.generation_params }
    : {};
  const inputImagePaths = Array.isArray(item?.input_image_paths)
    ? item.input_image_paths.filter(Boolean)
    : [];
  return {
    prompt: item?.prompt || "",
    mode: item?.mode || (inputImagePaths.length ? "image_to_image" : "text_to_image"),
    source: "manual",
    provider: item?.provider || params.provider_key || "",
    node_id: item?.node_id ?? null,
    generation_path: item?.generation_path || "",
    generation_size: item?.generation_size || params.resolved_size || params.size || "",
    generation_params: {
      ...params,
      output_image_paths: [],
    },
    output_image_path: "",
    generation_status: "ready",
    generation_task_id: "",
    generation_output_index: 1,
    generation_error: "",
    generation_started_at: "",
    generation_finished_at: "",
    input_image_paths: inputImagePaths,
    tags: Array.isArray(item?.tags) ? [...item.tags] : [],
  };
}

async function batchCopyInstances() {
  const ids = selectedInstanceIds();
  if (!ids.length) {
    return;
  }
  const items = ids
    .map((id) => instanceById(id))
    .filter((item) => item && item.generation_status !== "running");
  const skipped = ids.length - items.length;
  if (!items.length) {
    setMessage("没有可复制的实例", "info");
    return;
  }
  try {
    setMessage("");
    await runUndoableAction("批量复制实例", async () => {
      await api("/api/instances/bulk", {
        method: "POST",
        body: {
          items: items.map((item) => copyInstanceToPreparedPayload(item)),
        },
      });
    });
    state.filters.sort = "created_desc";
    state.filters.page = 1;
    clearCurrentPageSelection();
    state.editing.clear();
    await loadInstances();
    await loadTags();
    renderManagerIfActive();
    setMessage(
      skipped
        ? `已复制 ${items.length} 个，跳过 ${skipped} 个`
        : `已复制 ${items.length} 个`,
      "success",
    );
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function formatPendingTimerText(item) {
  return formatPendingElapsed(item.started_at_ms);
}

function updatePendingTimerNodes() {
  for (const node of document.querySelectorAll("[data-pending-elapsed-key]")) {
    const key = node.dataset.pendingElapsedKey || "";
    let startedAtMs = Number.parseFloat(node.dataset.pendingStartMs || "");
    if (!Number.isFinite(startedAtMs)) {
      startedAtMs = state.pendingStartedAtByKey.get(key) || performance.now();
      node.dataset.pendingStartMs = String(startedAtMs);
    }
    if (key) {
      state.pendingStartedAtByKey.set(key, startedAtMs);
    }
    const item = findPendingInstanceByKey(key);
    node.textContent = item ? pendingStatusText(item, startedAtMs) : formatPendingElapsed(startedAtMs);
  }
  stopPendingTimerIfIdle();
}

function findPendingInstanceByKey(key) {
  if (!key) {
    return null;
  }
  for (const item of state.pendingInstances || []) {
    if (runningInstanceKey(item) === key) {
      return item;
    }
  }
  for (const item of state.instances || []) {
    if (item.generation_status === "running" && runningInstanceKey(item) === key) {
      return item;
    }
  }
  return null;
}

function startPendingTimer() {
  if (state.pendingTimerId) {
    return;
  }
  state.pendingTimerId = window.setInterval(updatePendingTimerNodes, 100);
}

function stopPendingTimerIfIdle() {
  const hasDomPending = Boolean(document.querySelector("[data-pending-elapsed-key]"));
  const hasTaskPending = (state.generationTasks || []).some((task) => task.status === "running");
  if ((state.pendingInstances || []).length || hasDomPending || hasTaskPending || !state.pendingTimerId) {
    return;
  }
  window.clearInterval(state.pendingTimerId);
  state.pendingTimerId = 0;
}

function hasRunningInstances() {
  return (state.instances || []).some((item) => item.generation_status === "running")
    || (state.pendingInstances || []).length > 0
    || (state.generationTasks || []).some((task) => task.status === "running");
}

function activeManagerElement(target = document.activeElement) {
  return target?.closest?.(
    "button, select, input, textarea, [data-action], .manager-panel, [data-save-area], [data-operation-form]",
  );
}

function markManagerInteraction(target = document.activeElement) {
  if (state.page !== "manager") {
    return;
  }
  if (!target?.closest?.(".manager-panel, [data-save-area], [data-operation-form]")) {
    return;
  }
  state.managerInteractionUntil = performance.now() + 900;
}

function managerHasOpenFloatingControl() {
  return Boolean(
    state.generationPathDropdownOpen
      || state.operation.provider_dropdown_open
      || state.filters.tag_dropdown_open
      || state.nodeMenu?.openKey
      || state.nodeContextMenu?.open
      || state.operation.aspect_ratio_picker_open
      || state.operation.clarity_picker_open
      || state.operation.size_picker_open
      || state.operation.resolution_picker_open
      || document.querySelector(
        ".generation-path-dropdown, .tag-filter-menu, .tag-selector-menu, "
          + ".operation-provider-dropdown, .node-menu, .node-context-menu, [data-move-dialog], [data-path-replace-dialog]",
      ),
  );
}

function shouldDeferRunningRefreshRender() {
  if (state.page !== "manager") {
    return false;
  }
  const interacting = Number(state.managerInteractionUntil || 0) > performance.now();
  const savePageNavigating = Number(state.savePageNavigationUntil || 0) > performance.now();
  const activeElement = document.activeElement;
  return Boolean(
    interacting
      || savePageNavigating
      || managerHasOpenFloatingControl()
      || activeManagerElement(activeElement)?.matches?.("button, select, input, textarea, [data-action]"),
  );
}

function markSavePageNavigation() {
  state.savePageNavigationUntil = performance.now() + 1200;
}

function refreshSaveAreaOnly() {
  if (state.page !== "manager") {
    return false;
  }
  const saveArea = document.querySelector("[data-save-area]");
  if (!saveArea) {
    return false;
  }
  saveArea.outerHTML = renderSaveArea();
  bindSaveAreaEvents();
  globalThis.stabilizeSaveAreaImages?.({ forceVisible: true, reason: "refresh-save-area-only" });
  return true;
}

function stopRunningRefresh() {
  if (!state.runningRefreshTimerId) {
    return;
  }
  window.clearInterval(state.runningRefreshTimerId);
  state.runningRefreshTimerId = 0;
}

function startRunningRefresh() {
  if (state.runningRefreshTimerId || !hasRunningInstances()) {
    return;
  }
  state.runningRefreshTimerId = window.setInterval(async () => {
    if (state.page !== "manager" || !hasRunningInstances()) {
      stopRunningRefresh();
      return;
    }
    if (state.runningRefreshInFlight) {
      return;
    }
    state.runningRefreshInFlight = true;
    try {
      await loadInstances();
      if (!shouldDeferRunningRefreshRender()) {
        refreshSaveAreaOnly();
        state.runningRefreshNeedsRender = false;
      } else {
        state.runningRefreshNeedsRender = true;
      }
    } catch (error) {
      // Keep polling lightweight; visible task failures are surfaced by generation actions.
    } finally {
      state.runningRefreshInFlight = false;
      if (!hasRunningInstances()) {
        if (state.runningRefreshNeedsRender && state.page === "manager" && !shouldDeferRunningRefreshRender()) {
          refreshSaveAreaOnly();
        }
        state.runningRefreshNeedsRender = false;
        stopRunningRefresh();
      } else if (state.runningRefreshNeedsRender && !shouldDeferRunningRefreshRender()) {
        refreshSaveAreaOnly();
        state.runningRefreshNeedsRender = false;
      }
    }
  }, 1500);
}

function syncRunningRefresh() {
  if (state.page === "manager" && hasRunningInstances()) {
    startRunningRefresh();
  } else {
    stopRunningRefresh();
  }
}

function wakeVisibleSaveImages(options = {}) {
  const saveArea = document.querySelector("[data-save-area]");
  if (!saveArea) {
    return;
  }
  resetSaveAreaImageObserver?.();
  for (const slot of saveArea.querySelectorAll("[data-lazy-image-path]")) {
    observeSaveAreaImageSlot?.(slot, Boolean(options.forceVisible));
  }
}

function addGenerationPathHistory(path) {
  const cleanPath = String(path || "").trim();
  if (!cleanPath) {
    return;
  }
  const existing = cleanStringArray(state.generationPathHistory || [])
    .filter((item) => item !== cleanPath);
  state.generationPathHistory = [cleanPath, ...existing].slice(0, 20);
  persistUiState();
  api("/api/generation-path-history", {
    method: "POST",
    body: { path: cleanPath },
  }).then((data) => {
    state.generationPathHistory = [...new Set(cleanStringArray(data.paths || state.generationPathHistory))].slice(0, 20);
    persistUiState();
  }).catch(() => {});
}

function addSuccessfulProviderFieldHistory(field, value) {
  const cleanValue = String(value || "").trim();
  if (!cleanValue || !["api_key_env", "model", "user_agent"].includes(field)) {
    return;
  }
  state.successfulProviderFieldHistory = state.successfulProviderFieldHistory || {};
  const existing = cleanStringArray(state.successfulProviderFieldHistory[field] || [])
    .filter((item) => item !== cleanValue);
  state.successfulProviderFieldHistory[field] = [cleanValue, ...existing].slice(0, 20);
}

function recordSuccessfulProviderFieldHistory(values = {}) {
  const history = {};
  for (const field of ["api_key_env", "model", "user_agent"]) {
    const value = String(values[field] || "").trim();
    if (value) {
      history[field] = [value];
    }
  }
  if (!Object.keys(history).length) {
    return;
  }
  api("/api/provider-field-history", {
    method: "POST",
    body: { history },
  }).then((data) => {
    const shared = safeObject(data.history);
    state.settingsSharedProviderFieldHistory = {
      api_key_env: cleanStringArray(shared.api_key_env).slice(0, 20),
      model: cleanStringArray(shared.model).slice(0, 20),
      user_agent: cleanStringArray(shared.user_agent).slice(0, 20),
    };
    persistUiState();
  }).catch(() => {});
}

function recordSuccessfulGenerationHistories(payload = {}) {
  addGenerationPathHistory(payload.generation_path || state.operation.generation_path);
  const providerKey = String(payload.provider_key || activeProviderName() || "").trim();
  const provider = state.settings?.providers?.[providerKey] || activeProvider();
  addSuccessfulProviderFieldHistory("api_key_env", provider.api_key_env || "");
  addSuccessfulProviderFieldHistory("model", provider.model || "");
  addSuccessfulProviderFieldHistory("user_agent", provider.user_agent || "");
  recordSuccessfulProviderFieldHistory({
    api_key_env: provider.api_key_env || "",
    model: provider.model || "",
    user_agent: provider.user_agent || "",
  });
  persistUiState();
}

async function chooseInputImages() {
  syncOperationFromDom();
  try {
    setMessage("");
    const data = await api("/api/dialogs/images", { method: "POST" });
    const paths = Array.isArray(data.paths) ? data.paths : [];
    state.operation.input_image_paths.push(...paths);
    persistUiState();
    renderManagerIfActive();
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function removeInputImage(index) {
  syncOperationFromDom();
  state.operation.input_image_paths.splice(index, 1);
  persistUiState();
  renderManager();
}

function clearOperationInputImages() {
  syncOperationFromDom();
  state.operation.input_image_paths = [];
  persistUiState();
  renderManager();
}

function setClipboardImageTarget(target, options = {}) {
  const shouldRender = options.render !== false;
  if (!target) {
    state.clipboardImageTarget = null;
    if (shouldRender) {
      renderManagerIfActive();
    }
    return;
  }
  state.clipboardImageTarget = {
    scope: target.scope,
    area: target.area,
    instanceId: String(target.instanceId || ""),
  };
  if (state.page === "manager") {
    setMessage("已选中图片区：可从资源管理器复制图片文件后按 Ctrl+V 粘贴原始路径。", "info");
    if (shouldRender) {
      renderManagerIfActive();
    }
  }
}

function setClipboardImageTargetFromNode(node, options = {}) {
  const targetNode = node?.closest?.("[data-clipboard-image-target]");
  if (!targetNode) {
    return false;
  }
  setClipboardImageTarget({
    scope: targetNode.dataset.clipboardScope,
    area: targetNode.dataset.clipboardArea,
    instanceId: targetNode.dataset.clipboardInstanceId || "",
  }, options);
  return true;
}

function applyClipboardImagePaths(paths) {
  const target = state.clipboardImageTarget;
  const imagePaths = Array.isArray(paths) ? paths.filter(Boolean) : [];
  if (!target) {
    setMessage("请先点击要粘贴图片路径的图片区。", "error");
    return false;
  }
  if (!imagePaths.length) {
    setMessage("剪贴板中没有可用的本地图片路径，请从资源管理器复制图片文件，或点击选择图片。", "error");
    return false;
  }

  if (target.scope === "operation") {
    syncOperationFromDom();
    state.operation.input_image_paths.push(...imagePaths);
    persistUiState();
    renderManagerIfActive();
    setMessage("已粘贴原始图片路径", "success");
    return true;
  }

  if (target.scope === "instance") {
    const draft = syncInstanceDraftFromDom(target.instanceId);
    if (!draft) {
      setMessage("请先点击编辑，再粘贴图片路径。", "error");
      return false;
    }
    if (target.area === "input") {
      draft.input_image_paths.push(...imagePaths);
    } else {
      draft.output_image_path = imagePaths[0];
    }
    renderManagerIfActive();
    setMessage("已粘贴原始图片路径", "success");
    return true;
  }

  setMessage("请先点击要粘贴图片路径的图片区。", "error");
  return false;
}

async function pasteClipboardImagePaths() {
  try {
    setMessage("");
    const data = await api("/api/clipboard/image-paths");
    applyClipboardImagePaths(data.paths);
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message || "剪贴板中没有可用的本地图片路径", "error");
    }
  }
}

async function chooseGenerationPath() {
  syncOperationFromDom();
  try {
    setMessage("");
    const data = await api("/api/dialogs/directory", {
      method: "POST",
      body: { initial_dir: state.operation.generation_path },
    });
    if (data.path) {
      state.operation.generation_path = data.path;
      persistUiState();
      renderManagerIfActive();
      await saveDefaultOutputDir(data.path);
    }
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function clearOperation() {
  syncOperationFromDom();
  state.operation.prompt = "";
  state.operation.input_image_paths = [];
  setGenerationStatus();
  persistUiState();
  renderManager();
}

function clearOperationPrompt() {
  syncOperationFromDom();
  state.operation.prompt = "";
  persistUiState();
  renderManager();
}

function clearPromptSearch() {
  state.filters.q = "";
  state.filters.page = 1;
  state.filters.tag_dropdown_open = false;
  clearCurrentPageSelection();
  persistUiState();

  const input = document.querySelector('[data-save-toolbar] input[name="q"]');
  if (input) {
    input.value = "";
    input.focus();
  }

  refreshInstances().catch((error) => {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  });
}

function clearInstancePrompt(instanceId) {
  const id = String(instanceId || "");
  const draft = state.editing.get(id) || state.editing.get(Number(id));
  if (!draft) {
    return;
  }
  draft.prompt = "";
  const input = document.querySelector(
    `[data-instance-card][data-id="${CSS.escape(id)}"] [name="instance_prompt"]`,
  );
  if (input) {
    input.value = "";
    autoGrowPromptTextarea(input);
    input.focus();
  }
}

function normalizeBringInTags(tags) {
  if (!Array.isArray(tags)) {
    return [];
  }
  const normalized = [];
  const seen = new Set();
  for (const item of tags) {
    const tag = String(item || "").trim();
    if (!tag || tag === "__untagged__" || seen.has(tag)) {
      continue;
    }
    seen.add(tag);
    normalized.push(tag);
  }
  return normalized;
}

function bringInRecordTags(record) {
  return normalizeBringInTags(record?.tags);
}

function providerExists(providerKey) {
  return Boolean(providerKey && state.settings?.providers?.[providerKey]);
}

function chooseAvailableProviderForBringIn(message) {
  const providers = Object.keys(state.settings?.providers || {});
  if (!providers.length) {
    throw new Error("当前没有可用 Provider");
  }
  const selected = window.prompt(
    `${message}\n当前可用 Provider：${providers.join(" / ")}\n请输入要使用的 Provider 内部编号：`,
    providers[0],
  );
  if (selected === null) {
    return "";
  }
  const providerKey = String(selected || "").trim();
  if (!providerExists(providerKey)) {
    throw new Error("请选择当前可用 Provider");
  }
  return providerKey;
}

function resolveBringInProvider(providerKey) {
  const requested = String(providerKey || "").trim();
  if (!requested) {
    return "";
  }
  if (providerExists(requested)) {
    return requested;
  }
  return chooseAvailableProviderForBringIn("原 Provider 已不存在，请选择当前可用 Provider 后带入操作区。");
}

function normalizeBringInParams(params = {}) {
  const source = params && typeof params === "object" ? params : {};
  const ratio = String(source.ratio || "").trim();
  const clarity = String(source.resolution_level || source.resolution || "").trim();
  const size = String(source.resolved_size || source.size || "").trim();
  const count = parseGenerationCount(source.n || source.count);
  return { ratio, clarity, size, count };
}

async function applyBringInToOperation(payload = {}) {
  syncOperationFromDom();
  const preservedGenerationPath = state.operation.generation_path || "";
  const params = normalizeBringInParams(payload.params || payload.generation_params || {});
  const inputImagePaths = Array.isArray(payload.input_image_paths)
    ? payload.input_image_paths.filter(Boolean)
    : [];
  const mode = inputImagePaths.length ? "image_to_image" : (payload.mode || "text_to_image");
  const targetProvider = activeProvider();
  const capability = providerCallMethodCapability(targetProvider);
  const requestedMode = mode === "image_to_image" ? "image_to_image" : "text_to_image";
  if (requestedMode === "image_to_image" && capability.supportsImageToImage === false) {
    throw new Error("当前 Provider 不支持图生图，请更换 Provider 或移除输入图");
  }
  if (requestedMode === "text_to_image" && capability.supportsTextToImage === false) {
    throw new Error("当前 Provider 不支持文生图，请更换 Provider");
  }

  state.operation.mode = requestedMode;
  state.operation.prompt = payload.prompt || "";
  state.operation.input_image_paths = inputImagePaths;
  state.operation.tags = normalizeBringInTags(payload.tags);
  state.operation.generation_path = preservedGenerationPath;
  if (ASPECT_RATIO_PRESETS.includes(params.ratio)) {
    state.operation.aspect_ratio = params.ratio;
  }
  if (isValidGenerationResolution(params.clarity)) {
    state.operation.generation_clarity = params.clarity;
    state.operation.resolution = params.clarity;
  }
  if (isValidGenerationSize(params.size)) {
    state.operation.generation_size = params.size;
    state.operation.custom_generation_size = params.size;
    if (!ASPECT_RATIO_PRESETS.includes(params.ratio)) {
      state.operation.aspect_ratio = aspectRatioForSize(params.size, params.clarity) || state.operation.aspect_ratio;
    }
  } else if (isPresetClarity(state.operation.generation_clarity)) {
    state.operation.generation_size = sizeForAspectRatio(state.operation.aspect_ratio, state.operation.generation_clarity);
    state.operation.custom_generation_size = state.operation.generation_size;
  }
  let count = state.operation.mode === "image_to_image" ? 1 : (params.count || state.operation.generation_count || 1);
  if (state.operation.mode !== "image_to_image" && capability.supportsCount === false && count > 1) {
    count = 1;
    setMessage("当前 Provider 不支持多图数量，已将数量设为 1", "info");
  }
  state.operation.generation_count = count;
  state.operation.text_generation_count = count;
  state.operation.aspect_ratio_picker_open = false;
  state.operation.clarity_picker_open = false;
  state.operation.size_picker_open = false;
  state.operation.resolution_picker_open = false;
  state.operation.tag_selector_open = false;
  normalizeOperation();
  state.operation.generation_path = preservedGenerationPath;
  persistUiState();
  renderManagerIfActive();
  setMessage("已带入操作区", "success");
  if (
    payload.openai_call_method
    && activeProvider()?.openai_call_method
    && payload.openai_call_method !== activeProvider().openai_call_method
  ) {
    setMessage("历史记录的调用方式与当前 Provider 设置不同，后续生成将按当前 Provider 设置执行。", "info");
  }
}

async function bringInstanceToOperation(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  const instance = instanceById(instanceId);
  const item = draft || instance;
  if (!item || item.pending || item.generation_status === "running") {
    return;
  }
  const params = item.generation_params || {};
  await applyBringInToOperation({
    prompt: item.prompt || "",
    mode: item.input_image_paths?.length ? "image_to_image" : "text_to_image",
    input_image_paths: item.input_image_paths || [],
    tags: item.tags || [],
    openai_call_method: params.openai_call_method || "",
    params: {
      ...params,
      resolved_size: params.resolved_size || item.generation_size || "",
    },
  });
}

async function bringHistoryToOperation(historyId) {
  const record = (state.history.items || []).find((item) => String(item.id) === String(historyId));
  if (!record) {
    setMessage("历史记录不在当前页，请刷新后重试", "error");
    return;
  }
  const params = record.params || {};
  await applyBringInToOperation({
    prompt: record.prompt || "",
    mode: record.mode || "",
    input_image_paths: record.input_image_paths || [],
    tags: bringInRecordTags(record),
    openai_call_method: params.openai_call_method || record.openai_call_method || "",
    params: {
      ...params,
      resolved_size: params.resolved_size || record.resolved_size || "",
    },
  });
}

function operationPayload() {
  syncOperationFromDom();
  const resolutionLevel = activeGenerationClarity();
  if (!resolutionLevel) {
    throw new Error("请输入自定义清晰度");
  }
  const count = parseGenerationCount(state.operation.generation_count);
  if (!count) {
    throw new Error("生成数量必须是正整数");
  }
  state.operation.generation_count = count;
  state.operation.text_generation_count = count;
  const inputImagePaths = [...state.operation.input_image_paths].filter(Boolean);
  const mode = inferOperationModeFromInputs(inputImagePaths);
  state.operation.mode = mode;
  const activeOpenAIGoogle = isActiveOpenAIGoogleProvider();
  return {
    provider_key: activeProviderName(),
    mode,
    prompt: state.operation.prompt,
    input_image_paths: inputImagePaths,
    tags: [...state.operation.tags],
    generation_path: state.operation.generation_path,
    node_id: deepestSelectedNodeId(),
    options: {
      ratio: activeOpenAIGoogle ? "" : state.operation.aspect_ratio,
      resolution_level: activeOpenAIGoogle ? "" : resolutionLevel,
      size: activeOpenAIGoogle ? "" : state.operation.generation_size,
      // n: state.operation.generation_count
      n: state.operation.generation_count,
    },
  };
}

function inferOperationModeFromInputs(inputImagePaths = state.operation.input_image_paths) {
  return Array.isArray(inputImagePaths) && inputImagePaths.filter(Boolean).length
    ? "image_to_image"
    : "text_to_image";
}

function generationParamsForDraft(payload, providerKey = payload?.provider_key || "") {
  const provider = state.settings?.providers?.[providerKey] || {};
  const options = payload?.options || {};
  const activeOpenAIGoogle = normalizeProviderAdapter(provider.adapter) === "openai-google";
  const callMethod = provider.openai_call_method || "gpt-image-2";
  return {
    provider_key: providerKey,
    adapter: provider.adapter || "",
    openai_call_method: callMethod,
    model: callMethod === "response" ? "response" : provider.model || "gpt-image-2",
    ratio: options.ratio || "",
    resolution_level: options.resolution_level || "",
    resolved_size: activeOpenAIGoogle ? "" : (options.size || ""),
    size: activeOpenAIGoogle ? "" : (options.size || ""),
    quality: provider.quality || "high",
    output_format: provider.output_format || "png",
    output_compression: provider.output_compression ?? 80,
    background: provider.background || "auto",
    moderation: provider.moderation || "low",
    user: provider.user || "",
    user_agent: provider.user_agent || "",
    proxy_mode: provider.proxy_mode || "system",
    allow_untrusted_proxy_certificate: provider.allow_untrusted_proxy_certificate !== false,
    n: options.n || options.count || 1,
    custom_script_used: false,
  };
}

function draftInstancePayloadFromGenerationPayload(payload, overrides = {}) {
  const providerKey = overrides.provider_key ?? payload.provider_key ?? activeProviderName();
  const generationParams = {
    ...generationParamsForDraft(payload, providerKey),
    ...(overrides.generation_params || {}),
  };
  const generationSize = overrides.generation_size ?? payload.options?.size ?? "";
  return {
    prompt: overrides.prompt ?? payload.prompt ?? "",
    mode: overrides.mode ?? payload.mode ?? "text_to_image",
    source: "manual",
    provider: providerKey,
    generation_path: overrides.generation_path ?? payload.generation_path ?? "",
    generation_size: generationSize,
    generation_params: generationParams,
    output_image_path: "",
    input_image_paths: Array.isArray(overrides.input_image_paths)
      ? [...overrides.input_image_paths]
      : [...(payload.input_image_paths || [])],
    tags: Array.isArray(overrides.tags)
      ? [...overrides.tags]
      : [...(payload.tags || [])],
    node_id: overrides.node_id !== undefined ? overrides.node_id : payload.node_id,
  };
}

function generationOptionsForInstance(item) {
  const itemProviderKey = String(item?.provider || item?.generation_params?.provider_key || "").trim();
  if (isOpenAIGoogleProviderKey(itemProviderKey)) {
    return {
      ratio: "",
      resolution_level: "",
      size: "",
      n: 1,
    };
  }
  const params = item?.generation_params && typeof item.generation_params === "object"
    ? item.generation_params
    : {};
  const resolvedSize = String(params.resolved_size || params.size || item?.generation_size || "").trim();
  let resolutionLevel = String(params.resolution_level || params.resolution || "").trim();
  let ratio = String(params.ratio || "").trim();

  if (!isValidGenerationResolution(resolutionLevel)) {
    resolutionLevel = "";
  }
  if (!ASPECT_RATIO_PRESETS.includes(ratio) && ratio !== "custom") {
    ratio = "";
  }

  if (resolvedSize) {
    if (!resolutionLevel) {
      const inferredRatio = aspectRatioForSize(resolvedSize);
      if (inferredRatio) {
        for (const clarity of PRESET_RESOLUTIONS) {
          if (sizeForAspectRatio(inferredRatio, clarity) === resolvedSize) {
            resolutionLevel = clarity;
            break;
          }
        }
      }
    }
    if (!ratio && resolutionLevel) {
      ratio = aspectRatioForSize(resolvedSize, resolutionLevel);
    }
    if (!ratio) {
      ratio = aspectRatioForSize(resolvedSize);
    }
  }

  if (!resolutionLevel) {
    resolutionLevel = activeGenerationClarity();
  }
  if (!ratio && resolutionLevel !== "custom") {
    ratio = state.operation.aspect_ratio || defaultAspectRatio();
  }
  if (!ratio) {
    ratio = "custom";
  }

  const size = resolutionLevel === "custom"
    ? (isValidGenerationSize(resolvedSize) ? resolvedSize : (state.operation.generation_size || defaultGenerationSize()))
    : (sizeForAspectRatio(ratio, resolutionLevel) || resolvedSize || state.operation.generation_size || defaultGenerationSize());

  return {
    ratio,
    resolution_level: resolutionLevel,
    size,
    n: parseGenerationCount(params.n || params.count) || 1,
  };
}

function copiedGenerationSizeForInstance(item, options = {}) {
  const params = item?.generation_params && typeof item.generation_params === "object"
    ? item.generation_params
    : {};
  return String(
    item?.generation_size
      || params.resolved_size
      || params.size
      || options.size
      || "",
  ).trim();
}

function providerForInstanceSubmit(item) {
  const providerKey = String(item?.provider || item?.generation_params?.provider_key || "").trim();
  if (!providerKey) {
    throw new Error("当前实例没有保存 Provider，不能提交");
  }
  if (!state.settings?.providers?.[providerKey]) {
    throw new Error(`当前实例的 Provider 不存在：${providerKey}`);
  }
  return providerKey;
}

function isOpenAIGoogleProviderKey(providerKey) {
  const provider = state.settings?.providers?.[providerKey] || {};
  return normalizeProviderAdapter(provider.adapter) === "openai-google";
}

function pendingInstanceCountForPayload(payload) {
  if (payload?.mode === "image_to_image") {
    return 1;
  }
  return normalizeGenerationCount(payload?.options?.n || 1);
}

function instanceGenerationCountInputValue(instanceId) {
  const card = document.querySelector(`[data-instance-card][data-id="${CSS.escape(String(instanceId))}"]`);
  const input = card?.querySelector('[name="instance_generation_count"]');
  return input ? input.value : undefined;
}

function validateInstanceGenerationCount(item, rawValue = undefined) {
  const count = parseGenerationCount(rawValue ?? item?.generation_params?.n ?? item?.generation_params?.count ?? 1);
  if (!count) {
    throw new Error(`实例 ${instanceNumberLabel(item)} 的数量必须是正整数`);
  }
  item.generation_params = item.generation_params && typeof item.generation_params === "object"
    ? { ...item.generation_params }
    : {};
  item.generation_params.n = count;
  item.generation_params.count = count;
  return count;
}

function createPendingInstancesForTask(task, payload) {
  if (payload?.target_instance_id || payload?.retry_instance_id) {
    return [];
  }
  const count = pendingInstanceCountForPayload(payload);
  const createdAt = new Date().toISOString();
  const startedAtMs = performance.now();
  const provider = payload?.provider_key || activeProviderName();
  const generationSize = payload?.options?.size || "";
  const items = Array.from({ length: count }, (_, index) => ({
    id: `${task.id}-pending-${index + 1}`,
    pending: true,
    task_id: task.id,
    generation_task_id: payload?.generation_task_id || task.id,
    generation_output_index: index + 1,
    node_id: payload?.node_id || null,
    generation_status: "running",
    display_index: "",
    prompt: payload?.prompt || "",
    mode: payload?.mode || "text_to_image",
    source: "generated",
    provider,
    created_at: createdAt,
    started_at_ms: startedAtMs,
    input_image_paths: Array.isArray(payload?.input_image_paths) ? [...payload.input_image_paths] : [],
    output_image_path: "",
    tags: Array.isArray(payload?.tags) ? [...payload.tags] : [],
    generation_size: generationSize,
    generation_params: payload?.options || {},
  }));
  state.pendingInstances = [...items, ...(state.pendingInstances || [])];
  for (const item of items) {
    const key = runningInstanceKey(item);
    if (key) {
      state.pendingStartedAtByKey.set(key, item.started_at_ms);
    }
  }
  startPendingTimer();
  startRunningRefresh();
  return items;
}

function markInstanceRunningInPlace(instanceId, taskId) {
  const id = String(instanceId || "");
  const task = String(taskId || "");
  const startedAtMs = performance.now();
  for (const item of state.instances || []) {
    if (String(item.id) !== id) {
      continue;
    }
    item.generation_status = "running";
    item.generation_task_id = task;
    item.generation_output_index = 1;
    item.generation_error = "";
    item.output_image_path = "";
    item.output_image_paths = [];
    item.pending = false;
    item.started_at_ms = startedAtMs;
    const key = runningInstanceKey(item);
    if (key) {
      state.pendingStartedAtByKey.set(key, startedAtMs);
    }
  }
  startPendingTimer();
  startRunningRefresh();
}

function removePendingInstancesForTask(taskId) {
  for (const item of state.pendingInstances || []) {
    if (item.task_id === taskId) {
      const key = runningInstanceKey(item);
      if (key) {
        state.pendingStartedAtByKey.delete(key);
      }
    }
  }
  state.pendingInstances = (state.pendingInstances || []).filter(
    (item) => item.task_id !== taskId,
  );
  stopPendingTimerIfIdle();
  syncRunningRefresh();
}

async function generateFromOperation() {
  return addOperationDraft();
}

async function addOperationDraft() {
  try {
    setMessage("");
    const payload = operationPayload();
    const instancePayload = draftInstancePayloadFromGenerationPayload(payload);
    const data = await runUndoableAction("新增准备态实例", async () => (
      api("/api/instances", {
        method: "POST",
        body: instancePayload,
      })
    ));
    state.filters.sort = "created_desc";
    state.filters.page = 1;
    clearCurrentPageSelection();
    persistUiState();
    await loadInstances();
    await loadTags();
    renderManagerIfActive();
    const n = Number(instancePayload.generation_params?.n || 1);
    setMessage(n > 1 ? `已新增准备态实例，数量 ${n}` : "已新增准备态实例", "success");
    return data?.item || null;
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
    return null;
  }
}

async function resubmitInstance(instanceId) {
  return copySubmitInstance(instanceId);
}

async function copySubmitInstance(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  const instance = instanceById(instanceId);
  const item = draft || instance;
  if (!item) {
    return;
  }

  try {
    setMessage("");
    const inputImagePaths = Array.isArray(item.input_image_paths)
      ? item.input_image_paths.filter(Boolean)
      : [];
    const mode = inputImagePaths.length ? "image_to_image" : "text_to_image";
    validateInstanceGenerationCount(item, instanceGenerationCountInputValue(instanceId));
    const options = generationOptionsForInstance(item);
    const providerKey = providerForInstanceSubmit(item);
    if (!options.resolution_level && !isOpenAIGoogleProviderKey(providerKey)) {
      throw new Error("请输入自定义清晰度");
    }
    const generationPath = item.generation_path || state.settings?.default_output_dir || "";
    const payload = {
      provider_key: providerKey,
      mode,
      prompt: item.prompt || "",
      input_image_paths: inputImagePaths,
      tags: Array.isArray(item.tags) ? [...item.tags] : [],
      generation_path: generationPath,
      node_id: item.node_id ?? deepestSelectedNodeId(),
      options,
    };
    const copiedGenerationSize = isOpenAIGoogleProviderKey(providerKey)
      ? ""
      : copiedGenerationSizeForInstance(item, options);
    const copiedGenerationParams = {
      ...generationParamsForDraft(payload, providerKey),
      ...(item.generation_params || {}),
      resolved_size: copiedGenerationSize,
      size: copiedGenerationSize,
      ratio: options.ratio,
      resolution_level: options.resolution_level,
      n: options.n,
      output_image_paths: [],
    };
    await runUndoableAction("复制准备态实例", async () => (
      api("/api/instances", {
        method: "POST",
        body: draftInstancePayloadFromGenerationPayload(payload, {
          generation_size: copiedGenerationSize,
          output_image_path: "",
          generation_params: copiedGenerationParams,
        }),
      })
    ));
    state.filters.sort = "created_desc";
    state.filters.page = 1;
    clearCurrentPageSelection();
    await loadInstances();
    await loadTags();
    renderManagerIfActive();
    setMessage("已复制为准备态实例", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function retryFailedInstance(instanceId) {
  const instance = instanceById(instanceId);
  if (!instance || instance.generation_status !== "failed") {
    if (state.page === "manager") {
      setMessage("只有生成失败实例可以重提", "error");
    }
    return;
  }

  let task;
  try {
    syncOperationFromDom();
    normalizeOperation();
    const inputImagePaths = Array.isArray(instance.input_image_paths)
      ? instance.input_image_paths.filter(Boolean)
      : [];
    const mode = inputImagePaths.length ? "image_to_image" : "text_to_image";
    validateInstanceGenerationCount(instance, instanceGenerationCountInputValue(instanceId));
    const options = generationOptionsForInstance(instance);
    const providerKey = providerForInstanceSubmit(instance);
    if (!options.resolution_level && !isOpenAIGoogleProviderKey(providerKey)) {
      throw new Error("请输入自定义清晰度");
    }
    const generationPath = instance.generation_path || state.settings?.default_output_dir || "";
    const payload = {
      "retry_instance_id": Number(instance.id),
      provider_key: providerKey,
      mode,
      prompt: instance.prompt || "",
      input_image_paths: inputImagePaths,
      output_image_path: "",
      tags: Array.isArray(instance.tags) ? [...instance.tags] : [],
      generation_path: generationPath,
      node_id: instance.node_id ?? deepestSelectedNodeId(),
      options,
    };
    task = createGenerationTask(payload);
    payload.generation_task_id = task.id;
    markInstanceRunningInPlace(instance.id, task.id);
    setGenerationStatus();
    renderManagerIfActive();
    await api("/api/generate", {
      method: "POST",
      body: payload,
    });
    recordSuccessfulGenerationHistories(payload);
    updateGenerationTask(task.id, {
      status: "success",
    });
    await loadInstances();
    await loadTags();
    await loadGenerationHistory();
    if (renderManagerIfActive()) {
      setMessage("已重提", "success");
    }
  } catch (error) {
    if (task) {
      updateGenerationTask(task.id, {
        status: "failed",
        error: error.message,
      });
      loadInstances().catch(() => {});
      loadTags().catch(() => {});
      loadGenerationHistory().catch(() => {});
      renderManagerIfActive();
    } else if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function submitManualInstance(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  const instance = instanceById(instanceId);
  const item = draft || instance;
  if (!item) {
    return;
  }
  if (item.output_image_path || instance?.output_image_path) {
    setMessage("已有输出图，不能直接提交", "error");
    return;
  }

  let task;
  try {
    syncOperationFromDom();
    normalizeOperation();
    if (draft) {
      const result = await persistInstanceDraft(instanceId);
      if (!result.ok) {
        throw result.error;
      }
    }
    const inputImagePaths = Array.isArray(item.input_image_paths)
      ? item.input_image_paths.filter(Boolean)
      : [];
    const mode = inputImagePaths.length ? "image_to_image" : "text_to_image";
    validateInstanceGenerationCount(item, instanceGenerationCountInputValue(instanceId));
    const options = generationOptionsForInstance(item);
    const providerKey = providerForInstanceSubmit(item);
    if (!options.resolution_level && !isOpenAIGoogleProviderKey(providerKey)) {
      throw new Error("请输入自定义清晰度");
    }
    const generationPath = item.generation_path || state.settings?.default_output_dir || "";
    const payload = {
      target_instance_id: Number(instanceId),
      provider_key: providerKey,
      mode,
      prompt: item.prompt || "",
      input_image_paths: inputImagePaths,
      output_image_path: "",
      tags: Array.isArray(item.tags) ? [...item.tags] : [],
      generation_path: generationPath,
      node_id: item.node_id || deepestSelectedNodeId(),
      options,
    };
    task = createGenerationTask(payload);
    payload.generation_task_id = task.id;
    markInstanceRunningInPlace(instanceId, task.id);
    setGenerationStatus();
    renderManagerIfActive();
    await api("/api/generate", {
      method: "POST",
      body: payload,
    });
    recordSuccessfulGenerationHistories(payload);
    updateGenerationTask(task.id, {
      status: "success",
    });
    await loadInstances();
    await loadTags();
    await loadGenerationHistory();
    if (renderManagerIfActive()) {
      setMessage("已提交", "success");
    }
  } catch (error) {
    if (task) {
      updateGenerationTask(task.id, {
        status: "failed",
        error: error.message,
      });
      loadInstances().catch(() => {});
      loadTags().catch(() => {});
      loadGenerationHistory().catch(() => {});
      renderManagerIfActive();
    } else if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function submitSelectedInstances() {
  const ids = selectedInstanceIds();
  if (!ids.length) {
    return;
  }
  let submitted = 0;
  let retried = 0;
  let skipped = 0;
  const skippedInvalid = [];
  for (const id of ids) {
    const item = instanceById(id);
    if (
      !item
      || item.output_image_path
      || item.generation_status === "running"
    ) {
      skipped += 1;
      continue;
    }
    try {
      const draft = syncInstanceDraftFromDom(id);
      validateInstanceGenerationCount(draft || item, instanceGenerationCountInputValue(id));
    } catch (error) {
      skipped += 1;
      skippedInvalid.push(error.message);
      continue;
    }
    if (item.generation_status === "failed") {
      retried += 1;
      retryFailedInstance(id);
      continue;
    }
    submitted += 1;
    submitManualInstance(id);
  }
  if (submitted || retried || skipped) {
    const invalidText = skippedInvalid.length ? `；${skippedInvalid.join("；")}` : "";
    setMessage(
      `已提交 ${submitted} 个，已重提 ${retried} 个，跳过 ${skipped} 个${invalidText}`,
      skippedInvalid.length ? "error" : (submitted || retried ? "success" : "info"),
    );
  }
}

async function cancelGenerationTask(taskId) {
  const cleanId = String(taskId || "").trim();
  if (!cleanId) {
    return;
  }
  if (!(state.cancellingGenerationTaskIds instanceof Set)) {
    state.cancellingGenerationTaskIds = new Set(state.cancellingGenerationTaskIds || []);
  }
  state.cancellingGenerationTaskIds.add(cleanId);
  for (const item of state.pendingInstances || []) {
    if ((item.generation_task_id || item.task_id) === cleanId) {
      item.cancelling = true;
    }
  }
  for (const item of state.instances || []) {
    if (item.generation_status === "running" && item.generation_task_id === cleanId) {
      item.cancelling = true;
    }
  }
  renderManagerIfActive();
  try {
    await api("/api/generate/cancel", {
      method: "POST",
      body: { generation_task_id: cleanId },
    });
    for (const item of state.pendingInstances || []) {
      if ((item.generation_task_id || item.task_id) === cleanId) {
        item.cancelling = true;
      }
    }
    for (const item of state.instances || []) {
      if (item.generation_status === "running" && item.generation_task_id === cleanId) {
        item.cancelling = true;
      }
    }
    setMessage("已请求取消生成", "info");
    renderManagerIfActive();
  } catch (error) {
    state.cancellingGenerationTaskIds.delete(cleanId);
    for (const item of state.pendingInstances || []) {
      if ((item.generation_task_id || item.task_id) === cleanId) {
        item.cancelling = false;
      }
    }
    for (const item of state.instances || []) {
      if (item.generation_status === "running" && item.generation_task_id === cleanId) {
        item.cancelling = false;
      }
    }
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
    renderManagerIfActive();
  }
}


function instancePayload(draft) {
  return {
    prompt: draft.prompt,
    mode: draft.mode || "unspecified",
    source: draft.source || "manual",
    provider: draft.provider ?? "",
    generation_path: draft.generation_path || "",
    output_image_path: draft.output_image_path || "",
    input_image_paths: Array.isArray(draft.input_image_paths) ? [...draft.input_image_paths] : [],
    tags: Array.isArray(draft.tags) ? [...draft.tags] : [],
    generation_size: draft.generation_size || "",
    generation_params: draft.generation_params && typeof draft.generation_params === "object"
      ? { ...draft.generation_params }
      : {},
  };
}

function normalizedInstancePayloadString(payload) {
  return JSON.stringify({
    ...payload,
    input_image_paths: cleanStringArray(payload.input_image_paths),
    tags: cleanStringArray(payload.tags),
    generation_params: payload.generation_params && typeof payload.generation_params === "object"
      ? payload.generation_params
      : {},
  });
}

function hasInstanceDraftChanged(instanceId, draft = null) {
  const instance = instanceById(instanceId);
  const currentDraft = draft || syncInstanceDraftFromDom(instanceId);
  if (!instance || !currentDraft) {
    return false;
  }
  return normalizedInstancePayloadString(instancePayload(instance))
    !== normalizedInstancePayloadString(instancePayload(currentDraft));
}

async function persistInstanceDraft(instanceId) {
  const id = String(instanceId);
  if (state.savingInstances.has(id)) {
    return { ok: true, skipped: true };
  }

  const draft = syncInstanceDraftFromDom(instanceId);
  if (!draft) {
    return { ok: true, skipped: true };
  }

  state.savingInstances.add(id);
  try {
    await api(`/api/instances/${encodeURIComponent(instanceId)}`, {
      method: "PUT",
      body: instancePayload(draft),
    });
    state.editing.delete(Number(instanceId));
    state.editing.delete(String(instanceId));
    return { ok: true };
  } catch (error) {
    return { ok: false, error };
  } finally {
    state.savingInstances.delete(id);
  }
}

async function refreshInstances(message = "", type = "success") {
  const loaded = await loadInstances();
  if (loaded === false) {
    return;
  }
  await loadTags();
  if (renderManagerIfActive() && message) {
    setMessage(message, type);
  }
  globalThis.stabilizeSaveAreaImages?.({ reason: "refresh-instances" });
}

async function batchSaveEditingInstances({ excludeInstanceId = "" } = {}) {
  const exclude = String(excludeInstanceId || "");
  const ids = [...state.editing.keys()]
    .map((id) => String(id))
    .filter((id) => id && id !== exclude);
  if (!ids.length) {
    return;
  }

  const changedIds = ids.filter((id) => {
    const draft = syncInstanceDraftFromDom(id);
    return hasInstanceDraftChanged(id, draft);
  });
  const beforeSnapshot = changedIds.length ? await createSessionSnapshot() : null;
  const results = await Promise.all(ids.map((id) => persistInstanceDraft(id)));
  const changedIdSet = new Set(changedIds);
  const failures = results.filter((result) => !result.ok);
  const savedCount = results.length - failures.length;
  const undoableSavedCount = results.filter((result, index) => (
    result.ok && !result.skipped && changedIdSet.has(ids[index])
  )).length;
  if (undoableSavedCount > 0 && beforeSnapshot) {
    state.undoStack = [...(state.undoStack || []), { label: "批量保存实例编辑", snapshot: beforeSnapshot }];
    state.redoStack = [];
  }
  if (savedCount > 0) {
    await loadInstances();
    await loadTags();
  }
  if (renderManagerIfActive()) {
    if (failures.length) {
      setMessage(`批量保存失败 ${failures.length} 条：${failures[0].error?.message || "未知错误"}`, "error");
    } else if (savedCount > 0) {
      setMessage(`已批量保存 ${savedCount} 条`, "success");
    }
  }
}

function isInteractiveTarget(target) {
  return Boolean(
    target.closest(
      'textarea, input, select, button, [data-image-path], [data-clipboard-image-target], [data-skip-batch-save], [data-lightbox-backdrop], [data-path-replace-dialog], .size-popover, .resolution-popover, .tag-selector-menu, .tag-filter-menu',
    ),
  );
}

function shouldSkipBatchSave(event) {
  return isInteractiveTarget(event.target);
}

function handleBatchSaveBoundary(event) {
  if (state.page !== "manager" || shouldSkipBatchSave(event)) {
    return;
  }
  const card = event.target.closest("[data-instance-card]");
  const excludeInstanceId = card?.dataset.id || "";
  queueMicrotask(() => {
    batchSaveEditingInstances({ excludeInstanceId }).catch((error) => {
      if (state.page === "manager") {
        setMessage(`批量保存失败：${error.message}`, "error");
      }
    });
  });
}

function handleDocumentBatchSaveBoundary(event) {
  handleBatchSaveBoundary(event);
}

function applySaveFilters(form) {
  syncOperationFromDom();
  state.filters.q = form.elements.q?.value || "";
  state.filters.source = "all";
  state.filters.mode_filter = normalizeSaveModeFilter(form.elements.mode_filter?.value || "all");
  state.filters.provider = form.elements.provider?.value || "all";
  state.filters.statuses = normalizeSavedStatuses(state.filters.statuses, state.filters.status);
  state.filters.status = state.filters.statuses[0] || "all";
  state.filters.size = form.elements.size?.value || "all";
  state.filters.call_method = form.elements.call_method?.value || "all";
  state.filters.model = form.elements.model?.value || "all";
  state.filters.sort = form.elements.sort?.value || "created_desc";
  state.filters.per_page = normalizeSavePerPage(form.elements.per_page?.value || 50);
  state.filters.page = 1;
  state.filters.tag_dropdown_open = false;
  state.filters.status_dropdown_open = false;
  state.editing.clear();
  clearCurrentPageSelection();
  persistUiState();

  refreshInstances().catch((error) => {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  });
}

function applySaveStatusFilterChange() {
  state.filters.statuses = normalizeSavedStatuses(state.filters.statuses, state.filters.status);
  state.filters.status = state.filters.statuses[0] || "all";
  state.filters.status_dropdown_open = true;
  state.filters.page = 1;
  state.editing.clear();
  clearCurrentPageSelection();
  persistUiState();
  refreshInstances().catch((error) => {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  });
}

function toggleSaveStatusFilter(status) {
  const cleanStatus = normalizeOption(String(status || ""), ["all", ...SAVE_STATUS_FILTER_OPTIONS], "all");
  if (cleanStatus === "all") {
    state.filters.statuses = [];
    state.filters.status = "all";
    applySaveStatusFilterChange();
    return;
  }
  const statuses = new Set(normalizeSavedStatuses(state.filters.statuses, state.filters.status));
  if (statuses.has(cleanStatus)) {
    statuses.delete(cleanStatus);
  } else {
    statuses.add(cleanStatus);
  }
  state.filters.statuses = SAVE_STATUS_FILTER_OPTIONS.filter((item) => statuses.has(item));
  state.filters.status = state.filters.statuses[0] || "all";
  applySaveStatusFilterChange();
}

function clearSaveStatusFilter() {
  state.filters.statuses = [];
  state.filters.status = "all";
  state.filters.status_dropdown_open = false;
  state.filters.page = 1;
  clearCurrentPageSelection();
  persistUiState();
  refreshInstances().catch((error) => {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  });
}

function applyHistoryFilters(form) {
  closeHistoryTextPopover();
  state.history.q = form.elements.history_q?.value || "";
  state.history.status = form.elements.history_status?.value || "all";
  state.history.provider = form.elements.history_provider?.value || "all";
  state.history.size = form.elements.history_size?.value || "all";
  state.history.mode = form.elements.history_mode?.value || "all";
  state.history.call_method = form.elements.history_call_method?.value || "all";
  state.history.model = form.elements.history_model?.value || "all";
  state.history.number_type = form.elements.history_number_type?.value || "all";
  state.history.start_date = form.elements.history_start_date?.value || "";
  state.history.end_date = form.elements.history_end_date?.value || "";
  state.history.per_page = normalizeHistoryPerPage(form.elements.history_per_page?.value || 50);
  state.history.page = 1;
  persistUiState();
  loadGenerationHistory().catch((error) => {
    if (state.page === "history") {
      setMessage(error.message, "error");
    }
  });
}

function toggleHistoryFilterTag(tag) {
  const cleanTag = String(tag || "").trim();
  if (!cleanTag) {
    return;
  }
  const tags = new Set(state.history.tags || []);
  if (cleanTag === UNTAGGED_FILTER_VALUE) {
    if (tags.has(UNTAGGED_FILTER_VALUE)) {
      tags.delete(UNTAGGED_FILTER_VALUE);
    } else {
      tags.clear();
      tags.add(UNTAGGED_FILTER_VALUE);
    }
  } else if (tags.has(cleanTag)) {
    tags.delete(cleanTag);
  } else {
    tags.delete(UNTAGGED_FILTER_VALUE);
    tags.add(cleanTag);
  }
  state.history.tags = [...tags];
  state.history.history_tag_dropdown_open = true;
  state.history.page = 1;
  persistUiState();
  loadGenerationHistory().catch((error) => {
    if (state.page === "history") {
      setMessage(error.message, "error");
    }
  });
}

function clearHistoryTagFilter() {
  state.history.tags = [];
  state.history.tag_search = "";
  state.history.history_tag_dropdown_open = false;
  state.history.page = 1;
  persistUiState();
  loadGenerationHistory().catch((error) => {
    if (state.page === "history") {
      setMessage(error.message, "error");
    }
  });
}

function changeHistoryPage(delta) {
  const totalPages = Math.max(1, Math.ceil((state.history.total || 0) / (state.history.per_page || 50)));
  setHistoryPage(Math.min(totalPages, Math.max(1, (state.history.page || 1) + delta)));
}

function setHistoryPage(page) {
  closeHistoryTextPopover();
  const totalPages = Math.max(1, Math.ceil((state.history.total || 0) / (state.history.per_page || 50)));
  state.history.page = Math.min(totalPages, Math.max(1, Number.parseInt(page, 10) || 1));
  persistUiState();
  loadGenerationHistory().catch((error) => {
    if (state.page === "history") {
      setMessage(error.message, "error");
    }
  });
}

function clearTagFilter() {
  state.filters.tags = [];
  state.filters.tag_search = "";
  state.filters.tag_dropdown_open = false;
  state.filters.page = 1;
  clearCurrentPageSelection();
  persistUiState();
  refreshInstances().catch((error) => {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  });
}

function startEditingInstance(instanceId) {
  const instance = instanceById(instanceId);
  if (!instance) {
    return;
  }
  state.editing.set(Number(instanceId), cloneInstanceForEdit(instance));
  renderManager();
}

function cancelEditingInstance(instanceId) {
  state.editing.delete(Number(instanceId));
  renderManager();
}

function cancelAllEditingInstances() {
  if (!state.editing?.size) {
    return false;
  }
  state.editing.clear();
  renderManager();
  return true;
}

async function saveInstanceDraft(instanceId) {
  try {
    setMessage("");
    const draft = syncInstanceDraftFromDom(instanceId);
    const changed = hasInstanceDraftChanged(instanceId, draft);
    const beforeSnapshot = changed ? await createSessionSnapshot() : null;
    const result = await persistInstanceDraft(instanceId);
    if (!result.ok) {
      throw result.error;
    }
    if (changed && beforeSnapshot) {
      state.undoStack = [...(state.undoStack || []), { label: "保存实例编辑", snapshot: beforeSnapshot }];
      state.redoStack = [];
    }
    await refreshInstances("已保存", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function fallbackCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-1000px";
  textarea.style.left = "-1000px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("浏览器拒绝复制");
  }
}

async function copyInstancePrompt(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  const instance = instanceById(instanceId);
  const prompt = draft?.prompt ?? instance?.prompt ?? "";

  try {
    let copied = false;
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(prompt);
        copied = true;
      } catch (error) {
        copied = false;
      }
    }
    if (!copied) {
      fallbackCopyText(prompt);
    }
    setMessage("已复制提示词", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(`复制失败：${error.message}`, "error");
    }
  }
}

function historyRecordById(historyId) {
  return (state.history.items || []).find((item) => String(item.id) === String(historyId));
}

function historyFieldCopyText(record, field) {
  if (!record) {
    return "";
  }
  if (field && field.startsWith("error:")) {
    const index = Number.parseInt(field.slice("error:".length), 10);
    const errors = historyErrorRecords(record);
    return Number.isFinite(index) ? (errors[index]?.error_message || "") : "";
  }
  if (field === "prompt") {
    return record.prompt || "";
  }
  if (field === "params") {
    return formatParamsBlock(record.params || {});
  }
  if (field === "error") {
    return record.error_message || "";
  }
  return "";
}

async function copyHistoryField(historyId, field) {
  const record = historyRecordById(historyId);
  const text = historyFieldCopyText(record, field);
  const labelMap = {
    prompt: "指令",
    params: "参数",
    error: "错误",
  };
  const label = field && field.startsWith("error:") ? "错误" : (labelMap[field] || "内容");
  if (!record) {
    setMessage("历史记录不在当前页，请刷新后重试", "error");
    return;
  }
  if (!text) {
    setMessage(`没有可复制的${label}`, "info");
    return;
  }

  try {
    let copied = false;
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch (error) {
        copied = false;
      }
    }
    if (!copied) {
      fallbackCopyText(text);
    }
    setMessage(`已复制${label}`, "success");
  } catch (error) {
    setMessage(`复制失败：${error.message}`, "error");
  }
}

async function deleteInstance(instanceId) {
  const confirmed = window.confirm("确认删除这条实例？\n这只会删除软件中的记录，不会删除电脑上的图片文件。");
  if (!confirmed) {
    return;
  }

  try {
    setMessage("");
    await runUndoableAction("删除实例", async () => {
      await api(`/api/instances/${encodeURIComponent(instanceId)}`, { method: "DELETE" });
    });
    state.editing.delete(Number(instanceId));
    ensureSelectedInstanceIds().delete(String(instanceId));
    await refreshInstances("已删除", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function moveInstance(instanceId) {
  const nodeId = await chooseMoveNode("移动实例");
  if (nodeId === undefined) {
    return;
  }
  try {
    setMessage("");
    await runUndoableAction("移动实例", async () => {
      await api(`/api/instances/${encodeURIComponent(instanceId)}/move`, {
        method: "POST",
        body: { node_id: nodeId },
      });
    });
    await refreshInstances("已移动", "success");
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function createManualInstance() {
  try {
    setMessage("");
    const createCount = currentSaveLayout() === "double" ? 2 : 1;
    const data = await runUndoableAction("新增手动实例", async () => (
      api("/api/instances/bulk", {
        method: "POST",
        body: {
          items: Array.from({ length: createCount }, () => ({
            prompt: "新实例",
            source: "manual",
            mode: "unspecified",
            input_image_paths: [],
            output_image_path: "",
            tags: [],
          })),
        },
      })
    ));
    state.filters.q = "";
    state.filters.tags = [];
    state.filters.source = "all";
    state.filters.mode_filter = "all";
    state.filters.status = "all";
    state.filters.statuses = [];
    state.filters.status_dropdown_open = false;
    state.filters.size = "all";
    state.filters.call_method = "all";
    state.filters.model = "all";
    state.filters.sort = "created_desc";
    state.filters.page = 1;
    clearCurrentPageSelection();
    persistUiState();
    await loadInstances();
    await loadTags();
    const createdItems = Array.isArray(data.items) ? data.items : [];
    state.editing.clear();
    for (const createdItem of createdItems) {
      const item = state.instances.find((instance) => instance.id === createdItem.id) || createdItem;
      state.editing.set(Number(item.id), cloneInstanceForEdit(item));
    }
    renderManager();
    setMessage("已新增，请直接编辑", "success");
    const firstItem = createdItems[0];
    if (!firstItem) {
      return;
    }
    const promptInput = document.querySelector(
      `[data-instance-card][data-id="${CSS.escape(String(firstItem.id))}"] [name="instance_prompt"]`,
    );
    promptInput?.focus();
    promptInput?.select();
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function chooseInstanceInputImages(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  if (!draft) {
    return;
  }

  try {
    setMessage("");
    const data = await api("/api/dialogs/images", { method: "POST" });
    const paths = Array.isArray(data.paths) ? data.paths : [];
    draft.input_image_paths.push(...paths);
    renderManagerIfActive();
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function removeInstanceInputImage(instanceId, index) {
  const draft = syncInstanceDraftFromDom(instanceId);
  if (!draft) {
    return;
  }
  draft.input_image_paths.splice(index, 1);
  renderManager();
}

function clearInstanceInputImages(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  if (!draft) {
    return;
  }
  draft.input_image_paths = [];
  renderManager();
}

async function chooseInstanceOutputImage(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  if (!draft) {
    return;
  }

  try {
    setMessage("");
    const data = await api("/api/dialogs/images", { method: "POST" });
    const paths = Array.isArray(data.paths) ? data.paths : [];
    if (paths[0]) {
      draft.output_image_path = paths[0];
      renderManagerIfActive();
    }
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function removeInstanceOutputImage(instanceId) {
  const draft = syncInstanceDraftFromDom(instanceId);
  if (!draft) {
    return;
  }
  draft.output_image_path = "";
  renderManager();
}

async function addInstanceTagImmediate(instanceId, tag, options = {}) {
  const tagText = String(tag || "").trim();
  if (!tagText) {
    return;
  }
  try {
    const data = await runUndoableAction("添加实例标签", async () => (
      api(`/api/instances/${encodeURIComponent(instanceId)}/tags/add`, {
        method: "POST",
        body: { tags: [tagText] },
      })
    ));
    if (Array.isArray(data.tags)) {
      state.tagOptions = data.tags;
    } else {
      await loadTags();
    }
    await loadInstances();
    if (options.keepOpen) {
      openTagSelector("instance", instanceId);
    } else {
      renderManagerIfActive();
    }
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function removeInstanceTagImmediate(instanceId, tag, options = {}) {
  const tagText = String(tag || "").trim();
  if (!tagText) {
    return;
  }
  try {
    const data = await runUndoableAction("删除实例标签", async () => (
      api(`/api/instances/${encodeURIComponent(instanceId)}/tags/remove`, {
        method: "POST",
        body: { tags: [tagText] },
      })
    ));
    if (Array.isArray(data.tags)) {
      state.tagOptions = data.tags;
    } else {
      await loadTags();
    }
    await loadInstances();
    if (options.keepOpen) {
      openTagSelector("instance", instanceId);
    } else {
      renderManagerIfActive();
    }
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

async function clearInstanceTagsImmediate(instanceId, options = {}) {
  try {
    const data = await runUndoableAction("清空实例标签", async () => (
      api(`/api/instances/${encodeURIComponent(instanceId)}/tags/clear`, {
        method: "POST",
        body: {},
      })
    ));
    if (Array.isArray(data.tags)) {
      state.tagOptions = data.tags;
    } else {
      await loadTags();
    }
    await loadInstances();
    if (options.keepOpen) {
      openTagSelector("instance", instanceId);
    } else {
      renderManagerIfActive();
    }
  } catch (error) {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  }
}

function addInstanceTag(instanceId) {
  const target = tagTarget("instance", instanceId);
  const draft = String(target?.tag_draft || "").trim();
  const exact = (state.tagOptions || []).find(
    (tag) => tag.toLowerCase() === draft.toLowerCase(),
  );
  addInstanceTagImmediate(instanceId, exact || draft, { keepOpen: true });
}

function removeInstanceTag(instanceId, index) {
  const target = tagTarget("instance", instanceId);
  const tag = target?.tags?.[index] || "";
  removeInstanceTagImmediate(instanceId, tag);
}

function changeSavePage(delta) {
  const totalPages = Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50)));
  setSavePage(Math.min(totalPages, Math.max(1, (state.filters.page || 1) + delta)));
}

function setSavePage(page) {
  const totalPages = Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50)));
  state.filters.page = Math.min(totalPages, Math.max(1, Number.parseInt(page, 10) || 1));
  markSavePageNavigation();
  state.editing.clear();
  clearCurrentPageSelection();
  persistUiState();
  refreshInstances().catch((error) => {
    if (state.page === "manager") {
      setMessage(error.message, "error");
    }
  });
}

async function setSaveLayout(layout) {
  const nextLayout = layout === "single" ? "single" : "double";
  if (!state.settings) {
    return;
  }
  syncOperationFromDom();
  state.settings.save_layout = nextLayout;
  renderManager();
  try {
    await saveLayoutPreference(nextLayout);
  } catch (error) {
    if (state.page === "manager") {
      setMessage(`显示方式已切换，但保存默认值失败：${error.message}`, "error");
    }
  }
}

function toggleSaveThumbnailView() {
  syncOperationFromDom();
  state.saveViewMode = state.saveViewMode === "thumbnail" ? "list" : "thumbnail";
  pruneSelectionToCurrentPage();
  persistUiState();
  renderManager();
  globalThis.stabilizeSaveAreaImages?.({ forceVisible: true, reason: "toggle-thumbnail-view" });
}

function renderPathPreview(preview) {
  const examples = Array.isArray(preview.examples) ? preview.examples : [];
  return `
    <p>影响实例：${escapeHtml(preview.matched_instances || 0)} 条；影响路径：${escapeHtml(preview.matched_paths || 0)} 个。</p>
    <div class="preview-list">
      ${examples
        .map(
          (item) => `
            <div class="preview-item">
              <div>修改前：${escapeHtml(item.before)}</div>
              <div>修改后：${escapeHtml(item.after)}</div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function makeDialogDraggable(dialog, modal) {
  const handle = modal?.querySelector("[data-dialog-drag-handle]");
  if (!dialog || !modal || !handle) {
    return;
  }
  let dragging = false;
  let offsetX = 0;
  let offsetY = 0;
  const stopDragging = () => {
    dragging = false;
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", stopDragging);
  };
  function onMove(event) {
    if (!dragging) {
      return;
    }
    const maxLeft = Math.max(0, window.innerWidth - modal.offsetWidth);
    const maxTop = Math.max(0, window.innerHeight - modal.offsetHeight);
    const nextLeft = Math.min(Math.max(0, event.clientX - offsetX), maxLeft);
    const nextTop = Math.min(Math.max(0, event.clientY - offsetY), maxTop);
    modal.style.left = `${nextLeft}px`;
    modal.style.top = `${nextTop}px`;
  }
  handle.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button, input, textarea, select")) {
      return;
    }
    const rect = modal.getBoundingClientRect();
    dragging = true;
    offsetX = event.clientX - rect.left;
    offsetY = event.clientY - rect.top;
    modal.style.position = "fixed";
    modal.style.margin = "0";
    modal.style.left = `${rect.left}px`;
    modal.style.top = `${rect.top}px`;
    dialog.style.placeItems = "stretch";
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", stopDragging);
  });
}

function openPathReplaceDialog() {
  document.querySelector("[data-path-replace-dialog]")?.remove();

  const dialog = document.createElement("div");
  dialog.className = "modal-backdrop";
  dialog.dataset.pathReplaceDialog = "true";
  dialog.dataset.skipBatchSave = "true";
  dialog.innerHTML = `
    <div class="modal path-replace-modal" role="dialog" aria-modal="true" aria-labelledby="path-replace-title">
      <div class="modal-title-row" data-dialog-drag-handle>
        <h2 id="path-replace-title">路径替换</h2>
      </div>
      <label class="field">
        <span>查找内容 A</span>
        <input id="replace-find" placeholder="例如 C:\\old">
      </label>
      <label class="field">
        <span>替换为 B</span>
        <input id="replace-with" placeholder="例如 D:\\new">
      </label>
      <div class="actions">
        <button type="button" id="preview-replace">预览影响</button>
        <button type="button" class="primary" id="apply-replace" disabled>确认替换</button>
        <button type="button" id="close-replace">关闭</button>
      </div>
      <div id="replace-preview" class="preview-box"></div>
    </div>
  `;
  document.body.appendChild(dialog);

  const findInput = dialog.querySelector("#replace-find");
  const replaceInput = dialog.querySelector("#replace-with");
  const previewBox = dialog.querySelector("#replace-preview");
  const applyButton = dialog.querySelector("#apply-replace");
  const previewButton = dialog.querySelector("#preview-replace");
  const modal = dialog.querySelector(".path-replace-modal");
  makeDialogDraggable(dialog, modal);

  const resetPreview = () => {
    applyButton.disabled = true;
    previewBox.textContent = "";
  };

  findInput.addEventListener("input", resetPreview);
  replaceInput.addEventListener("input", resetPreview);
  dialog.querySelector("#close-replace").addEventListener("click", () => dialog.remove());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.remove();
    }
  });

  previewButton.addEventListener("click", async () => {
    try {
      previewBox.textContent = "正在预览";
      applyButton.disabled = true;
      const preview = await api("/api/paths/replace/preview", {
        method: "POST",
        body: { find: findInput.value, replace: replaceInput.value },
      });
      previewBox.innerHTML = renderPathPreview(preview);
      applyButton.disabled = Number(preview.matched_paths || 0) === 0;
    } catch (error) {
      previewBox.textContent = error.message;
      applyButton.disabled = true;
    }
  });

  applyButton.addEventListener("click", async () => {
    const confirmed = window.confirm("确认替换数据库中的图片路径？\n替换前会自动备份数据库，不会移动或删除电脑上的图片文件。");
    if (!confirmed) {
      return;
    }

    try {
      applyButton.disabled = true;
      previewBox.textContent = "正在替换";
      const result = await api("/api/paths/replace/apply", {
        method: "POST",
        body: { find: findInput.value, replace: replaceInput.value },
      });
      previewBox.innerHTML = `
        <p>已替换 ${escapeHtml(result.matched_paths || 0)} 个路径。</p>
        <p>备份：${escapeHtml(result.backup_path || "")}</p>
      `;
      await loadInstances();
      renderManagerIfActive();
    } catch (error) {
      previewBox.textContent = error.message;
      applyButton.disabled = false;
    }
  });
}


Object.assign(globalThis, {
  ensureSelectedInstanceIds,
  clearCurrentPageSelection,
  toggleSelectInstance,
  toggleSelectInstanceFromZone,
  selectCurrentPageInstances,
  selectedInstanceIds,
  hasSelectedInstances,
  createSessionSnapshot,
  restoreSessionSnapshot,
  pushUndoSnapshot,
  runUndoableAction,
  undoLastAction,
  redoLastAction,
  splitTagText,
  chooseBatchTags,
  batchAddTags,
  batchRemoveTags,
  batchDeleteInstances,
  batchMoveInstances,
  copyInstanceToPreparedPayload,
  batchCopyInstances,
  formatPendingTimerText,
  updatePendingTimerNodes,
  startPendingTimer,
  stopPendingTimerIfIdle,
  hasRunningInstances,
  markManagerInteraction,
  shouldDeferRunningRefreshRender,
  markSavePageNavigation,
  refreshSaveAreaOnly,
  stopRunningRefresh,
  startRunningRefresh,
  syncRunningRefresh,
  wakeVisibleSaveImages,
  chooseInputImages,
  removeInputImage,
  clearOperationInputImages,
  setClipboardImageTarget,
  setClipboardImageTargetFromNode,
  applyClipboardImagePaths,
  pasteClipboardImagePaths,
  chooseGenerationPath,
  addGenerationPathHistory,
  addSuccessfulProviderFieldHistory,
  recordSuccessfulProviderFieldHistory,
  recordSuccessfulGenerationHistories,
  clearOperation,
  clearOperationPrompt,
  clearPromptSearch,
  clearInstancePrompt,
  normalizeBringInTags,
  bringInRecordTags,
  providerExists,
  chooseAvailableProviderForBringIn,
  resolveBringInProvider,
  normalizeBringInParams,
  applyBringInToOperation,
  bringInstanceToOperation,
  bringHistoryToOperation,
  operationPayload,
  inferOperationModeFromInputs,
  generationParamsForDraft,
  draftInstancePayloadFromGenerationPayload,
  generationOptionsForInstance,
  copiedGenerationSizeForInstance,
  pendingInstanceCountForPayload,
  validateInstanceGenerationCount,
  instanceGenerationCountInputValue,
  createPendingInstancesForTask,
  markInstanceRunningInPlace,
  removePendingInstancesForTask,
  generateFromOperation,
  addOperationDraft,
  resubmitInstance,
  copySubmitInstance,
  copyHistoryField,
  historyFieldCopyText,
  retryFailedInstance,
  submitManualInstance,
  submitSelectedInstances,
  cancelGenerationTask,
  instancePayload,
  normalizedInstancePayloadString,
  hasInstanceDraftChanged,
  persistInstanceDraft,
  refreshInstances,
  batchSaveEditingInstances,
  isInteractiveTarget,
  shouldSkipBatchSave,
  handleBatchSaveBoundary,
  handleDocumentBatchSaveBoundary,
  applySaveFilters,
  toggleSaveStatusFilter,
  clearSaveStatusFilter,
  applyHistoryFilters,
  toggleHistoryFilterTag,
  clearHistoryTagFilter,
  changeHistoryPage,
  setHistoryPage,
  clearTagFilter,
  toggleSaveThumbnailView,
  startEditingInstance,
  cancelEditingInstance,
  cancelAllEditingInstances,
  saveInstanceDraft,
  fallbackCopyText,
  copyInstancePrompt,
  deleteInstance,
  moveInstance,
  createManualInstance,
  chooseInstanceInputImages,
  removeInstanceInputImage,
  clearInstanceInputImages,
  chooseInstanceOutputImage,
  removeInstanceOutputImage,
  addInstanceTag,
  removeInstanceTag,
  addInstanceTagImmediate,
  removeInstanceTagImmediate,
  clearInstanceTagsImmediate,
  changeSavePage,
  setSavePage,
  setSaveLayout,
  renderPathPreview,
  makeDialogDraggable,
  openPathReplaceDialog,
});
