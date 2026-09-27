async function loadInstances() {
  const requestSeq = (state.instanceListRequestSeq || 0) + 1;
  state.instanceListRequestSeq = requestSeq;
  state.filters.page = normalizePositiveInteger(state.filters.page);
  state.filters.per_page = normalizeSavePerPage(state.filters.per_page);
  const requestedPage = state.filters.page;
  const params = new URLSearchParams();
  params.set("q", state.filters.q || "");
  params.set("mode_filter", state.filters.mode_filter || "all");
  params.set("provider", state.filters.provider || "all");
  for (const status of normalizeSavedStatuses(state.filters.statuses, state.filters.status)) {
    params.append("statuses", status);
  }
  params.set("size", state.filters.size || "all");
  params.set("call_method", state.filters.call_method || "all");
  params.set("model", state.filters.model || "all");
  const nodeQuery = currentNodeQuery();
  params.set("node_filter_type", nodeQuery.node_filter_type || "all");
  if (nodeQuery.node_id) {
    params.set("node_id", String(nodeQuery.node_id));
  }
  params.set("start_date", state.filters.start_date || "");
  params.set("end_date", state.filters.end_date || "");
  params.set("sort", state.filters.sort || "created_desc");
  params.set("page", String(requestedPage));
  params.set("per_page", String(state.filters.per_page));
  for (const tag of state.filters.tags || []) {
    params.append("tags", tag);
  }

  const data = await api(`/api/instances?${params.toString()}`);
  if (requestSeq !== state.instanceListRequestSeq) {
    return false;
  }
  state.instances = Array.isArray(data.items) ? data.items : [];
  loadInstanceFilterOptions().catch(() => {});
  syncCancellingGenerationTasksWithInstances();
  if (state.selectedInstanceIds instanceof Set) {
    const currentIds = new Set(
      state.instances
        .filter((item) => item.generation_status !== "running")
        .map((item) => String(item.id)),
    );
    for (const id of [...state.selectedInstanceIds]) {
      if (!currentIds.has(String(id))) {
        state.selectedInstanceIds.delete(id);
      }
    }
  }
  if (typeof pruneSelectionToCurrentPage === "function") {
    pruneSelectionToCurrentPage();
  }
  state.total = Number.isFinite(data.total) ? data.total : state.instances.length;
  state.filters.per_page = normalizeSavePerPage(data.per_page || state.filters.per_page);
  const responsePage = Number.isFinite(data.page) ? data.page : requestedPage;
  const normalizedPage = normalizePageForTotal(responsePage, state.total, state.filters.per_page);
  state.filters.page = normalizedPage;
  if (shouldReloadForNormalizedPage(requestedPage, normalizedPage)) {
    persistUiState();
    return loadInstances();
  }
  return true;
}

function syncCancellingGenerationTasksWithInstances() {
  if (!(state.cancellingGenerationTaskIds instanceof Set)) {
    state.cancellingGenerationTaskIds = new Set(state.cancellingGenerationTaskIds || []);
  }
  const runningTaskIds = new Set();
  for (const item of state.instances || []) {
    const taskId = String(item.generation_task_id || item.task_id || "").trim();
    if (taskId && item.generation_status === "running") {
      runningTaskIds.add(taskId);
      if (state.cancellingGenerationTaskIds.has(taskId)) {
        item.cancelling = true;
      }
    }
  }
  for (const item of state.pendingInstances || []) {
    const taskId = String(item.generation_task_id || item.task_id || "").trim();
    if (taskId && state.cancellingGenerationTaskIds.has(taskId)) {
      item.cancelling = true;
    }
  }
  for (const taskId of [...state.cancellingGenerationTaskIds]) {
    const hasPending = (state.pendingInstances || []).some((item) =>
      String(item.generation_task_id || item.task_id || "").trim() === taskId
    );
    if (!runningTaskIds.has(taskId) && !hasPending) {
      state.cancellingGenerationTaskIds.delete(taskId);
    }
  }
}

async function loadTags() {
  const data = await api("/api/tags");
  state.tagOptions = Array.isArray(data.items) ? data.items : [];
}

