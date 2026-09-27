function normalizeNodeFilterPath(path = state.nodeFilter?.path) {
  const entries = Array.isArray(path) ? path : [];
  const normalized = entries
    .map((entry) => ({
      selection: ["all", "unassigned", "node"].includes(entry?.selection) ? entry.selection : "all",
      node_id: entry?.node_id ? normalizePositiveInteger(entry.node_id, 0) : null,
    }))
    .filter((entry, index) => index === 0 || entry.selection === "node" || entry.selection === "all" || entry.selection === "unassigned");
  return normalized.length ? normalized : [{ selection: "all", node_id: null }];
}

function findNode(nodeId, nodes = state.nodes) {
  const target = Number.parseInt(nodeId, 10);
  if (!target) {
    return null;
  }
  for (const node of nodes || []) {
    if (Number(node.id) === target) {
      return node;
    }
    const child = findNode(target, node.children || []);
    if (child) {
      return child;
    }
  }
  return null;
}

function childrenForParent(parentId) {
  if (!parentId) {
    return state.nodes || [];
  }
  return findNode(parentId)?.children || [];
}

function deepestSelectedNodeId(path = state.nodeFilter?.path) {
  const entries = normalizeNodeFilterPath(path);
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (entries[index].selection === "node" && entries[index].node_id) {
      return entries[index].node_id;
    }
  }
  return null;
}

function currentNodeQuery() {
  const path = normalizeNodeFilterPath();
  const current = path[path.length - 1] || { selection: "all", node_id: null };
  return {
    node_filter_type: current.selection || "all",
    node_id: current.node_id || "",
  };
}

async function loadNodes() {
  const data = await api("/api/nodes");
  state.nodes = Array.isArray(data.items) ? data.items : [];
  const filtered = normalizeNodeFilterPath(state.nodeFilter.path)
    .filter((entry, index) => {
      if (index === 0 && entry.node_id == null) {
        return true;
      }
      return !entry.node_id || findNode(entry.node_id);
    });
  state.nodeFilter.path = filtered.length ? filtered : [{ selection: "all", node_id: null }];
}

function truncateNodeLabel(name, limit = 8) {
  const text = String(name || "");
  return text.length > limit ? text.slice(0, limit) : text;
}

function nodeSelectionLabel(entry) {
  if (entry?.selection === "unassigned") {
    return "其他";
  }
  if (entry?.selection === "node" && entry.node_id) {
    return findNode(entry.node_id)?.name || "节点已不存在";
  }
  return "全部";
}

function nodeSelectionTitle(entry) {
  return nodeSelectionLabel(entry);
}

function validateNodeNameLocally(name, parentId, currentNodeId = null) {
  const normalizedName = String(name || "").trim();
  if (!normalizedName) {
    return "节点名称不能为空";
  }
  if (["全部", "其他", "新建"].includes(normalizedName)) {
    return "节点名称是保留名称";
  }
  const siblingNames = childrenForParent(parentId)
    .filter((node) => Number(node.id) !== Number(currentNodeId || 0))
    .map((node) => String(node.name || "").trim());
  if (siblingNames.includes(normalizedName)) {
    return "节点名称已存在";
  }
  return "";
}

async function createNode(parentId, name) {
  const data = await api("/api/nodes", {
    method: "POST",
    body: { parent_id: parentId || null, name },
  });
  state.nodes = Array.isArray(data.items) ? data.items : [];
  return data.item;
}

function nodeMenuKey(scope, level) {
  return `${scope || "filter"}:${Number.parseInt(level, 10) || 0}`;
}

function closeNodeMenus() {
  state.nodeMenu = { openKey: "" };
  state.nodeContextMenu = { open: false, node_id: null, x: 0, y: 0 };
}

