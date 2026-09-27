function tagManagementItemById(tagId) {
  return (state.tagManagement.items || []).find((item) => String(item.id) === String(tagId)) || null;
}

function renderTagManagementRows() {
  const items = state.tagManagement.items || [];
  if (state.tagManagement.loading) {
    return `<div class="empty-state">加载中</div>`;
  }
  if (!items.length) {
    return `<div class="empty-state">暂无正在使用的 TAG</div>`;
  }

  const cards = items.map((item) => `
    <div class="tag-management-card" data-tag-management-row data-tag-management-context-id="${escapeHtml(item.id)}" data-tag-id="${escapeHtml(item.id)}" data-tag-name="${escapeHtml(item.name)}">
      <div class="tag-management-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
      <div class="tag-management-count">${escapeHtml(item.usage_count || 0)} 个实例</div>
    </div>
  `).join("");

  return `
    <div class="tag-management-card-grid">
      ${cards}
    </div>
  `;
}

function renderTagManagementContextMenu() {
  const menu = state.tagManagementContextMenu || {};
  if (!menu.open || !menu.tag_id) {
    return "";
  }
  return `
    <div class="tag-management-context-menu" style="left:${escapeHtml(menu.x || 0)}px; top:${escapeHtml(menu.y || 0)}px;" data-tag-management-context-menu>
      <button type="button" data-action="rename-tag-management" data-tag-id="${escapeHtml(menu.tag_id)}" data-tag-name="${escapeHtml(menu.tag_name || "")}">重命名</button>
      <button type="button" data-action="open-merge-tag-management" data-tag-id="${escapeHtml(menu.tag_id)}" data-tag-name="${escapeHtml(menu.tag_name || "")}">合并</button>
    </div>
  `;
}

function renderTagMergeDialog() {
  const dialog = state.tagManagement.mergeDialog || {};
  if (!dialog.open) {
    return "";
  }
  const target = tagManagementItemById(dialog.targetId);
  const sourceOptions = (state.tagManagement.items || [])
    .filter((item) => String(item.id) !== String(dialog.targetId));
  const optionsHtml = sourceOptions.length
    ? sourceOptions.map((item) => `
      <label class="tag-merge-option" title="${escapeHtml(item.name)}">
        <input type='checkbox' name="tag_merge_source" value="${escapeHtml(item.id)}">
        <span>${escapeHtml(item.name)}</span>
        <small>${escapeHtml(item.usage_count || 0)} 个实例</small>
      </label>
    `).join("")
    : `<div class="empty-state">没有可合并的其他 TAG</div>`;

  return `
    <div class="modal-backdrop" data-tag-management-dialog>
      <div class="modal-card">
        <div class="modal-title-row">
          <h2>合并 TAG</h2>
          <button type="button" data-action="close-merge-tag-management">取消</button>
        </div>
        <p class="tag-management-note">
          将选中的正在使用 TAG 合并到「${escapeHtml(target?.name || "")}」。虚拟筛选项“无”和内部值 __untagged__ 不是真实 TAG，不参与管理。
        </p>
        <div class="tag-merge-list">
          ${optionsHtml}
        </div>
        <div class="modal-actions">
          <button type="button" data-action="close-merge-tag-management">取消</button>
          <button type="button" class="primary" data-action="confirm-merge-tag-management" data-target-tag-id="${escapeHtml(dialog.targetId)}">确认合并</button>
        </div>
      </div>
    </div>
  `;
}

function renderTagManagementPage() {
  document.body.classList.remove("has-lightbox");
  const status = state.tagManagement.error
    || state.tagManagement.status
    || (state.tagManagement.loading ? "加载中" : "");
  const statusType = state.tagManagement.error ? "is-error" : state.tagManagement.loading ? "is-loading" : "";

  app.innerHTML = `
    <section class="panel tag-management-panel">
      <div class="panel-header tag-management-top-row">
        <h1>标签管理</h1>
        <form class="tag-management-toolbar" data-tag-management-toolbar>
          <label class="toolbar-field tag-management-search">
            <span>搜索 TAG</span>
            <input name="tag_management_q" value="${escapeHtml(state.tagManagement.q || "")}" placeholder="搜索正在使用的 TAG">
          </label>
          <div class="toolbar-actions">
            <button type="submit" class="primary">搜索</button>
            <button type="button" data-action="refresh-tag-management" ${state.tagManagement.loading ? "disabled" : ""}>刷新</button>
          </div>
          <div class="tag-management-status">总数 ${escapeHtml(state.tagManagement.total || 0)}</div>
        </form>
      </div>
      <div class="message ${statusType}" data-message>${escapeHtml(status)}</div>
      <p class="tag-management-note">只管理正在使用的真实 TAG；不新建 TAG，不显示未使用 TAG，不把“无”或 __untagged__ 当作真实 TAG。</p>
      <div class="tag-management-list">
        ${renderTagManagementRows()}
      </div>
      ${renderTagManagementContextMenu()}
      ${renderTagMergeDialog()}
    </section>
  `;
}

function renderTagManagementIfActive() {
  if (state.page !== "tag-management") {
    return false;
  }
  renderTagManagementPage();
  return true;
}

Object.assign(globalThis, {
  tagManagementItemById,
  renderTagManagementRows,
  renderTagManagementContextMenu,
  renderTagMergeDialog,
  renderTagManagementPage,
  renderTagManagementIfActive,
});