async function loadGenerationPathHistory() {
  const data = await api("/api/generation-path-history");
  const sharedPaths = cleanStringArray(data.paths || []);
  const localPaths = cleanStringArray(state.generationPathHistory || []);
  state.generationPathHistory = [...new Set([...sharedPaths, ...localPaths])].slice(0, 20);
  persistUiState();
  return state.generationPathHistory;
}

async function loadProviderFieldHistory() {
  const data = await api("/api/provider-field-history");
  const shared = safeObject(data.history);
  const local = safeObject(state.successfulProviderFieldHistory);
  state.settingsSharedProviderFieldHistory = {
    api_key_env: cleanStringArray(shared.api_key_env).slice(0, 20),
    model: cleanStringArray(shared.model).slice(0, 20),
    user_agent: cleanStringArray(shared.user_agent).slice(0, 20),
  };
  state.successfulProviderFieldHistory = {
    api_key_env: [...new Set([
      ...cleanStringArray(state.settingsSharedProviderFieldHistory.api_key_env),
      ...cleanStringArray(local.api_key_env),
    ])].slice(0, 20),
    model: [...new Set([
      ...cleanStringArray(state.settingsSharedProviderFieldHistory.model),
      ...cleanStringArray(local.model),
    ])].slice(0, 20),
    user_agent: [...new Set([
      ...cleanStringArray(state.settingsSharedProviderFieldHistory.user_agent),
      ...cleanStringArray(local.user_agent),
    ])].slice(0, 20),
  };
  persistUiState();
  return state.successfulProviderFieldHistory;
}

async function loadInstanceFilterOptions() {
  const data = await api("/api/instances/filter-options");
  state.filters.filterOptions = {
    providers: Array.isArray(data.providers) ? data.providers : [],
    sizes: Array.isArray(data.sizes) ? data.sizes : [],
    call_methods: Array.isArray(data.call_methods) ? data.call_methods : [],
    models: Array.isArray(data.models) ? data.models : [],
    statuses: Array.isArray(data.statuses) ? data.statuses : [],
  };
}

async function loadGenerationHistory() {
  closeHistoryTextPopover();
  state.history.loading = true;
  state.history.error = "";
  if (state.page === "history") {
    renderHistoryPage();
  }
  state.history.page = normalizePositiveInteger(state.history.page);
  state.history.per_page = normalizeHistoryPerPage(state.history.per_page);
  const requestedPage = state.history.page;
  const params = new URLSearchParams();
  params.set("q", state.history.q || "");
  params.set("status", state.history.status || "all");
  params.set("provider", state.history.provider || "all");
  params.set("size", state.history.size || "all");
  params.set("mode", state.history.mode || "all");
  params.set("call_method", state.history.call_method || "all");
  params.set("model", state.history.model || "all");
  params.set("number_type", state.history.number_type || "all");
  params.set("start_date", state.history.start_date || "");
  params.set("end_date", state.history.end_date || "");
  params.set("save_sort", state.filters.sort || "created_desc");
  params.set("page", String(requestedPage));
  params.set("per_page", String(state.history.per_page));
  for (const tag of state.history.tags || []) {
    params.append("tags", tag);
  }
  try {
    const data = await api(`/api/generation-history?${params.toString()}`);
    state.history.items = Array.isArray(data.items) ? data.items : [];
    state.history.total = Number.isFinite(data.total) ? data.total : state.history.items.length;
    state.history.per_page = normalizeHistoryPerPage(data.per_page || state.history.per_page);
    const responsePage = Number.isFinite(data.page) ? data.page : requestedPage;
    const normalizedPage = normalizePageForTotal(responsePage, state.history.total, state.history.per_page);
    state.history.page = normalizedPage;
    if (shouldReloadForNormalizedPage(requestedPage, normalizedPage)) {
      persistUiState();
      return loadGenerationHistory();
    }
    state.history.loading = false;
    state.history.error = "";
    loadGenerationHistoryFilterOptions().catch(() => {});
  } catch (error) {
    state.history.loading = false;
    state.history.error = error.message;
    throw error;
  } finally {
    if (state.page === "history") {
      renderHistoryPage();
    }
  }
}

