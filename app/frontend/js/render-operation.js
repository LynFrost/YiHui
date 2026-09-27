function render() {
  tabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.page === state.page);
  });

  if (state.page === "settings") {
    hideImageHoverPreview();
    renderSettings();
    return;
  }

  if (state.page === "history") {
    hideImageHoverPreview();
    renderHistoryPage();
    return;
  }

  if (state.page === "data-safety") {
    hideImageHoverPreview();
    renderDataSafetyPage();
    return;
  }

  if (state.page === "tag-management") {
    hideImageHoverPreview();
    renderTagManagementPage();
    return;
  }

  renderManager();
}

function renderManagerIfActive() {
  if (state.page !== "manager") {
    return false;
  }

  renderManager();
  return true;
}

function renderSettingsIfActive() {
  if (state.page !== "settings") {
    return false;
  }

  renderSettings();
  return true;
}

function renderDataSafetyIfActive() {
  if (state.page !== "data-safety") {
    return false;
  }

  renderDataSafetyPage();
  return true;
}

function isActiveOpenAIGoogleProvider() {
  return normalizeProviderAdapter(activeProvider()?.adapter) === "openai-google";
}

function renderManager() {
  normalizeOperation();
  document.body.classList.toggle("has-lightbox", Boolean(state.lightbox.path));

  app.innerHTML = `
    <section class="manager-panel">
      ${renderOperationArea()}
      ${renderSaveArea()}
    </section>
    ${renderLightbox()}
  `;
  bindSaveAreaEvents();
  scrollGenerationPathInputToEnd();
  syncRunningRefresh();
  globalThis.stabilizeSaveAreaImages?.({ forceVisible: true, reason: "render-manager" });
}

function normalizeOperation() {
  state.operation = {
    ...OPERATION_DEFAULTS,
    ...(state.operation || {}),
  };

  if (!Array.isArray(state.operation.input_image_paths)) {
    state.operation.input_image_paths = [];
  }
  state.operation.input_image_paths = [...state.operation.input_image_paths];
  if (!Array.isArray(state.operation.tags)) {
    state.operation.tags = [];
  }
  state.operation.tags = [...state.operation.tags];
  if (!state.operation.generation_path && state.settings?.default_output_dir) {
    state.operation.generation_path = state.settings.default_output_dir;
  }
  if (!state.operation.generation_clarity && state.operation.resolution) {
    state.operation.generation_clarity = state.operation.resolution;
  }
  if (!isValidGenerationResolution(state.operation.generation_clarity)) {
    state.operation.generation_clarity = defaultGenerationClarity();
  }
  state.operation.resolution = state.operation.generation_clarity;
  if (!ASPECT_RATIO_PRESETS.includes(state.operation.aspect_ratio)) {
    state.operation.aspect_ratio = defaultAspectRatio();
  }
  if (
    isPresetClarity(state.operation.generation_clarity)
    || !isValidGenerationSize(state.operation.generation_size)
  ) {
    state.operation.generation_size = isPresetClarity(state.operation.generation_clarity)
      ? sizeForAspectRatio(state.operation.aspect_ratio, state.operation.generation_clarity)
      : defaultGenerationSize();
  }
  state.operation.custom_resolution = defaultCustomResolution();
  state.operation.text_generation_count = normalizeGenerationCount(
    state.operation.text_generation_count || state.operation.generation_count,
  );
  state.operation.generation_count = normalizeGenerationCount(
    state.operation.generation_count,
  );
  state.operation.mode = state.operation.input_image_paths.length ? "image_to_image" : "text_to_image";
  state.operation.text_generation_count = state.operation.generation_count;
  if (!state.operation.custom_generation_size) {
    state.operation.custom_generation_size = state.operation.generation_size;
  }
}

function renderSlotOverlay(path) {
  return `<div class="slot-overlay" title="${escapeHtml(path)}">${escapeHtml(path)}</div>`;
}

function clipboardTargetForAction(action, instanceId = "") {
  if (action === "choose-input-images") {
    return { scope: "operation", area: "input", instanceId: "" };
  }
  if (action === "choose-instance-input-images") {
    return { scope: "instance", area: "input", instanceId: String(instanceId || "") };
  }
  if (action === "choose-instance-output-image") {
    return { scope: "instance", area: "output", instanceId: String(instanceId || "") };
  }
  return null;
}