function renderNodeMenuOptions({
  parentId,
  current,
  level,
  levelAttr = "data-node-level",
  parentAttr = "data-parent-id",
  optionAction = "select-node-option",
  enableContextMenu = true,
} = {}) {
  const children = childrenForParent(parentId);
  const commonAttrs = `${levelAttr}="${escapeHtml(level)}" ${parentAttr}="${escapeHtml(parentId || "")}"`;
  const selectedClass = (kind, nodeId = null) => {
    if (kind === "node") {
      return current?.selection === "node" && Number(current?.node_id) === Number(nodeId) ? " is-selected" : "";
    }
    return current?.selection === kind ? " is-selected" : "";
  };
  const fixedOptions = `
    <button
      type="button"
      class="node-menu-option is-create"
      data-action="${escapeHtml(optionAction)}"
      data-node-option-kind="new"
      data-node-value="new"
      ${commonAttrs}
    >新建</button>
    <button
      type="button"
      class="node-menu-option${selectedClass("all")}"
      data-action="${escapeHtml(optionAction)}"
      data-node-option-kind="all"
      data-node-value="all"
      ${commonAttrs}
    >全部</button>
    <button
      type="button"
      class="node-menu-option${selectedClass("unassigned")}"
      data-action="${escapeHtml(optionAction)}"
      data-node-option-kind="unassigned"
      data-node-value="unassigned"
      ${commonAttrs}
    >其他</button>
  `;
  const nodeOptions = children.map((node) => `
    <button
      type="button"
      class="node-menu-option is-draggable${selectedClass("node", node.id)}"
      draggable="true"
      data-action="${escapeHtml(optionAction)}"
      data-node-option-kind="node"
      data-node-value="node:${escapeHtml(node.id)}"
      data-node-drag-id="${escapeHtml(node.id)}"
      data-node-drag-parent-id="${escapeHtml(parentId || "")}"
      ${enableContextMenu ? `data-node-context-id="${escapeHtml(node.id)}"` : ""}
      ${commonAttrs}
      title="${escapeHtml(node.name)}"
    ><span class="node-menu-drag-handle" aria-hidden="true">⋮</span>${escapeHtml(node.name)}</button>
  `).join("");
  return `${fixedOptions}${nodeOptions}`;
}

function renderNodePathSelectors({
  path = [{ selection: "all", node_id: null }],
  action = "select-node-option",
  toggleAction = "toggle-node-menu",
  optionAction = "select-node-option",
  levelAttr = "data-node-level",
  parentAttr = "data-parent-id",
  selectClass = "node-select",
  scope = "filter",
  openMenuKey = state.nodeMenu?.openKey || "",
  enableContextMenu = true,
} = {}) {
  const normalizedPath = normalizeNodeFilterPath(path);
  const selects = [];
  let parentId = null;
  normalizedPath.forEach((entry, index) => {
    const selectTitle = nodeSelectionTitle(entry);
    const displayLabel = truncateNodeLabel(selectTitle);
    const menuKey = nodeMenuKey(scope, index);
    const isOpen = openMenuKey === menuKey;
    selects.push(`
      <span class="node-select-wrap ${isOpen ? "is-open" : ""}" title="${escapeHtml(selectTitle)}">
        <button
          type="button"
          class="${escapeHtml(selectClass)}"
          data-action="${escapeHtml(toggleAction)}"
          data-node-menu-key="${escapeHtml(menuKey)}"
          ${levelAttr}="${escapeHtml(index)}"
          ${parentAttr}="${escapeHtml(parentId || "")}"
          title="${escapeHtml(selectTitle)}"
          data-node-display="${escapeHtml(displayLabel)}"
        ><span class="node-select-display">${escapeHtml(displayLabel)}</span></button>
        ${
          isOpen
            ? `<div class="node-menu" data-node-menu="${escapeHtml(menuKey)}">
                ${renderNodeMenuOptions({
                  parentId,
                  current: entry,
                  level: index,
                  levelAttr,
                  parentAttr,
                  optionAction,
                  enableContextMenu,
                })}
              </div>`
            : ""
        }
      </span>
    `);
    if (entry.selection === "node" && entry.node_id) {
      parentId = entry.node_id;
    } else {
      parentId = null;
    }
  });
  const last = normalizedPath[normalizedPath.length - 1];
  if (last?.selection === "node" && last.node_id) {
    const menuKey = nodeMenuKey(scope, normalizedPath.length);
    const isOpen = openMenuKey === menuKey;
    selects.push(`
      <span class="node-select-wrap ${isOpen ? "is-open" : ""}" title="全部">
        <button
          type="button"
          class="${escapeHtml(selectClass)}"
          data-action="${escapeHtml(toggleAction)}"
          data-node-menu-key="${escapeHtml(menuKey)}"
          ${levelAttr}="${escapeHtml(normalizedPath.length)}"
          ${parentAttr}="${escapeHtml(last.node_id)}"
          title="全部"
          data-node-display="全部"
        ><span class="node-select-display">全部</span></button>
        ${
          isOpen
            ? `<div class="node-menu" data-node-menu="${escapeHtml(menuKey)}">
                ${renderNodeMenuOptions({
                  parentId: last.node_id,
                  current: { selection: "all", node_id: last.node_id },
                  level: normalizedPath.length,
                  levelAttr,
                  parentAttr,
                  optionAction,
                  enableContextMenu,
                })}
              </div>`
            : ""
        }
      </span>
    `);
  }
  return selects.join("");
}