async function loadGenerationHistoryFilterOptions() {
  try {
    const data = await api("/api/generation-history/filter-options");
    state.history.filterOptions = {
      providers: Array.isArray(data.providers) ? data.providers : [],
      sizes: Array.isArray(data.sizes) ? data.sizes : [],
      modes: Array.isArray(data.modes) ? data.modes : [],
      call_methods: Array.isArray(data.call_methods) ? data.call_methods : [],
      models: Array.isArray(data.models) ? data.models : [],
      statuses: Array.isArray(data.statuses) ? data.statuses : [],
      tags: Array.isArray(data.tags) ? data.tags : [],
    };
  } catch (error) {
    state.history.error = error.message;
    throw error;
  } finally {
    if (state.page === "history") {
      renderHistoryPage();
    }
  }
}

function historyCleanupSafetyText() {
  return "此操作不会删除保存区实例，也不会删除电脑上的图片文件。";
}

async function previewGenerationHistoryCleanup(payload) {
  return api("/api/generation-history/cleanup/preview", {
    method: "POST",
    body: payload,
  });
}

async function runGenerationHistoryCleanup(payload, endpoint, successPrefix) {
  if (state.history.cleanup?.running) {
    return;
  }
  state.history.cleanup = {
    ...(state.history.cleanup || {}),
    running: true,
  };
  state.history.error = "";
  renderHistoryPage();
  try {
    const preview = await previewGenerationHistoryCleanup(payload);
    const count = Number(preview.matched_count || 0);
    const label = payload.type === "before_date"
      ? `将删除 ${count} 条 ${payload.before_date} 之前的非生成中历史记录。`
      : `将删除 ${count} 条失败历史记录。`;
    const confirmed = window.confirm(`${label}${historyCleanupSafetyText()}确定继续？`);
    if (!confirmed) {
      return;
    }
    const result = await api(endpoint, {
      method: "POST",
      body: payload.type === "before_date" ? { before_date: payload.before_date } : {},
    });
    state.history.error = "";
    state.history.cleanup = {
      ...(state.history.cleanup || {}),
      running: false,
    };
    await loadGenerationHistoryFilterOptions();
    await loadGenerationHistory();
    setMessage(`${successPrefix} ${Number(result.deleted || 0)} 条`, "success");
  } catch (error) {
    state.history.error = error.message;
    if (state.page === "history") {
      setMessage(error.message, "error");
    }
  } finally {
    state.history.cleanup = {
      ...(state.history.cleanup || {}),
      running: false,
    };
    if (state.page === "history") {
      renderHistoryPage();
    }
  }
}

async function cleanupFailedHistory() {
  await runGenerationHistoryCleanup(
    { type: "failed" },
    "/api/generation-history/cleanup/failed",
    "已删除失败历史记录",
  );
}

async function cleanupHistoryBeforeDate() {
  const beforeDate = String(
    document.querySelector('[name="history_cleanup_before_date"]')?.value
      || state.history.cleanup?.before_date
      || "",
  ).trim();
  state.history.cleanup = {
    ...(state.history.cleanup || {}),
    before_date: beforeDate,
  };
  if (!beforeDate) {
    state.history.error = "请选择清理日期";
    renderHistoryPage();
    return;
  }
  await runGenerationHistoryCleanup(
    { type: "before_date", before_date: beforeDate },
    "/api/generation-history/cleanup/before-date",
    "已删除日期之前历史记录",
  );
}

async function loadBackups() {
  state.dataSafety.loading = true;
  state.dataSafety.error = "";
  if (state.page === "data-safety") {
    renderDataSafetyPage();
  }
  try {
    const data = await api("/api/backups");
    state.dataSafety.backups = Array.isArray(data.items) ? data.items : [];
    state.dataSafety.loading = false;
    state.dataSafety.error = "";
  } catch (error) {
    state.dataSafety.loading = false;
    state.dataSafety.error = error.message;
    throw error;
  } finally {
    renderDataSafetyIfActive();
  }
}

