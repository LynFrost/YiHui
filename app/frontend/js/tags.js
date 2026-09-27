function tagTarget(scope, instanceId = "") {
  if (scope === "operation") {
    syncOperationFromDom();
    return state.operation;
  }
  return syncInstanceDraftFromDom(instanceId) || instanceById(instanceId);
}

function openTagSelector(scope, instanceId = "") {
  const target = tagTarget(scope, instanceId);
  if (!target) {
    return;
  }
  state.operation.tag_selector_open = scope === "operation";
  for (const draft of state.editing.values()) {
    draft.tag_selector_open = scope === "instance" && String(draft.id) === String(instanceId);
  }
  target.tag_selector_open = true;
  renderManager();
  focusTagSelectorInput(scope, instanceId);
}

function closeTagSelectors() {
  state.operation.tag_selector_open = false;
  for (const draft of state.editing.values()) {
    draft.tag_selector_open = false;
  }
  for (const item of state.instances || []) {
    item.tag_selector_open = false;
  }
}

function focusTagSelectorInput(scope, instanceId = "") {
  window.setTimeout(() => {
    const selector = scope === "operation"
      ? '.tag-selector input[name="tag_draft"]'
      : `[data-instance-card][data-id="${CSS.escape(String(instanceId))}"] .tag-selector input[name="instance_tag_draft"]`;
    const input = document.querySelector(selector);
    input?.focus();
    const end = input?.value?.length || 0;
    input?.setSelectionRange?.(end, end);
  }, 0);
}

function updateTagDraft(scope, instanceId, value) {
  const target = tagTarget(scope, instanceId);
  if (!target) {
    return;
  }
  target.tag_draft = value || "";
  target.tag_selector_open = true;
  renderManager();
  focusTagSelectorInput(scope, instanceId);
}

function selectTagChoice(scope, tag, instanceId = "") {
  const target = tagTarget(scope, instanceId);
  if (!target) {
    return;
  }
  const nextTag = String(tag || "").trim();
  if (scope === "instance") {
    addInstanceTagImmediate(instanceId, nextTag, { keepOpen: true });
    return;
  }
  if (nextTag && !target.tags.includes(nextTag)) {
    target.tags.push(nextTag);
  }
  target.tag_draft = "";
  target.tag_selector_open = true;
  if (scope === "operation") {
    persistUiState();
  }
  renderManager();
  focusTagSelectorInput(scope, instanceId);
}

function addTagFromDraft(scope, instanceId = "") {
  const target = tagTarget(scope, instanceId);
  if (!target) {
    return;
  }
  const draft = String(target.tag_draft || "").trim();
  const exact = (state.tagOptions || []).find(
    (tag) => tag.toLowerCase() === draft.toLowerCase(),
  );
  selectTagChoice(scope, exact || draft, instanceId);
}

function removeTagChip(scope, index, instanceId = "") {
  const target = tagTarget(scope, instanceId);
  if (!target) {
    return;
  }
  if (scope === "instance") {
    removeInstanceTagImmediate(instanceId, target.tags?.[index] || "", { keepOpen: true });
    return;
  }
  target.tags.splice(index, 1);
  target.tag_selector_open = true;
  if (scope === "operation") {
    persistUiState();
  }
  renderManager();
  focusTagSelectorInput(scope, instanceId);
}

function clearTagSelector(scope, instanceId = "") {
  const target = tagTarget(scope, instanceId);
  if (!target) {
    return;
  }
  if (scope === "instance") {
    target.tags = [];
    target.tag_draft = "";
    target.tag_selector_open = false;
    clearInstanceTagsImmediate(instanceId);
    return;
  }
  target.tags = [];
  target.tag_draft = "";
  target.tag_selector_open = false;
  if (scope === "operation") {
    persistUiState();
  }
  renderManager();
}

function addOperationTag() {
  addTagFromDraft("operation");
}

function removeOperationTag(index) {
  removeTagChip("operation", index);
}


Object.assign(globalThis, {
  tagTarget,
  openTagSelector,
  closeTagSelectors,
  focusTagSelectorInput,
  updateTagDraft,
  selectTagChoice,
  addTagFromDraft,
  removeTagChip,
  clearTagSelector,
  addOperationTag,
  removeOperationTag,
});