function sameClipboardImageTarget(target) {
  const current = state.clipboardImageTarget;
  return Boolean(
    current
      && target
      && current.scope === target.scope
      && current.area === target.area
      && String(current.instanceId || "") === String(target.instanceId || ""),
  );
}

function clipboardTargetAttrs(action, instanceId = "") {
  const target = clipboardTargetForAction(action, instanceId);
  if (!target) {
    return { attrs: "", className: "" };
  }
  const activeClass = sameClipboardImageTarget(target) ? " is-clipboard-target" : "";
  return {
    attrs: ` data-clipboard-image-target="${escapeHtml(target.scope)}:${escapeHtml(target.area)}" data-clipboard-scope="${escapeHtml(target.scope)}" data-clipboard-area="${escapeHtml(target.area)}" data-clipboard-instance-id="${escapeHtml(target.instanceId || "")}"`,
    className: activeClass,
  };
}

function renderEmptyImageSlot(action, instanceId = "") {
  const clipboard = clipboardTargetAttrs(action, instanceId);
  const idAttr = instanceId === "" ? "" : ` data-id="${escapeHtml(instanceId)}"`;
  return `
    <div class="image-slot image-slot-add${clipboard.className}" role="button" tabindex="0" data-action="select-empty-image-slot"${clipboard.attrs} aria-label="选中图片位">
      <button type="button" class="image-slot-upload-button" data-action="${escapeHtml(action)}"${idAttr}${clipboard.attrs} aria-label="添加图片">+</button>
    </div>
  `;
}

function renderImageSlot(path, action, index = "") {
  const clipboard = clipboardTargetAttrs(action);
  if (!path) {
    return renderEmptyImageSlot(action);
  }

  const indexAttr = index === "" ? "" : ` data-index="${escapeHtml(index)}"`;
  const removeAction = "remove-input-image";

  return `
    <div class="image-slot image-slot-filled${clipboard.className}" role="button" tabindex="0" data-image-path="${escapeHtml(path)}" data-lazy-image-path="${escapeHtml(path)}"${clipboard.attrs} aria-label="查看原图">
      <img src="${escapeHtml(thumbnailUrl(path))}" alt="${escapeHtml(path)}" loading="lazy" decoding="async">
      <button type="button" class="slot-remove" data-action="${removeAction}"${indexAttr} aria-label="移除图片">×</button>
      ${renderSlotOverlay(path)}
    </div>
  `;
}

function renderSavedImageSlot(path, options) {
  const {
    addAction,
    removeAction,
    instanceId,
    index = "",
    editable = false,
    emptyText = "无图片",
    replaceWhenFilled = false,
    reserveOnly = false,
    pendingKey = "",
    pendingStartMs = "",
  } = options;
  const idAttr = ` data-id="${escapeHtml(instanceId)}"`;
  const indexAttr = index === "" ? "" : ` data-index="${escapeHtml(index)}"`;

  if (!path) {
    if (reserveOnly) {
      return "";
    }
    if (!editable) {
      const pendingText = pendingKey
        ? `<span data-pending-elapsed-key="${escapeHtml(pendingKey)}" data-pending-start-ms="${escapeHtml(pendingStartMs)}">${escapeHtml(emptyText)}</span>`
        : escapeHtml(emptyText);
      return `<div class="image-slot image-slot-empty">${pendingText}</div>`;
    }

    return renderEmptyImageSlot(addAction, instanceId);
  }

  const clipboard = clipboardTargetAttrs(addAction, instanceId);
  return `
    <div class="image-slot image-slot-filled${clipboard.className}" role="button" tabindex="0" data-image-path="${escapeHtml(path)}" data-lazy-image-path="${escapeHtml(path)}"${clipboard.attrs} aria-label="查看原图">
      <img src="${escapeHtml(thumbnailUrl(path))}" alt="${escapeHtml(path)}" loading="lazy" decoding="async">
      ${editable && replaceWhenFilled ? `<button type="button" class="slot-add" data-action="${escapeHtml(addAction)}"${idAttr}${clipboard.attrs} aria-label="更换图片">+</button>` : ""}
      ${editable ? `<button type="button" class="slot-remove" data-action="${escapeHtml(removeAction)}"${idAttr}${indexAttr} aria-label="移除图片">×</button>` : ""}
      ${renderSlotOverlay(path)}
    </div>
  `;
}