async function loadThumbnailCacheStats() {
  try {
    const data = await api("/api/thumbnails/stats");
    state.dataSafety.thumbnailCache = {
      file_count: Number.isFinite(data.file_count) ? data.file_count : 0,
      size_label: data.size_label || "0 B",
      path: data.path || "",
    };
  } catch (error) {
    state.dataSafety.error = error.message;
    throw error;
  } finally {
    renderDataSafetyIfActive();
  }
}

async function createBackup() {
  state.dataSafety.backingUp = true;
  state.dataSafety.error = "";
  state.dataSafety.status = "正在备份";
  renderDataSafetyIfActive();
  try {
    const item = await api("/api/backups", {
      method: "POST",
      body: { backup_type: "manual" },
    });
    state.dataSafety.status = `已创建备份：${item.file_name || item.path || ""}`;
    await loadBackups();
  } catch (error) {
    state.dataSafety.error = error.message;
  } finally {
    state.dataSafety.backingUp = false;
    renderDataSafetyIfActive();
  }
}

async function clearThumbnailCache() {
  const confirmed = window.confirm("清理缩略图缓存不会删除原图，也不会修改数据库。确认清理？");
  if (!confirmed) {
    return;
  }
  state.dataSafety.clearingThumbnails = true;
  state.dataSafety.error = "";
  state.dataSafety.status = "正在清理缩略图缓存";
  renderDataSafetyIfActive();
  try {
    const result = await api("/api/thumbnails/clear", { method: "POST" });
    const deletedCount = Number.isFinite(result.deleted_count) ? result.deleted_count : 0;
    const deletedSize = result.deleted_size_label || "0 B";
    const failedCount = Number.isFinite(result.failed_count) ? result.failed_count : 0;
    state.dataSafety.status = failedCount
      ? `已清理 ${deletedCount} 个缩略图，${failedCount} 个文件未能删除`
      : `已清理 ${deletedCount} 个缩略图，共 ${deletedSize}`;
    await loadThumbnailCacheStats();
  } catch (error) {
    state.dataSafety.error = error.message;
  } finally {
    state.dataSafety.clearingThumbnails = false;
    renderDataSafetyIfActive();
  }
}

function dataSummaryText(summary) {
  if (!summary || typeof summary !== "object") {
    return "";
  }
  return [
    `实例 ${summary.instance_count || 0}`,
    `输入图 ${summary.input_image_count || 0}`,
    `输出图 ${summary.output_image_count || 0}`,
    `标签 ${summary.tag_count || 0}`,
    `节点 ${summary.node_count || 0}`,
    `历史 ${summary.generation_history_count || 0}`,
    `Provider ${summary.provider_count || 0}`,
  ].join(" · ");
}

async function pollExportTask() {
  if (!state.dataSafety.exportTaskId) {
    return;
  }
  try {
    const task = await api(`/api/exports/tasks/${state.dataSafety.exportTaskId}`);
    state.dataSafety.exportTask = task;
    if (task.status === "running") {
      state.dataSafety.status = task.total_rows
        ? `${task.message || "正在导出数据"}：${task.processed_rows || 0} / ${task.total_rows || 0}`
        : task.message || "正在导出数据";
      renderDataSafetyIfActive();
      window.setTimeout(pollExportTask, 800);
      return;
    }
    if (task.status === "success") {
      state.dataSafety.status = `导出完成：${dataSummaryText(task.summary)}；${task.path || ""}`;
      state.dataSafety.exporting = false;
      renderDataSafetyIfActive();
      return;
    }
    state.dataSafety.error = task.error || "导出失败";
    state.dataSafety.exporting = false;
  } catch (error) {
    state.dataSafety.error = error.message;
    state.dataSafety.exporting = false;
  } finally {
    renderDataSafetyIfActive();
  }
}

async function exportDataPackage() {
  state.dataSafety.exporting = true;
  state.dataSafety.error = "";
  state.dataSafety.status = "正在导出数据";
  state.dataSafety.exportTask = null;
  state.dataSafety.exportTaskId = "";
  renderDataSafetyIfActive();
  try {
    const result = await api("/api/exports", { method: "POST" });
    state.dataSafety.exportTaskId = result.task_id || "";
    await pollExportTask();
  } catch (error) {
    state.dataSafety.error = error.message;
    state.dataSafety.exporting = false;
    renderDataSafetyIfActive();
  }
}

