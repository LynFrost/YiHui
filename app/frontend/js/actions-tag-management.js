async function loadTagManagementTags() {
  state.tagManagement.loading = true;
  state.tagManagement.error = "";
  renderTagManagementIfActive();

  const params = new URLSearchParams();
  params.set("q", state.tagManagement.q || "");

  try {
    const data = await api(`/api/tag-management?${params.toString()}`);
    state.tagManagement.items = Array.isArray(data.items) ? data.items : [];
    state.tagManagement.total = Number.isFinite(data.total) ? data.total : state.tagManagement.items.length;
    state.tagManagement.loading = false;
    state.tagManagement.error = "";
  } catch (error) {
    state.tagManagement.loading = false;
    state.tagManagement.error = error.message;
    throw error;
  } finally {
    renderTagManagementIfActive();
  }
}

function closeTagManagementContextMenu() {
  state.tagManagementContextMenu = {
    open: false,
    tag_id: null,
    tag_name: "",
    x: 0,
    y: 0,
  };
}

function openTagManagementContextMenu(tagId, tagName, x, y) {
  state.tagManagementContextMenu = {
    open: true,
    tag_id: Number.parseInt(tagId, 10),
    tag_name: String(tagName || ""),
    x: Math.max(0, Math.round(x || 0)),
    y: Math.max(0, Math.round(y || 0)),
  };
  renderTagManagementIfActive();
}

function tagManagementNamesForIds(ids) {
  const selected = new Set((ids || []).map((id) => String(id)));
  return (state.tagManagement.items || [])
    .filter((item) => selected.has(String(item.id)))
    .map((item) => item.name)
    .filter(Boolean);
}

function replaceTagFilters(oldNames, nextName) {
  const oldSet = new Set((oldNames || []).filter(Boolean));
  if (!oldSet.size || !Array.isArray(state.filters.tags)) {
    return false;
  }
  let changed = false;
  const next = [];
  for (const tag of state.filters.tags) {
    if (oldSet.has(tag)) {
      changed = true;
      if (nextName && !next.includes(nextName)) {
        next.push(nextName);
      }
      continue;
    }
    if (!next.includes(tag)) {
      next.push(tag);
    }
  }
  if (changed) {
    state.filters.tags = next;
    state.filters.page = 1;
    persistUiState();
  }
  return changed;
}

async function refreshAfterTagManagement(tags) {
  if (Array.isArray(tags)) {
    state.tagOptions = tags;
  } else {
    await loadTags();
  }
  clearCurrentPageSelection();
  await loadInstances();
  await loadTagManagementTags();
  renderManagerIfActive();
}

async function renameTagFromManagement(tagId, oldName) {
  closeTagManagementContextMenu();
  const currentName = String(oldName || "").trim();
  const nextName = window.prompt("重命名 TAG", currentName);
  if (nextName === null) {
    return;
  }
  const trimmedName = String(nextName || "").trim();
  if (!trimmedName || trimmedName === currentName) {
    return;
  }
  state.tagManagement.error = "";
  state.tagManagement.status = "正在重命名 TAG";
  renderTagManagementIfActive();
  try {
    const data = await api(`/api/tag-management/${tagId}/rename`, {
      method: "PATCH",
      body: { name: trimmedName },
    });
    replaceTagFilters([currentName], data.item?.name || trimmedName);
    state.tagManagement.status = "TAG 已重命名";
    await refreshAfterTagManagement(data.tags);
  } catch (error) {
    state.tagManagement.error = error.message;
    state.tagManagement.status = "";
    renderTagManagementIfActive();
  }
}

function openMergeTagManagement(tagId) {
  closeTagManagementContextMenu();
  state.tagManagement.mergeDialog = {
    open: true,
    targetId: String(tagId || ""),
  };
  state.tagManagement.error = "";
  renderTagManagementIfActive();
}

function closeMergeTagManagement() {
  state.tagManagement.mergeDialog = {
    open: false,
    targetId: "",
  };
  renderTagManagementIfActive();
}

async function confirmMergeTagManagement(targetTagId) {
  const checked = [...document.querySelectorAll('input[name="tag_merge_source"]:checked')];
  const sourceTagIds = checked.map((input) => Number.parseInt(input.value, 10)).filter((id) => Number.isFinite(id));
  if (!sourceTagIds.length) {
    state.tagManagement.error = "请至少选择一个要合并的 TAG";
    renderTagManagementIfActive();
    return;
  }
  const target = tagManagementItemById(targetTagId);
  const confirmed = window.confirm(`确定将选中的 TAG 合并到「${target?.name || ""}」吗？此操作只修改软件数据库中的 TAG 关联，不会删除电脑上的图片文件。`);
  if (!confirmed) {
    return;
  }
  state.tagManagement.error = "";
  state.tagManagement.status = "正在合并 TAG";
  renderTagManagementIfActive();
  try {
    const sourceNames = tagManagementNamesForIds(sourceTagIds);
    const data = await api("/api/tag-management/merge", {
      method: "POST",
      body: {
        source_tag_ids: sourceTagIds,
        target_tag_id: Number.parseInt(targetTagId, 10),
      },
    });
    replaceTagFilters(sourceNames, data.target?.name || target?.name || "");
    state.tagManagement.mergeDialog = {
      open: false,
      targetId: "",
    };
    state.tagManagement.status = "TAG 已合并";
    await refreshAfterTagManagement(data.tags);
  } catch (error) {
    state.tagManagement.error = error.message;
    state.tagManagement.status = "";
    renderTagManagementIfActive();
  }
}

function applyTagManagementSearch(form) {
  closeTagManagementContextMenu();
  state.tagManagement.q = form?.elements.tag_management_q?.value || "";
  loadTagManagementTags().catch(() => {});
}

Object.assign(globalThis, {
  loadTagManagementTags,
  closeTagManagementContextMenu,
  openTagManagementContextMenu,
  tagManagementNamesForIds,
  replaceTagFilters,
  refreshAfterTagManagement,
  renameTagFromManagement,
  openMergeTagManagement,
  closeMergeTagManagement,
  confirmMergeTagManagement,
  applyTagManagementSearch,
});