function renderNodeContextMenu() {
  const menu = state.nodeContextMenu || {};
  if (!menu.open || !menu.node_id) {
    return "";
  }
  const node = findNode(menu.node_id);
  if (!node) {
    return "";
  }
  return `
    <div
      class="node-context-menu"
      data-node-context-menu="true"
      data-skip-batch-save="true"
      style="left:${escapeHtml(menu.x || 0)}px; top:${escapeHtml(menu.y || 0)}px"
    >
      <button type="button" data-action="rename-node-from-menu" data-node-id="${escapeHtml(menu.node_id)}">重命名</button>
      <button type="button" class="danger" data-action="delete-node-from-menu" data-node-id="${escapeHtml(menu.node_id)}">删除</button>
    </div>
  `;
}

function renderNodeControls() {
  return `
    <div class="node-controls" data-node-controls data-skip-batch-save="true">
      ${renderNodePathSelectors({ path: state.nodeFilter?.path })}
      ${renderNodeContextMenu()}
    </div>
  `;
}

function openNodeNameDialog({
  parentId = null,
  title = "新建节点",
  initialValue = "",
  validate = null,
  onSubmit = null,
} = {}) {
  return new Promise((resolve) => {
    document.querySelector("[data-node-name-dialog]")?.remove();
    const dialog = document.createElement("div");
    dialog.className = "modal-backdrop";
    dialog.dataset.nodeNameDialog = "true";
    dialog.dataset.skipBatchSave = "true";
    dialog.innerHTML = `
      <div class="modal move-dialog" role="dialog" aria-modal="true">
        <div class="modal-title-row">
          <h2>${escapeHtml(title)}</h2>
        </div>
        <label class="field">
          <span>节点名称</span>
          <input data-node-name-input placeholder="输入节点名称" value="${escapeHtml(initialValue)}">
        </label>
        <div class="field-error" data-node-name-error hidden></div>
        <div class="actions">
          <button type="button" class="primary" data-node-name-confirm>确认</button>
          <button type="button" data-node-name-cancel>取消</button>
        </div>
      </div>
    `;
    document.body.appendChild(dialog);
    const input = dialog.querySelector("[data-node-name-input]");
    const errorBox = dialog.querySelector("[data-node-name-error]");
    const confirmButton = dialog.querySelector("[data-node-name-confirm]");
    const cancelButton = dialog.querySelector("[data-node-name-cancel]");
    const setError = (message = "") => {
      if (!errorBox) {
        return;
      }
      errorBox.textContent = message;
      errorBox.hidden = !message;
    };
    const setPending = (pending) => {
      if (confirmButton) {
        confirmButton.disabled = pending;
      }
      if (cancelButton) {
        cancelButton.disabled = pending;
      }
      if (input) {
        input.disabled = pending;
      }
    };
    const close = (value) => {
      dialog.remove();
      resolve(value);
    };
    const submit = async () => {
      const name = String(input?.value || "");
      const localError = typeof validate === "function" ? validate(name) : "";
      if (localError) {
        setError(localError);
        input?.focus();
        input?.select();
        return;
      }
      if (typeof onSubmit !== "function") {
        close({ parentId, name });
        return;
      }
      try {
        setPending(true);
        const result = await onSubmit(String(name || "").trim());
        close(result);
      } catch (error) {
        setPending(false);
        setError(error.message || "节点操作失败");
        input?.focus();
        input?.select();
      }
    };
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog || event.target.closest("[data-node-name-cancel]")) {
        close(undefined);
        return;
      }
      if (event.target.closest("[data-node-name-confirm]")) {
        submit();
      }
    });
    input?.addEventListener("input", () => setError(""));
    input?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        submit();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        close(undefined);
      }
    });
    input?.focus();
    input?.select();
  });
}