async function previewRestoreFile(path) {
  if (!path) {
    state.dataSafety.restorePreview = null;
    return;
  }
  state.dataSafety.restorePreview = null;
  state.dataSafety.status = "正在校验恢复文件";
  renderDataSafetyIfActive();
  try {
    const preview = await api("/api/restore/preview", {
      method: "POST",
      body: { path },
    });
    state.dataSafety.restorePreview = preview;
    state.dataSafety.status = `恢复预览：${dataSummaryText(preview.summary)}`;
  } catch (error) {
    state.dataSafety.error = error.message;
    state.dataSafety.restorePreview = null;
  } finally {
    renderDataSafetyIfActive();
  }
}

async function chooseBackup() {
  state.dataSafety.error = "";
  try {
    const result = await api("/api/backups/choose", { method: "POST" });
    if (result.path) {
      state.dataSafety.selectedBackupPath = result.path;
      state.dataSafety.status = "已选择备份文件";
      await previewRestoreFile(result.path);
    }
  } catch (error) {
    state.dataSafety.error = error.message;
  } finally {
    renderDataSafetyIfActive();
  }
}

async function openBackupFolder() {
  state.dataSafety.error = "";
  try {
    await api("/api/backups/open-folder", { method: "POST" });
    state.dataSafety.status = "已打开备份文件夹";
  } catch (error) {
    state.dataSafety.error = error.message;
  } finally {
    renderDataSafetyIfActive();
  }
}

async function restoreSelectedBackup() {
  const path = state.dataSafety.selectedBackupPath || "";
  if (!path) {
    state.dataSafety.error = "请先选择备份文件";
    renderDataSafetyIfActive();
    return;
  }
  if (hasRunningGenerationTasks()) {
    state.dataSafety.error = "当前有生成任务正在进行，不能恢复备份";
    renderDataSafetyIfActive();
    return;
  }
  const confirmed = window.confirm(
    "恢复会替换当前数据库和设置。恢复前会自动备份当前数据。不会删除任何图片文件。确认恢复？",
  );
  if (!confirmed) {
    return;
  }

  state.dataSafety.restoring = true;
  state.dataSafety.error = "";
  state.dataSafety.status = "正在创建恢复前备份";
  renderDataSafetyIfActive();
  try {
    const result = await api("/api/restore", {
      method: "POST",
      body: { path, confirmed: true },
    });
    const fixes = result.reference_fixes || {};
    const fixTotal = Object.values(fixes).reduce((sum, value) => sum + (Number(value) || 0), 0);
    const preRestorePath = result.pre_restore_backup?.path || "";
    state.dataSafety.status = fixTotal
      ? `恢复完成：${dataSummaryText(result.summary)}；已自动创建恢复前备份：${preRestorePath}；修正引用 ${fixTotal} 项。请刷新页面后继续使用。`
      : `恢复完成：${dataSummaryText(result.summary)}；已自动创建恢复前备份：${preRestorePath}；引用检查通过。请刷新页面后继续使用。`;
    state.dataSafety.restorePreview = null;
    await loadBackups();
  } catch (error) {
    state.dataSafety.error = error.message;
  } finally {
    state.dataSafety.restoring = false;
    renderDataSafetyIfActive();
  }
}


Object.assign(globalThis, {
  loadInstances,
  loadTags,
  loadGenerationPathHistory,
  loadProviderFieldHistory,
  loadInstanceFilterOptions,
  loadGenerationHistory,
  loadGenerationHistoryFilterOptions,
  historyCleanupSafetyText,
  previewGenerationHistoryCleanup,
  runGenerationHistoryCleanup,
  cleanupFailedHistory,
  cleanupHistoryBeforeDate,
  loadBackups,
  loadThumbnailCacheStats,
  createBackup,
  clearThumbnailCache,
  dataSummaryText,
  pollExportTask,
  exportDataPackage,
  previewRestoreFile,
  chooseBackup,
  openBackupFolder,
  restoreSelectedBackup,
});