function renderEditablePromptField({
  name,
  value,
  className = "",
  clearAction = "",
  copyAction = "",
  beforeCopyAction = "",
  countAction = "",
  instanceId = "",
  retryLabel = "",
}) {
  const promptClass = `field prompt-field is-editable ${className}`.trim();
  const idAttr = instanceId === "" ? "" : ` data-id="${escapeHtml(instanceId)}"`;
  const clearTitleButton = clearAction
    ? `<button type="button" class="field-title-action prompt-title-clear" data-action="${escapeHtml(clearAction)}"${idAttr} data-skip-batch-save="true" aria-label="清空提示词">清除</button>`
    : "";
  const copyButton = copyAction === "copy-instance-prompt"
    ? `<button type="button" class="field-title-action" data-action="copy-instance-prompt" data-id="${escapeHtml(instanceId)}" data-skip-batch-save="true">复制</button>`
    : "";
  const retryBadge = retryLabel
    ? `<span class="field-title-retry" title="${escapeHtml(retryLabel)}">${escapeHtml(retryLabel)}</span>`
    : "";
  const countSlot = countAction || beforeCopyAction || "";
  const titleActions = clearTitleButton || copyButton || countSlot
    ? `
      <span class="field-title-actions">
        <span class="field-title-action-slot field-title-clear-slot">${clearTitleButton || `<span class="field-title-clear-placeholder"></span>`}</span>
        <span class="field-title-action-slot field-title-copy-slot">${copyButton}</span>
        <span class="field-title-action-slot field-title-count-slot">${countSlot}</span>
      </span>
    `
    : "";

  return `
    <label class="${escapeHtml(promptClass)}">
      <div class="field-title-row">
        <span>提示词</span>
        ${retryBadge}
        ${titleActions}
      </div>
      <div class="prompt-shell">
        <textarea
          name="${escapeHtml(name)}"
          rows="3"
          spellcheck="false"
          autocapitalize="off"
          autocomplete="off"
          autocorrect="off"
        >${escapeHtml(value)}</textarea>
      </div>
    </label>
  `;
}

function renderReadonlyPromptField({
  name,
  value,
  className = "",
  copyAction = "",
  beforeCopyAction = "",
  countAction = "",
  instanceId = "",
  retryLabel = "",
}) {
  const promptClass = `field prompt-field is-readonly ${className}`.trim();
  const copyButton = copyAction === "copy-instance-prompt"
    ? `<button type="button" class="field-title-action" data-action="copy-instance-prompt" data-id="${escapeHtml(instanceId)}" data-skip-batch-save="true">复制</button>`
    : "";
  const retryBadge = retryLabel
    ? `<span class="field-title-retry" title="${escapeHtml(retryLabel)}">${escapeHtml(retryLabel)}</span>`
    : "";
  const countSlot = countAction || beforeCopyAction || "";
  const titleActions = copyButton || countSlot
    ? `
      <span class="field-title-actions">
        <span class="field-title-action-slot field-title-clear-slot"><span class="field-title-clear-placeholder"></span></span>
        <span class="field-title-action-slot field-title-copy-slot">${copyButton}</span>
        <span class="field-title-action-slot field-title-count-slot">${countSlot}</span>
      </span>
    `
    : "";

  return `
    <label class="${escapeHtml(promptClass)}">
      <div class="field-title-row">
        <span>提示词</span>
        ${retryBadge}
        ${titleActions}
      </div>
      <div class="prompt-shell">
        <textarea
          name="${escapeHtml(name)}"
          rows="3"
          readonly
          tabindex="-1"
          spellcheck="false"
          autocapitalize="off"
          autocomplete="off"
          autocorrect="off"
        >${escapeHtml(value)}</textarea>
        <div class="prompt-overlay">${escapeHtml(value)}</div>
      </div>
    </label>
  `;
}

function renderPromptField(options) {
  return options.readonly
    ? renderReadonlyPromptField(options)
    : renderEditablePromptField(options);
}

function autoGrowPromptTextarea(textarea) {
  if (!textarea?.matches?.("textarea")) {
    return;
  }
  textarea.style.height = "auto";
  textarea.style.height = `${Math.max(textarea.scrollHeight, textarea.clientHeight)}px`;
}

function resetPromptTextareaHeight(textarea) {
  if (!textarea?.matches?.("textarea")) {
    return;
  }
  if (textarea.classList.contains("code-example-editor")) {
    return;
  }
  textarea.style.height = "";
}