async function createNodeFromDialog(parentId) {
  return openNodeNameDialog({
    parentId,
    title: "新建节点",
    validate: (name) => validateNodeNameLocally(name, parentId),
    onSubmit: (name) => runUndoableAction("新建节点", async () => createNode(parentId, name)),
  });
}

async function renameNodeById(nodeId) {
  if (!nodeId) {
    return;
  }
  const currentNode = findNode(nodeId);
  if (!currentNode) {
    return;
  }
  const parentId = currentNode?.parent_id ?? null;
  const data = await openNodeNameDialog({
    parentId,
    title: "重命名节点",
    initialValue: currentNode?.name || "",
    validate: (name) => validateNodeNameLocally(name, parentId, nodeId),
    onSubmit: (name) => runUndoableAction("重命名节点", async () => (
      api(`/api/nodes/${encodeURIComponent(nodeId)}`, {
        method: "PATCH",
        body: { name },
      })
    )),
  });
  if (!data) {
    renderManagerIfActive();
    return;
  }
  state.nodes = Array.isArray(data.items) ? data.items : state.nodes;
  persistUiState();
  await refreshInstances("已重命名节点", "success");
}

async function renameCurrentNode() {
  return renameNodeById(deepestSelectedNodeId(state.nodeFilter?.path));
}

function pathAfterDeletingNode(nodeId) {
  const currentPath = normalizeNodeFilterPath(state.nodeFilter?.path);
  const deletedIndex = currentPath.findIndex((entry) => (
    entry.selection === "node" && Number(entry.node_id) === Number(nodeId)
  ));
  if (deletedIndex < 0) {
    return currentPath;
  }
  const parentPath = currentPath.slice(0, deletedIndex);
  return parentPath.length ? normalizeNodeFilterPath(parentPath) : [{ selection: "all", node_id: null }];
}

async function deleteNodeById(nodeId) {
  if (!nodeId) {
    return;
  }
  const currentNode = findNode(nodeId);
  if (!currentNode) {
    return;
  }
  const confirmed = window.confirm(`确认删除节点“${currentNode.name}”？\n不会删除任何实例记录或电脑上的图片文件。`);
  if (!confirmed) {
    return;
  }
  const nextPath = pathAfterDeletingNode(nodeId);
  await runUndoableAction("删除节点", async () => (
    api(`/api/nodes/${encodeURIComponent(nodeId)}`, { method: "DELETE" })
  ));
  state.nodeFilter.path = nextPath;
  state.filters.page = 1;
  clearCurrentPageSelection();
  persistUiState();
  await loadNodes();
  await refreshInstances("已删除节点", "success");
}

async function deleteCurrentNode() {
  return deleteNodeById(deepestSelectedNodeId(state.nodeFilter?.path));
}

async function changeNodeFilter(level, value, parentId = "") {
  const nextPath = normalizeNodeFilterPath().slice(0, Number.parseInt(level, 10) || 0);
  const parentNodeId = parentId ? Number.parseInt(parentId, 10) : null;
  closeNodeMenus();
  if (value === "new") {
    const item = await createNodeFromDialog(parentNodeId);
    if (!item?.id) {
      renderManagerIfActive();
      return;
    }
    nextPath.push({ selection: "node", node_id: item.id });
  } else if (String(value).startsWith("node:")) {
    nextPath.push({ selection: "node", node_id: Number.parseInt(String(value).slice(5), 10) });
  } else {
    nextPath.push({ selection: value === "unassigned" ? "unassigned" : "all", node_id: parentNodeId });
  }
  state.nodeFilter.path = normalizeNodeFilterPath(nextPath);
  state.filters.page = 1;
  clearCurrentPageSelection();
  persistUiState();
  await refreshInstances();
}

function toggleNodeMenu(menuKey) {
  state.nodeContextMenu = { open: false, node_id: null, x: 0, y: 0 };
  state.nodeMenu = {
    openKey: state.nodeMenu?.openKey === menuKey ? "" : menuKey,
  };
  renderManagerIfActive();
}

