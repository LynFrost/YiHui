function backupTypeLabel(type) {
  const labels = {
    manual: "手动备份",
    auto: "自动备份",
    pre_restore: "恢复前备份",
    pre_migration: "迁移前备份",
  };
  return labels[type] || type || "未知";
}

function hasRunningGenerationTasks() {
  return (state.generationTasks || []).some((task) => task.status === "running");
}

function renderDataSummary(summary) {
  if (!summary || typeof summary !== "object") {
    return `<span>摘要不可用</span>`;
  }
  return `
    <span>实例 ${escapeHtml(summary.instance_count || 0)}</span>
    <span>输入图 ${escapeHtml(summary.input_image_count || 0)}</span>
    <span>输出图 ${escapeHtml(summary.output_image_count || 0)}</span>
    <span>标签 ${escapeHtml(summary.tag_count || 0)}</span>
    <span>节点 ${escapeHtml(summary.node_count || 0)}</span>
    <span>历史 ${escapeHtml(summary.generation_history_count || 0)}</span>
    <span>Provider ${escapeHtml(summary.provider_count || 0)}</span>
  `;
}

function renderRestorePreview() {
  const preview = state.dataSafety.restorePreview;
  if (!preview) {
    return `<p class="data-safety-note">选择恢复文件后会先显示数据摘要。缩略图缓存不是核心数据，恢复后会按需重新生成。</p>`;
  }
  const warnings = Array.isArray(preview.warnings) && preview.warnings.length
    ? `<p class="data-safety-note">${escapeHtml(preview.warnings.join("；"))}</p>`
    : "";
  return `
    <div class="data-summary">
      ${renderDataSummary(preview.summary)}
    </div>
    <p class="data-safety-note">图片文件不会被复制、移动或删除；缩略图缓存不是核心数据，恢复后会按需重新生成。</p>
    ${warnings}
  `;
}

function renderBackupRows() {
  const backups = state.dataSafety.backups || [];
  if (!backups.length) {
    return `<div class="empty-state">暂无备份</div>`;
  }

  return backups
    .map((backup) => {
      const path = backup.path || "";
      const selected = path && path === state.dataSafety.selectedBackupPath ? "is-selected" : "";
      const summary = backup.summary
        ? `实例 ${backup.summary.instance_count || 0} · 标签 ${backup.summary.tag_count || 0} · 节点 ${backup.summary.node_count || 0} · 历史 ${backup.summary.generation_history_count || 0}`
        : "摘要不可用";
      return `
        <button
          type="button"
          class="backup-row ${selected}"
          data-action="select-backup"
          data-backup-path="${escapeHtml(path)}"
        >
          <span>${escapeHtml(formatDate(backup.created_at || ""))}</span>
          <span>${escapeHtml(backup.app_version || "")}</span>
          <span>${escapeHtml(backupTypeLabel(backup.backup_type))}</span>
          <span>${escapeHtml(backup.size_label || "")}</span>
          <span class="backup-file-name" title="${escapeHtml(`${backup.file_name || path} · ${summary}`)}">${escapeHtml(backup.file_name || path)}</span>
        </button>
      `;
    })
    .join("");
}

function renderDataSafetyPage() {
  document.body.classList.remove("has-lightbox");
  const restoreDisabled = state.dataSafety.restoring
    || !state.dataSafety.selectedBackupPath
    || !state.dataSafety.restorePreview
    || hasRunningGenerationTasks();
  const busy = state.dataSafety.loading
    || state.dataSafety.backingUp
    || state.dataSafety.exporting
    || state.dataSafety.restoring
    || state.dataSafety.clearingThumbnails;
  const thumbnailCache = state.dataSafety.thumbnailCache || {};
  const status = state.dataSafety.error || state.dataSafety.status || (state.dataSafety.loading ? "加载中" : "");
  const statusType = state.dataSafety.error ? "is-error" : state.dataSafety.loading ? "is-loading" : "";

  app.innerHTML = `
    <section class="panel data-safety-panel">
      <div class="panel-header data-safety-top-row">
        <h1>数据安全</h1>
        <div class="data-safety-actions">
          <button type="button" class="primary" data-action="create-backup" ${busy ? "disabled" : ""}>立即备份</button>
          <button type="button" data-action="refresh-backups" ${state.dataSafety.loading ? "disabled" : ""}>刷新列表</button>
          <button type="button" data-action="open-backup-folder">打开备份文件夹</button>
        </div>
      </div>
      <div class="message ${statusType}" data-message>${escapeHtml(status)}</div>
      <div class="data-safety-grid">
        <section class="data-safety-card data-safety-list-card">
          <div class="data-safety-card-title">
            <h2>备份列表</h2>
            <span>恢复前会自动备份当前数据；备份、导出、恢复都不删除电脑上的图片文件。</span>
          </div>
          <div class="backup-list">
            <div class="backup-row backup-row-head" aria-hidden="true">
              <span>备份时间</span>
              <span>版本</span>
              <span>类型</span>
              <span>大小</span>
              <span>文件名</span>
            </div>
            ${renderBackupRows()}
          </div>
        </section>
        <section class="data-safety-card">
          <div class="data-safety-card-title">
            <h2>数据导出</h2>
            <span>导出当前实例、标签、节点、设置、Provider、历史记录；数据包不包含图片文件。</span>
          </div>
          <button type="button" data-action="export-data" ${busy ? "disabled" : ""}>导出数据</button>
          ${state.dataSafety.exportTask?.summary ? `<div class="data-summary">${renderDataSummary(state.dataSafety.exportTask.summary)}</div>` : ""}
        </section>
        <section class="data-safety-card">
          <div class="data-safety-card-title">
            <h2>缩略图缓存</h2>
            <span>缩略图缓存只用于加快列表小图显示；清理缓存不会删除原图，也不会修改数据库。</span>
          </div>
          <div class="thumbnail-cache-meta">
            <span>文件：${escapeHtml(thumbnailCache.file_count || 0)}</span>
            <span>占用：${escapeHtml(thumbnailCache.size_label || "0 B")}</span>
            <span title="${escapeHtml(thumbnailCache.path || "")}">目录：${escapeHtml(thumbnailCache.path || "未创建")}</span>
          </div>
          <button type="button" data-action="clear-thumbnail-cache" ${busy ? "disabled" : ""}>清理缩略图缓存</button>
        </section>
        <section class="data-safety-card">
          <div class="data-safety-card-title">
            <h2>恢复备份</h2>
            <span>支持 zip 整库恢复、V0.39 数据包恢复，也支持旧 JSON 恢复；恢复前会自动备份当前数据库。</span>
          </div>
          <div class="path-row">
            <input readonly value="${escapeHtml(state.dataSafety.selectedBackupPath)}" placeholder="从列表选择备份，或点击选择恢复文件">
            <button type="button" data-action="choose-backup-file" ${busy ? "disabled" : ""}>选择恢复文件</button>
          </div>
          ${renderRestorePreview()}
          <button type="button" class="danger" data-action="restore-selected-backup" ${restoreDisabled ? "disabled" : ""}>恢复当前文件</button>
          ${
            hasRunningGenerationTasks()
              ? `<p class="data-safety-note">当前有生成任务正在进行，暂不能恢复备份。</p>`
              : ""
          }
        </section>
      </div>
    </section>
  `;
}


Object.assign(globalThis, {
  backupTypeLabel,
  hasRunningGenerationTasks,
  renderDataSummary,
  renderRestorePreview,
  renderBackupRows,
  renderDataSafetyPage,
});