function renderTagSelector({
  scope,
  tags,
  draft,
  editable = true,
  instanceId = "",
  open = false,
}) {
  const selectedTags = Array.isArray(tags) ? tags : [];
  const selectedSet = new Set(selectedTags);
  const displayTags = selectedTags.map((tag) => (
    String(tag).length > 8 ? `${String(tag).slice(0, 8)}` : String(tag)
  ));
  const inputName = scope === "operation" ? "tag_draft" : "instance_tag_draft";
  const draftText = String(draft || "");
  const normalizedDraft = draftText.trim();
  const query = normalizedDraft.toLowerCase();
  const idAttr = instanceId === "" ? "" : ` data-id="${escapeHtml(instanceId)}"`;
  const options = (state.tagOptions || [])
    .filter((tag) => !selectedSet.has(tag))
    .filter((tag) => !query || tag.toLowerCase().includes(query));
  const hasExact = (state.tagOptions || []).some(
    (tag) => tag.toLowerCase() === normalizedDraft.toLowerCase(),
  );
  const newOption = normalizedDraft && !hasExact && !selectedSet.has(normalizedDraft)
    ? `
      <button
        type="button"
        class="tag-selector-option is-new"
        data-action="select-tag-option"
        data-scope="${escapeHtml(scope)}"
        data-tag="${escapeHtml(normalizedDraft)}"${idAttr}
      >
        新加：${escapeHtml(normalizedDraft)}
      </button>
    `
    : "";
  const optionHtml = [...options.map((tag) => `
      <button
        type="button"
        class="tag-selector-option"
        data-action="select-tag-option"
        data-scope="${escapeHtml(scope)}"
        data-tag="${escapeHtml(tag)}"${idAttr}
      >
        ${escapeHtml(tag)}
      </button>
    `), newOption].join("");
  const chips = selectedTags.map((tag, index) => `
      <span class="tag-chip">
        ${escapeHtml(displayTags[index])}
        ${
          editable
            ? `<button type="button" data-action="remove-tag-chip" data-scope="${escapeHtml(scope)}" data-index="${index}"${idAttr} aria-label="移除标签">×</button>`
            : ""
        }
      </span>
    `).join("");
  const readonlyPlaceholder = !editable && !chips
    ? `<span class="tag-placeholder">添加标签</span>`
    : "";
  const clearButton = editable && selectedTags.length && scope !== "instance"
    ? `
      <button
        type="button"
        class="tag-selector-clear"
        data-action="clear-tag-selector"
        data-scope="${escapeHtml(scope)}"${idAttr}
        aria-label="清空标签"
      >×</button>
    `
    : "";

  return `
    <div class="tag-selector ${open ? "is-open" : ""} ${editable ? "" : "is-readonly"}">
      <div class="tag-selector-input-wrap">
        ${chips}
        ${readonlyPlaceholder}
        ${
          editable
            ? `
              <input
                name="${escapeHtml(inputName)}"
                value="${escapeHtml(draftText)}"
                placeholder="添加标签"
                data-action="open-tag-selector"
                data-scope="${escapeHtml(scope)}"${idAttr}
              >
            `
            : ""
        }
        ${clearButton}
      </div>
      ${
        editable && open
          ? `
            <div class="tag-selector-menu" data-skip-batch-save="true">
              ${optionHtml || `<div class="tag-selector-empty">暂无可选 TAG</div>`}
            </div>
          `
          : ""
      }
    </div>
  `;
}