function openNodeContextMenu(nodeId, x, y) {
  const node = findNode(nodeId);
  if (!node) {
    return;
  }
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1024;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 768;
  const menuWidth = 120;
  const menuHeight = 82;
  state.nodeContextMenu = {
    open: true,
    node_id: Number.parseInt(nodeId, 10),
    x: Math.max(8, Math.min(x, viewportWidth - menuWidth - 8)),
    y: Math.max(8, Math.min(y, viewportHeight - menuHeight - 8)),
  };
  renderManagerIfActive();
}

function normalizeNodeDragParentId(value) {
  const normalized = Number.parseInt(value, 10);
  return normalized > 0 ? normalized : null;
}

function siblingIdsForParent(parentId) {
  return childrenForParent(parentId).map((node) => Number(node.id)).filter(Boolean);
}

async function reorderSiblingNodes(parentId, draggedId, targetId) {
  const normalizedParentId = normalizeNodeDragParentId(parentId);
  const normalizedDraggedId = Number.parseInt(draggedId, 10);
  const normalizedTargetId = Number.parseInt(targetId, 10);
  if (!normalizedDraggedId || !normalizedTargetId || normalizedDraggedId === normalizedTargetId) {
    return false;
  }
  const nextIds = siblingIdsForParent(normalizedParentId);
  const fromIndex = nextIds.indexOf(normalizedDraggedId);
  const toIndex = nextIds.indexOf(normalizedTargetId);
  if (fromIndex < 0 || toIndex < 0) {
    return false;
  }
  nextIds.splice(fromIndex, 1);
  nextIds.splice(toIndex, 0, normalizedDraggedId);
  const data = await api("/api/nodes/reorder", {
    method: "POST",
    body: { parent_id: normalizedParentId, node_ids: nextIds },
  });
  state.nodes = Array.isArray(data.items) ? data.items : [];
  state.nodeFilter.path = normalizeNodeFilterPath(state.nodeFilter.path);
  persistUiState();
  renderManagerIfActive();
  return true;
}

function clearNodeDragClasses() {
  document.querySelectorAll(".node-menu-option.is-dragging, .node-menu-option.is-drop-target").forEach((node) => {
    node.classList.remove("is-dragging", "is-drop-target");
  });
}

function handleNodeDragStart(event) {
  const option = event.target.closest?.("[data-node-drag-id]");
  if (!option || !app.contains(option) || event.button !== 0) {
    return false;
  }
  const nodeId = Number.parseInt(option.dataset.nodeDragId || "", 10);
  if (!nodeId || option.dataset.nodeOptionKind !== "node") {
    return false;
  }
  const parentId = normalizeNodeDragParentId(option.dataset.nodeDragParentId || "");
  state.nodeDrag = {
    active: true,
    node_id: nodeId,
    parent_id: parentId,
    suppressClick: true,
  };
  option.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", String(nodeId));
  return true;
}

function handleNodeDragOver(event) {
  const option = event.target.closest?.("[data-node-drag-id]");
  if (!state.nodeDrag?.active || !option || !app.contains(option)) {
    return false;
  }
  const targetParentId = normalizeNodeDragParentId(option.dataset.nodeDragParentId || "");
  if (targetParentId !== state.nodeDrag.parent_id) {
    return false;
  }
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  clearNodeDragClasses();
  option.classList.add("is-drop-target");
  return true;
}

function handleNodeDrop(event) {
  const option = event.target.closest?.("[data-node-drag-id]");
  if (!state.nodeDrag?.active || !option || !app.contains(option)) {
    return false;
  }
  const targetParentId = normalizeNodeDragParentId(option.dataset.nodeDragParentId || "");
  if (targetParentId !== state.nodeDrag.parent_id) {
    return false;
  }
  event.preventDefault();
  event.stopPropagation();
  const draggedId = state.nodeDrag.node_id;
  const targetId = Number.parseInt(option.dataset.nodeDragId || "", 10);
  reorderSiblingNodes(targetParentId, draggedId, targetId).catch(async (error) => {
    setMessage(error.message, "error");
    await loadNodes();
    renderManagerIfActive();
  }).finally(() => {
    handleNodeDragEnd();
  });
  return true;
}

function handleNodeDragEnd() {
  clearNodeDragClasses();
  state.nodeDrag = {
    active: false,
    node_id: null,
    parent_id: null,
    suppressClick: Boolean(state.nodeDrag?.suppressClick),
  };
  window.setTimeout(() => {
    if (state.nodeDrag) {
      state.nodeDrag.suppressClick = false;
    }
  }, 0);
  return true;
}

function normalizeMoveNodePath(path) {
  const normalized = normalizeNodeFilterPath(path);
  return normalized.length ? normalized : [{ selection: "all", node_id: null }];
}

function chooseMoveNode(title = "移动到节点") {
  return new Promise((resolve) => {
    document.querySelector("[data-move-dialog]")?.remove();
    let movePath = normalizeMoveNodePath([{ selection: "all", node_id: null }]);
    let moveOpenKey = "";
    const dialog = document.createElement("div");
    dialog.className = "modal-backdrop";
    dialog.dataset.moveDialog = "true";
    dialog.dataset.skipBatchSave = "true";

    const renderDialog = () => {
      dialog.innerHTML = `
        <div class="modal move-dialog" role="dialog" aria-modal="true">
          <div class="modal-title-row">
            <h2>${escapeHtml(title)}</h2>
          </div>
          <div class="node-path-dialog">
            <span>目标节点</span>
            ${renderNodePathSelectors({
              path: movePath,
              toggleAction: "toggle-move-node-menu",
              optionAction: "select-move-node-option",
              levelAttr: "data-move-node-level",
              parentAttr: "data-move-parent-id",
              selectClass: "node-select",
              scope: "move",
              openMenuKey: moveOpenKey,
              enableContextMenu: false,
            })}
          </div>
          <div class="actions">
            <button type="button" class="primary" data-move-confirm>确认</button>
            <button type="button" data-move-cancel>取消</button>
          </div>
        </div>
      `;
    };

    renderDialog();
    document.body.appendChild(dialog);

    const close = (value) => {
      dialog.remove();
      resolve(value);
    };

    dialog.addEventListener("click", async (event) => {
      const toggle = event.target.closest("[data-action='toggle-move-node-menu']");
      if (toggle) {
        const key = toggle.dataset.nodeMenuKey || "";
        moveOpenKey = moveOpenKey === key ? "" : key;
        renderDialog();
        return;
      }
      const option = event.target.closest("[data-action='select-move-node-option']");
      if (option) {
        const level = Number.parseInt(option.dataset.moveNodeLevel || "0", 10) || 0;
        const parentNodeId = option.dataset.moveParentId ? Number.parseInt(option.dataset.moveParentId, 10) : null;
        const nextPath = normalizeMoveNodePath(movePath).slice(0, level);
        const value = option.dataset.nodeValue || "all";
        moveOpenKey = "";
        if (value === "new") {
          const item = await createNodeFromDialog(parentNodeId);
          if (!item?.id) {
            renderDialog();
            return;
          }
          movePath = normalizeMoveNodePath([...nextPath, { selection: "node", node_id: item.id }]);
        } else if (String(value).startsWith("node:")) {
          movePath = normalizeMoveNodePath([...nextPath, { selection: "node", node_id: Number.parseInt(String(value).slice(5), 10) }]);
        } else {
          movePath = normalizeMoveNodePath([...nextPath, { selection: value === "unassigned" ? "unassigned" : "all", node_id: parentNodeId }]);
        }
        renderDialog();
        return;
      }
      if (event.target === dialog || event.target.closest("[data-move-cancel]")) {
        close(undefined);
        return;
      }
      if (event.target.closest("[data-move-confirm]")) {
        const nodeId = deepestSelectedNodeId(movePath);
        close(nodeId ?? null);
      }
    });
  });
}

Object.assign(globalThis, {
  normalizeNodeFilterPath,
  findNode,
  childrenForParent,
  deepestSelectedNodeId,
  currentNodeQuery,
  loadNodes,
  createNode,
  nodeSelectionLabel,
  nodeSelectionTitle,
  renderNodeMenuOptions,
  renderNodePathSelectors,
  renderNodeControls,
  renderNodeContextMenu,
  openNodeNameDialog,
  createNodeFromDialog,
  renameNodeById,
  renameCurrentNode,
  deleteNodeById,
  deleteCurrentNode,
  changeNodeFilter,
  toggleNodeMenu,
  closeNodeMenus,
  openNodeContextMenu,
  reorderSiblingNodes,
  handleNodeDragStart,
  handleNodeDragOver,
  handleNodeDrop,
  handleNodeDragEnd,
  chooseMoveNode,
  truncateNodeLabel,
  validateNodeNameLocally,
});