function renderAspectRatioPicker() {
  if (isActiveOpenAIGoogleProvider()) {
    return `
      <div class="field record-aspect-ratio openai-google-size-disabled">
        <span>分辨率</span>
          <button type="button" class="aspect-ratio-current option-current" title="无" disabled>
          <span>无</span>
          <span class="select-arrow" aria-hidden="true">▾</span>
        </button>
      </div>
    `;
  }
  const clarity = state.operation.generation_clarity || defaultGenerationClarity();
  const size = state.operation.generation_size || defaultGenerationSize();
  const presetOptions = ASPECT_RATIO_PRESETS.map((ratio) => `
      <button
        type="button"
        class="aspect-ratio-option ${ratio === state.operation.aspect_ratio ? "is-active" : ""}"
        data-action="set-aspect-ratio"
        data-aspect-ratio="${escapeHtml(ratio)}"
      >
        ${escapeHtml(displayAspectRatioOption(ratio, clarity))}
      </button>
    `).join("");
  const customOptions = customGenerationSizes().map((size) => `
      <div class="custom-size-option ${size === state.operation.generation_size ? "is-active" : ""}">
        <button
          type="button"
          class="custom-size-choice"
          data-action="set-custom-generation-size"
          data-size="${escapeHtml(size)}"
        >
          ${escapeHtml(displayCustomSizeOption(size))}
        </button>
        <button
          type="button"
          class="custom-size-delete"
          data-action="remove-custom-generation-size"
          data-size="${escapeHtml(size)}"
          title="删除"
        >×</button>
      </div>
    `).join("");
  const isCustom = clarity === "custom";

  return `
    <div class="field record-aspect-ratio">
      <span>分辨率</span>
      <button
        type="button"
        class="aspect-ratio-current option-current"
        data-action="toggle-aspect-ratio-picker"
        title="${escapeHtml(isCustom ? displayCustomSizeOption(size) : displayAspectRatioOption(state.operation.aspect_ratio, clarity))}"
      >
        <span>${escapeHtml(displayAspectRatioButtonText())}</span>
        <span class="select-arrow" aria-hidden="true">▾</span>
      </button>
      ${
        state.operation.aspect_ratio_picker_open
          ? `
            <div class="aspect-ratio-popover" data-skip-batch-save="true">
              ${isCustom ? customOptions : `<div class="aspect-ratio-grid">${presetOptions}</div>`}
              ${
                isCustom
                  ? `
                    <div class="size-custom-row">
                      <input
                        name="custom_generation_size"
                        value="${escapeHtml(state.operation.custom_generation_size || size)}"
                        placeholder="1024x1024"
                      >
                      <button type="button" data-action="confirm-custom-size">确认</button>
                    </div>
                  `
                  : ""
              }
              ${
                state.operation.size_error
                  ? `<div class="size-error">${escapeHtml(state.operation.size_error)}</div>`
                  : ""
              }
            </div>
          `
          : ""
      }
    </div>
  `;
}

function renderSizePicker() {
  return renderAspectRatioPicker();
}

function renderClarityPicker() {
  if (isActiveOpenAIGoogleProvider()) {
    return `
      <div class="field record-clarity openai-google-size-disabled">
        <span>清晰度</span>
        <div class="clarity-count-row">
          <button type="button" class="clarity-current option-current" title="无" disabled>
            <span>无</span>
            <span class="select-arrow" aria-hidden="true">▾</span>
          </button>
          <input
            class="generation-count-input"
            name="generation_count"
            value="${escapeHtml(state.operation.generation_count || DEFAULT_GENERATION_COUNT)}"
            inputmode="numeric"
            pattern="[1-9][0-9]*"
          >
        </div>
      </div>
    `;
  }
  const clarity = state.operation.generation_clarity || defaultGenerationClarity();
  const count = state.operation.generation_count || DEFAULT_GENERATION_COUNT;
  const presets = CLARITY_PRESETS.map((preset) => {
    const label = preset === "custom" ? "自定义" : preset;
    return `
      <button
        type="button"
        class="option-preset ${preset === clarity ? "is-active" : ""}"
        data-action="set-generation-clarity"
        data-clarity="${escapeHtml(preset)}"
      >
        ${escapeHtml(label)}
      </button>
    `;
  }).join("");
  const visibleClarity = clarity === "custom" ? "" : clarity;

  return `
    <div class="field record-clarity">
      <span>清晰度</span>
      <div class="clarity-count-row">
        <button
          type="button"
          class="clarity-current option-current"
          data-action="toggle-clarity-picker"
          title="${clarity === "custom" ? "自定义清晰度" : escapeHtml(clarity)}"
        >
          <span>${escapeHtml(visibleClarity)}</span>
          <span class="select-arrow" aria-hidden="true">▾</span>
        </button>
        <input
          class="generation-count-input"
          name="generation_count"
          value="${escapeHtml(count)}"
          inputmode="numeric"
          pattern="[1-9][0-9]*"
        >
      </div>
      ${
        state.operation.clarity_picker_open
          ? `
            <div class="clarity-popover" data-skip-batch-save="true">
              ${presets}
            </div>
          `
          : ""
      }
    </div>
  `;
}

function renderResolutionPicker() {
  return renderClarityPicker();
}

function renderGenerationOptions() {
  return `
    <div class="field record-generation-options">
      ${renderAspectRatioPicker()}
      ${renderClarityPicker()}
    </div>
  `;
}

function renderOperationInputImagesBlock() {
  const inputSlots = state.operation.input_image_paths
    .map((path, index) => renderImageSlot(path, "choose-input-images", index))
    .join("");

  return `
    <div class="field record-input-images operation-input-images">
      ${renderImageFieldHeader("输入图", {
        editable: true,
        action: "clear-operation-input-images",
        buttonLabel: "清除",
      })}
      <div class="image-grid">
        ${inputSlots}
        ${renderImageSlot("", "choose-input-images")}
      </div>
    </div>
  `;
}

function renderGenerationPathOptions() {
  const paths = [...new Set(cleanStringArray(state.generationPathHistory || []))];
  if (!paths.length) {
    return "";
  }
  return `
    <div class="generation-path-dropdown" role="listbox">
      ${paths.map((path) => `
        <button type="button" data-action="select-generation-path-history" data-generation-path="${escapeHtml(path)}" title="${escapeHtml(path)}">
          ${escapeHtml(path)}
        </button>
      `).join("")}
    </div>
  `;
}

function renderGenerationPathDropdown() {
  return state.generationPathDropdownOpen ? renderGenerationPathOptions() : "";
}

function scrollGenerationPathInputToEnd() {
  const input = document.querySelector(".generation-path-input");
  if (!input) {
    return;
  }
  requestAnimationFrame(() => {
    input.scrollLeft = input.scrollWidth;
    if (document.activeElement === input && typeof input.setSelectionRange === "function") {
      const end = String(input.value || "").length;
      input.setSelectionRange(end, end);
    }
  });
}

function renderOperationArea() {
  const customSizeDisplayProbe = state.operation.generation_clarity === "custom"
    ? (state.operation.generation_size || state.operation.custom_generation_size)
    : "";
  const status = generationTaskSummary();
  const statusMessage = status.message;
  const statusType = status.type;
  return `
    <form class="image-record record-row operation-area" data-operation-form>
      ${renderEditablePromptField({
        name: "prompt",
        value: state.operation.prompt,
        className: "record-prompt operation-prompt",
        clearAction: "clear-operation-prompt",
      })}

      ${renderOperationInputImagesBlock()}

      ${renderGenerationOptions()}

      <div class="field record-detail">
        <div class="detail-stack">
          ${renderOperationProviderSelect()}
          ${renderTagSelector({
            scope: "operation",
            tags: state.operation.tags,
            draft: state.operation.tag_draft,
            editable: true,
            open: Boolean(state.operation.tag_selector_open),
          })}
          <div class="path-row">
            <div class="generation-path-combobox">
              <input class="generation-path-input" name="generation_path" value="${escapeHtml(state.operation.generation_path)}" title="${escapeHtml(state.operation.generation_path)}" placeholder="生成路径" autocomplete="off">
              <button type="button" class="generation-path-toggle" data-action="toggle-generation-path-dropdown" aria-label="选择生成路径历史">▾</button>
              ${renderGenerationPathDropdown()}
            </div>
            <button type="button" data-action="choose-generation-path">选择</button>
          </div>
        </div>
      </div>

      <div class="record-actions actions operation-actions">
        <div class="operation-button-row">
          <button type="button" data-action="clear-operation">清空</button>
          <button type="submit" class="primary" data-action="add-operation-draft">新增</button>
        </div>
      </div>
      <div class="operation-status-panel">
        <div class="message operation-status-row operation-status-tail" data-message data-status-type="${escapeHtml(statusType)}" title="${escapeHtml(statusMessage)}">${escapeHtml(statusMessage)}</div>
        ${statusMessage ? `<div class="operation-status-popover">${escapeHtml(statusMessage)}</div>` : ""}
        ${renderGenerationTaskDetails()}
      </div>
    </form>
  `;
}


Object.assign(globalThis, {
  render,
  isActiveOpenAIGoogleProvider,
  renderManagerIfActive,
  renderSettingsIfActive,
  renderDataSafetyIfActive,
  renderManager,
  normalizeOperation,
  renderSlotOverlay,
  clipboardTargetForAction,
  sameClipboardImageTarget,
  clipboardTargetAttrs,
  renderEmptyImageSlot,
  renderImageSlot,
  renderSavedImageSlot,
  renderEditablePromptField,
  renderReadonlyPromptField,
  renderPromptField,
  autoGrowPromptTextarea,
  resetPromptTextareaHeight,
  renderTagSelector,
  renderAspectRatioPicker,
  renderSizePicker,
  renderClarityPicker,
  renderResolutionPicker,
  renderGenerationOptions,
  renderOperationInputImagesBlock,
  renderGenerationPathOptions,
  renderGenerationPathDropdown,
  scrollGenerationPathInputToEnd,
  renderOperationArea,
});
