async function boot() {
  mountAppVersionBadge();
  try {
    const data = await api("/api/settings");
    state.settings = data.settings;
    await loadOpenAIScriptExamples().catch(() => {});
    const persistedUiState = loadPersistedUiState();
    state.operation.generation_path = state.settings?.default_output_dir || "";
    state.operation.aspect_ratio = defaultAspectRatio();
    state.operation.generation_clarity = defaultGenerationClarity();
    state.operation.generation_size = defaultGenerationSize();
    state.operation.resolution = state.operation.generation_clarity;
    state.operation.custom_resolution = defaultCustomResolution();
    state.operation.generation_count = defaultGenerationCount();
    state.operation.custom_generation_size = state.operation.generation_size;
    applyPersistedUiState(persistedUiState);
    await loadGenerationPathHistory().catch(() => {});
    await loadProviderFieldHistory().catch(() => {});
    await loadNodes();
    await loadInstances();
    await loadTags();
    state.loading = false;
    render();
    syncRunningRefresh();
  } catch (error) {
    state.loading = false;
    render();
    setMessage(error.message, "error");
  }
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    if (state.page === "manager") {
      syncOperationFromDom();
    }
    closeHistoryTextPopover();
    state.generationPathDropdownOpen = false;
    state.settingHistoryDropdownOpen = "";
    state.operation.provider_dropdown_open = false;
    state.page = tab.dataset.page;
    if (state.page !== "manager") {
      state.saveAreaKeyboardFocus = false;
      stopRunningRefresh();
    }
    render();
    if (state.page === "history") {
      loadGenerationHistoryFilterOptions().catch(() => {});
      loadGenerationHistory().catch(() => {});
    }
    if (state.page === "data-safety") {
      loadBackups().catch(() => {});
      loadThumbnailCacheStats().catch(() => {});
    }
    if (state.page === "tag-management") {
      loadTagManagementTags().catch(() => {});
    }
  });
});

function closeFloatingDropdownsForClick(target) {
  let closedManagerDropdown = false;
  let closedSettingsDropdown = false;
  if (!target.closest?.(".generation-path-combobox") && state.generationPathDropdownOpen) {
    syncOperationFromDom();
    state.generationPathDropdownOpen = false;
    document.querySelector(".generation-path-dropdown")?.remove();
    closedManagerDropdown = true;
  }
  if (!target.closest?.(".operation-provider-select") && state.operation.provider_dropdown_open) {
    syncOperationFromDom();
    closeOperationProviderDropdown({ render: false });
    document.querySelector(".operation-provider-dropdown")?.remove();
    closedManagerDropdown = true;
  }
  if (!target.closest?.(".setting-history-combobox") && state.settingHistoryDropdownOpen) {
    state.settingHistoryDropdownOpen = "";
    document.querySelector(".setting-history-dropdown")?.remove();
    closedSettingsDropdown = true;
  }
  return {
    manager: closedManagerDropdown,
    settings: closedSettingsDropdown,
  };
}

function renderClosedFloatingDropdowns(closedDropdowns) {
  if (closedDropdowns?.manager) {
    renderManagerIfActive();
  }
  if (closedDropdowns?.settings) {
    renderSettingsIfActive();
  }
}

let suppressHistoryPopoverHoverUntilLeave = false;

function isNodeMenuInteractiveTarget(target) {
  return Boolean(
    target?.closest?.(".node-select-wrap")
      || target?.closest?.(".node-menu")
      || target?.closest?.("[data-node-context-menu]")
      || target?.closest?.("[data-node-name-dialog]"),
  );
}

function closeNodeMenusForOutsidePointerDown(event) {
  if (
    state.page !== "manager"
    || !(state.nodeMenu?.openKey || state.nodeContextMenu?.open)
    || isNodeMenuInteractiveTarget(event.target)
  ) {
    return;
  }
  closeNodeMenus();
  renderManagerIfActive();
}

app.addEventListener("click", async (event) => {
  const imageSlot = event.target.closest("[data-image-path]");
  if (!imageSlot) {
    hideImageHoverPreview();
  }
  const historyPopoverSource = event.target.closest("[data-history-popover-source]");
  if (historyPopoverSource) {
    event.preventDefault();
    toggleHistoryTextPopover(historyPopoverSource, true);
    return;
  }
  closeHistoryTextPopover();
  const actionNode = event.target.closest("[data-action]");
  const action = actionNode?.dataset.action;
  const closedDropdowns = closeFloatingDropdownsForClick(event.target);
  if (actionNode) {
    setClipboardImageTargetFromNode(actionNode, { render: false });
  }
  if (
    state.page === "history"
    && state.history.history_tag_dropdown_open
    && !event.target.closest(".history-tag-filter")
  ) {
    state.history.history_tag_dropdown_open = false;
    renderHistoryPage();
    if (!actionNode) {
      return;
    }
  }
  if (state.page === "tag-management" && state.tagManagementContextMenu?.open && !event.target.closest("[data-tag-management-context-menu]")) {
    closeTagManagementContextMenu();
    if (!actionNode) {
      renderTagManagementIfActive();
    }
  }
  if (!actionNode) {
    if (event.target.closest("textarea, input, select")) {
      return;
    }
    const backdrop = event.target.closest("[data-lightbox-backdrop]");
    if (backdrop && event.target === backdrop) {
      closeImageLightbox();
      return;
    }
    const closeArea = event.target.closest("[data-lightbox-close-area]");
    if (closeArea && !event.target.closest(".lightbox-image")) {
      closeImageLightbox();
      return;
    }
    const imageSlot = event.target.closest("[data-image-path]");
    if (imageSlot?.dataset.imagePath) {
      hideImageHoverPreview();
      setClipboardImageTargetFromNode(imageSlot, { render: false });
      openImageLightbox(imageSlot.dataset.imagePath, imageSlot);
      return;
    }
    let closedOperationPicker = false;
    if (!event.target.closest(".record-aspect-ratio") && state.operation.aspect_ratio_picker_open) {
      syncOperationFromDom();
      state.operation.aspect_ratio_picker_open = false;
      state.operation.size_picker_open = false;
      closedOperationPicker = true;
    }
    if (!event.target.closest(".record-clarity") && state.operation.clarity_picker_open) {
      syncOperationFromDom();
      state.operation.clarity_picker_open = false;
      state.operation.resolution_picker_open = false;
      closedOperationPicker = true;
    }
    if (closedOperationPicker) {
      renderManager();
      return;
    }
    if (state.page === "tag-management" && event.target.matches("[data-tag-management-dialog]")) {
      closeMergeTagManagement();
      return;
    }
    if (!event.target.closest(".tag-filter") && state.filters.tag_dropdown_open) {
      state.filters.tag_dropdown_open = false;
      renderManager();
      return;
    }
    if (!event.target.closest(".save-status-filter") && state.filters.status_dropdown_open) {
      state.filters.status_dropdown_open = false;
      renderManager();
      return;
    }
    if (
      !event.target.closest("[data-node-controls]")
      && !event.target.closest("[data-node-context-menu]")
      && (state.nodeMenu?.openKey || state.nodeContextMenu?.open)
    ) {
      closeNodeMenus();
      renderManagerIfActive();
      return;
    }
    if (!event.target.closest(".tag-selector")) {
      closeTagSelectors();
      renderManagerIfActive();
      return;
    }
    if (closedDropdowns.manager) {
      renderClosedFloatingDropdowns(closedDropdowns);
      return;
    }
    if (closedDropdowns.settings) {
      renderClosedFloatingDropdowns(closedDropdowns);
      return;
    }
    return;
  }
  if (actionNode.closest(".image-slot") || actionNode.closest("[data-lightbox-backdrop]")) {
    event.stopPropagation();
  }
  if (action === "close-lightbox") {
    closeImageLightbox();
  }
  if (action === "lightbox-zoom-in") {
    zoomLightbox(LIGHTBOX_ZOOM_STEP);
  }
  if (action === "lightbox-zoom-out") {
    zoomLightbox(-LIGHTBOX_ZOOM_STEP);
  }
  if (action === "lightbox-fit") {
    resetLightboxZoom();
  }
  if (action === "lightbox-prev") {
    switchLightboxImage(-1);
  }
  if (action === "lightbox-next") {
    switchLightboxImage(1);
  }
  if (action === "select-empty-image-slot") {
    setClipboardImageTargetFromNode(actionNode);
    return;
  }
  if (action === "toggle-aspect-ratio-picker") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    toggleAspectRatioPicker();
  }
  if (action === "toggle-size-picker") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    toggleSizePicker();
  }
  if (action === "toggle-clarity-picker") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    toggleClarityPicker();
  }
  if (action === "toggle-resolution-picker") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    toggleResolutionPicker();
  }
  if (action === "close-size-picker") {
    syncOperationFromDom();
    state.operation.size_picker_open = false;
    state.operation.size_error = "";
    renderManager();
  }
  if (action === "set-aspect-ratio") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    setAspectRatio(actionNode.dataset.aspectRatio);
  }
  if (action === "set-custom-generation-size") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    setCustomGenerationSize(actionNode.dataset.size);
  }
  if (action === "remove-custom-generation-size") {
    removeCustomGenerationSize(actionNode.dataset.size);
  }
  if (action === "set-generation-size") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    setGenerationSize(actionNode.dataset.size);
  }
  if (action === "set-generation-clarity") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    setGenerationClarity(actionNode.dataset.clarity);
  }
  if (action === "set-generation-resolution") {
    if (isActiveOpenAIGoogleProvider()) {
      return;
    }
    setGenerationResolution(actionNode.dataset.resolution);
  }
  if (action === "set-save-layout") {
    setSaveLayout(actionNode.dataset.layout);
  }
  if (action === "toggle-operation-provider-dropdown") {
    state.operation.provider_dropdown_open = !state.operation.provider_dropdown_open;
    renderManager();
  }
  if (action === "select-operation-provider") {
    event.stopPropagation();
    const providerKey = actionNode.dataset.providerKey || "";
    const providerChanged = providerKey && providerKey !== activeProviderName();
    closeOperationProviderDropdown({ render: !providerChanged });
    if (providerChanged) {
      changeOperationProvider(providerKey);
    }
  }
  if (action === "toggle-operation-provider-marker") {
    event.stopPropagation();
    toggleProviderMarker(actionNode.dataset.providerKey || "");
  }
  if (action === "toggle-thumbnail-view") {
    toggleSaveThumbnailView();
  }
  if (action === "refresh-tag-management") {
    loadTagManagementTags().catch(() => {});
  }
  if (action === "rename-tag-management") {
    renameTagFromManagement(actionNode.dataset.tagId, actionNode.dataset.tagName);
  }
  if (action === "open-merge-tag-management") {
    openMergeTagManagement(actionNode.dataset.tagId);
  }
  if (action === "close-merge-tag-management") {
    closeMergeTagManagement();
  }
  if (action === "confirm-merge-tag-management") {
    confirmMergeTagManagement(actionNode.dataset.targetTagId);
  }
  if (action === "confirm-custom-size") {
    syncOperationFromDom();
    setCustomGenerationSize(state.operation.custom_generation_size);
  }
  if (action === "open-tag-selector") {
    openTagSelector(actionNode.dataset.scope, actionNode.dataset.id || "");
  }
  if (action === "select-tag-option") {
    selectTagChoice(actionNode.dataset.scope, actionNode.dataset.tag, actionNode.dataset.id || "");
  }
  if (action === "remove-tag-chip") {
    removeTagChip(actionNode.dataset.scope, Number(actionNode.dataset.index), actionNode.dataset.id || "");
  }
  if (action === "clear-tag-selector") {
    event.stopPropagation();
    clearTagSelector(actionNode.dataset.scope, actionNode.dataset.id || "");
  }
  if (action === "create-node") {
    changeNodeFilter(
      normalizeNodeFilterPath().length,
      "new",
      String(deepestSelectedNodeId() || ""),
    ).catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "rename-current-node") {
    renameCurrentNode().catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "delete-current-node") {
    deleteCurrentNode().catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "toggle-tag-filter-dropdown") {
    state.filters.tag_dropdown_open = !state.filters.tag_dropdown_open;
    state.filters.status_dropdown_open = false;
    renderManager();
  }
  if (action === "toggle-filter-tag") {
    const tag = actionNode.dataset.tag || "";
    const tags = new Set(state.filters.tags || []);
    if (tag === UNTAGGED_FILTER_VALUE) {
      if (tags.has(UNTAGGED_FILTER_VALUE)) {
        tags.delete(UNTAGGED_FILTER_VALUE);
      } else {
        tags.clear();
        tags.add(UNTAGGED_FILTER_VALUE);
      }
    } else if (tags.has(tag)) {
      tags.delete(tag);
    } else if (tag) {
      tags.delete(UNTAGGED_FILTER_VALUE);
      tags.add(tag);
    }
    state.filters.tags = [...tags];
    state.filters.tag_dropdown_open = true;
    state.filters.page = 1;
    clearCurrentPageSelection();
    persistUiState();
    refreshInstances().catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "clear-tag-filter") {
    clearTagFilter();
  }
  if (action === "toggle-save-status-filter-dropdown") {
    state.filters.status_dropdown_open = !state.filters.status_dropdown_open;
    state.filters.tag_dropdown_open = false;
    renderManager();
  }
  if (action === "toggle-save-status-filter") {
    toggleSaveStatusFilter(actionNode.dataset.status || "all");
  }
  if (action === "clear-save-status-filter") {
    clearSaveStatusFilter();
  }
  if (action === "toggle-history-tag-filter-dropdown") {
    state.history.history_tag_dropdown_open = !state.history.history_tag_dropdown_open;
    renderHistoryPage();
  }
  if (action === "toggle-history-filter-tag") {
    toggleHistoryFilterTag(actionNode.dataset.tag || "");
  }
  if (action === "clear-history-tag-filter") {
    clearHistoryTagFilter();
  }
  if (action === "toggle-node-menu") {
    toggleNodeMenu(actionNode.dataset.nodeMenuKey || "");
  }
  if (action === "select-node-option") {
    if (state.nodeDrag?.suppressClick) {
      event.preventDefault();
      state.nodeDrag.suppressClick = false;
      return;
    }
    changeNodeFilter(
      actionNode.dataset.nodeLevel,
      actionNode.dataset.nodeValue || "all",
      actionNode.dataset.parentId || "",
    ).catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "rename-node-from-menu") {
    const nodeId = actionNode.dataset.nodeId || "";
    closeNodeMenus();
    renameNodeById(nodeId).catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "delete-node-from-menu") {
    const nodeId = actionNode.dataset.nodeId || "";
    closeNodeMenus();
    deleteNodeById(nodeId).catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "apply-prompt-search") {
    const toolbar = actionNode.closest("[data-save-toolbar]");
    if (toolbar) {
      applySaveFilters(toolbar);
    }
  }
  if (action === "choose-default-dir") {
    chooseDefaultDir();
  }
  if (action === "choose-input-images") {
    chooseInputImages();
  }
  if (action === "remove-input-image") {
    removeInputImage(Number(actionNode.dataset.index));
  }
  if (action === "clear-operation-input-images") {
    clearOperationInputImages();
  }
  if (action === "add-operation-tag") {
    addOperationTag();
  }
  if (action === "remove-operation-tag") {
    removeOperationTag(Number(actionNode.dataset.index));
  }
  if (action === "choose-generation-path") {
    chooseGenerationPath();
  }
  if (action === "toggle-generation-path-dropdown") {
    syncOperationFromDom();
    state.settingHistoryDropdownOpen = "";
    state.operation.provider_dropdown_open = false;
    state.generationPathDropdownOpen = !state.generationPathDropdownOpen;
    renderManager();
  }
  if (action === "select-generation-path-history") {
    syncOperationFromDom();
    state.operation.generation_path = actionNode.dataset.generationPath || "";
    state.generationPathDropdownOpen = false;
    persistUiState();
    renderManager();
  }
  if (action === "clear-operation") {
    clearOperation();
    persistUiState();
  }
  if (action === "clear-operation-prompt") {
    clearOperationPrompt();
  }
  if (action === "clear-prompt-search") {
    event.stopPropagation();
    clearPromptSearch();
  }
  if (action === "clear-instance-prompt") {
    event.stopPropagation();
    clearInstancePrompt(actionNode.dataset.id);
  }
  if (action === "new-provider") {
    createProviderDraft();
  }
  if (action === "copy-provider") {
    copyProviderDraft();
  }
  if (action === "cancel-settings-changes") {
    cancelSettingsChanges();
  }
  if (action === "delete-provider") {
    deleteProvider();
  }
  if (action === "toggle-setting-history") {
    const field = actionNode.dataset.settingHistoryField || "";
    state.generationPathDropdownOpen = false;
    state.operation.provider_dropdown_open = false;
    state.settingHistoryDropdownOpen = state.settingHistoryDropdownOpen === field ? "" : field;
    renderSettings();
  }
  if (action === "select-setting-history") {
    const field = actionNode.dataset.settingHistoryField || "";
    const value = actionNode.dataset.settingHistoryValue || "";
    const form = actionNode.closest("[data-settings-form]");
    const input = form?.elements?.[field];
    if (input) {
      const previousValue = input.value;
      input.value = value;
      syncSettingsProviderDraftFromForm(form);
      if (value !== previousValue) {
        markSettingsDirty();
      }
    }
    state.settingHistoryDropdownOpen = "";
    renderSettings();
  }
  if (action === "show-code-example-tab") {
    showCodeExampleTab(actionNode.dataset.codeTab);
  }
  if (action === "edit-code-example") {
    editCodeExample();
  }
  if (action === "save-code-example") {
    saveCodeExample();
  }
  if (action === "cancel-code-example") {
    cancelCodeExample();
  }
  if (action === "copy-code-example") {
    copyCodeExample(actionNode.dataset.codeTarget);
  }
  if (action === "save-custom-script") {
    saveCustomScript();
  }
  if (action === "clear-custom-script") {
    clearCustomScript();
  }
  if (action === "new-manual-instance") {
    addOperationDraft();
  }
  if (action === "path-replace") {
    openPathReplaceDialog();
  }
  if (action === "create-backup") {
    createBackup();
  }
  if (action === "refresh-backups") {
    loadBackups().catch((error) => {
      state.dataSafety.error = error.message;
      renderDataSafetyIfActive();
    });
  }
  if (action === "open-backup-folder") {
    openBackupFolder();
  }
  if (action === "clear-thumbnail-cache") {
    clearThumbnailCache();
  }
  if (action === "export-data") {
    exportDataPackage();
  }
  if (action === "choose-backup-file") {
    chooseBackup();
  }
  if (action === "select-backup") {
    state.dataSafety.selectedBackupPath = actionNode.dataset.backupPath || "";
    state.dataSafety.status = "已选择备份";
    state.dataSafety.error = "";
    previewRestoreFile(state.dataSafety.selectedBackupPath);
    renderDataSafetyIfActive();
  }
  if (action === "restore-selected-backup") {
    restoreSelectedBackup();
  }
  if (action === "edit-instance") {
    startEditingInstance(actionNode.dataset.id);
  }
  if (action === "cancel-edit-instance") {
    cancelEditingInstance(actionNode.dataset.id);
  }
  if (action === "save-instance") {
    saveInstanceDraft(actionNode.dataset.id);
  }
  if (action === "copy-instance-prompt") {
    copyInstancePrompt(actionNode.dataset.id);
  }
  if (action === "bring-instance-to-operation") {
    bringInstanceToOperation(actionNode.dataset.id).catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "bring-history-to-operation") {
    bringHistoryToOperation(actionNode.dataset.historyId).catch((error) => {
      setMessage(error.message, "error");
    });
  }
  if (action === "copy-history-field") {
    copyHistoryField(actionNode.dataset.historyId, actionNode.dataset.historyField);
  }
  if (action === "delete-instance") {
    deleteInstance(actionNode.dataset.id);
  }
  if (action === "resubmit-instance") {
    resubmitInstance(actionNode.dataset.id);
  }
  if (action === "copy-submit-instance") {
    copySubmitInstance(actionNode.dataset.id);
  }
  if (action === "submit-manual-instance") {
    submitManualInstance(actionNode.dataset.id);
  }
  if (action === "retry-failed-instance") {
    retryFailedInstance(actionNode.dataset.id);
  }
  if (action === "cancel-generation-task") {
    cancelGenerationTask(actionNode.dataset.taskId);
  }
  if (action === "toggle-select-instance") {
    if (event.shiftKey) {
      event.preventDefault();
    }
    toggleSelectInstance(actionNode.dataset.id, { shiftKey: event.shiftKey });
  }
  if (action === "toggle-select-zone") {
    if (event.shiftKey) {
      event.preventDefault();
    }
    toggleSelectInstanceFromZone(actionNode.dataset.id, { shiftKey: event.shiftKey });
  }
  if (action === "select-current-page") {
    selectCurrentPageInstances();
  }
  if (action === "clear-selection") {
    clearCurrentPageSelection();
    renderManagerIfActive();
  }
  if (action === "undo-last-action") {
    undoLastAction().catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "redo-last-action") {
    redoLastAction().catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (action === "batch-add-tags") {
    batchAddTags();
  }
  if (action === "batch-remove-tags") {
    batchRemoveTags();
  }
  if (action === "batch-delete-instances") {
    batchDeleteInstances();
  }
  if (action === "batch-move-instances") {
    batchMoveInstances();
  }
  if (action === "batch-submit-instances") {
    submitSelectedInstances();
  }
  if (action === "batch-copy-instances") {
    batchCopyInstances();
  }
  if (action === "move-instance") {
    moveInstance(actionNode.dataset.id);
  }
  if (action === "choose-instance-input-images") {
    chooseInstanceInputImages(actionNode.dataset.id);
  }
  if (action === "remove-instance-input-image") {
    removeInstanceInputImage(actionNode.dataset.id, Number(actionNode.dataset.index));
  }
  if (action === "clear-instance-input-images") {
    clearInstanceInputImages(actionNode.dataset.id);
  }
  if (action === "choose-instance-output-image") {
    chooseInstanceOutputImage(actionNode.dataset.id);
  }
  if (action === "remove-instance-output-image") {
    removeInstanceOutputImage(actionNode.dataset.id);
  }
  if (action === "add-instance-tag") {
    addInstanceTag(actionNode.dataset.id);
  }
  if (action === "remove-instance-tag") {
    removeInstanceTag(actionNode.dataset.id, Number(actionNode.dataset.index));
  }
  if (action === "clear-instance-tags") {
    event.stopPropagation();
    clearInstanceTagsImmediate(actionNode.dataset.id);
  }
  if (action === "save-page-first") {
    setSavePage(1);
  }
  if (action === "save-page-prev") {
    changeSavePage(-1);
  }
  if (action === "save-page-next") {
    changeSavePage(1);
  }
  if (action === "save-page-last") {
    const totalPages = Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50)));
    setSavePage(totalPages);
  }
  if (action === "history-page-first") {
    setHistoryPage(1);
  }
  if (action === "history-page-prev") {
    changeHistoryPage(-1);
  }
  if (action === "history-page-next") {
    changeHistoryPage(1);
  }
  if (action === "history-page-last") {
    const totalPages = Math.max(1, Math.ceil((state.history.total || 0) / (state.history.per_page || 50)));
    setHistoryPage(totalPages);
  }
  if (action === "refresh-history") {
    loadGenerationHistoryFilterOptions().catch(() => {});
    loadGenerationHistory().catch((error) => {
      if (state.page === "history") {
        setMessage(error.message, "error");
      }
    });
  }
});

app.addEventListener("pointerover", (event) => {
  const historyPopoverSource = event.target.closest("[data-history-popover-source]");
  if (historyPopoverSource && app.contains(historyPopoverSource)) {
    if (suppressHistoryPopoverHoverUntilLeave || historyPopoverSource.dataset.historyPopoverSuppressHover === "true") {
      return;
    }
    showHistoryTextPopover(historyPopoverSource);
    return;
  }
  const imageSlot = event.target.closest("[data-image-path]");
  if (!imageSlot || !app.contains(imageSlot)) {
    return;
  }
  showImageHoverPreview(imageSlot.dataset.imagePath);
});

app.addEventListener("pointerout", (event) => {
  const historyPopoverSource = event.target.closest("[data-history-popover-source]");
  if (historyPopoverSource && !historyPopoverSource.contains(event.relatedTarget)) {
    suppressHistoryPopoverHoverUntilLeave = false;
    delete historyPopoverSource.dataset.historyPopoverSuppressHover;
    if (!document.querySelector("[data-history-popover].is-pinned")) {
      closeHistoryTextPopover();
    }
    return;
  }
  const imageSlot = event.target.closest("[data-image-path]");
  if (!imageSlot || !app.contains(imageSlot)) {
    return;
  }
  if (event.relatedTarget && imageSlot.contains(event.relatedTarget)) {
    return;
  }
  hideImageHoverPreview();
});

app.addEventListener("contextmenu", (event) => {
  const tagCard = event.target.closest("[data-tag-management-context-id]");
  if (tagCard && app.contains(tagCard)) {
    event.preventDefault();
    openTagManagementContextMenu(
      tagCard.dataset.tagManagementContextId,
      tagCard.dataset.tagName || "",
      event.clientX,
      event.clientY,
    );
    return;
  }
  const nodeOption = event.target.closest("[data-node-context-id]");
  if (!nodeOption || !app.contains(nodeOption)) {
    return;
  }
  event.preventDefault();
  openNodeContextMenu(nodeOption.dataset.nodeContextId, event.clientX, event.clientY);
});

app.addEventListener("dragstart", (event) => {
  handleNodeDragStart(event);
});

app.addEventListener("dragover", (event) => {
  if (handleNodeDragOver(event)) {
    return;
  }
  if (!event.target.closest("[data-clipboard-image-target]")) {
    return;
  }
  event.preventDefault();
});

app.addEventListener("drop", (event) => {
  if (handleNodeDrop(event)) {
    return;
  }
  const target = event.target.closest("[data-clipboard-image-target]");
  if (!target) {
    return;
  }
  event.preventDefault();
  setClipboardImageTargetFromNode(target);
  setMessage("拖拽无法读取原始路径，请从资源管理器复制图片文件后粘贴，或点击选择图片。", "error");
});

app.addEventListener("dragend", () => {
  handleNodeDragEnd();
});

app.addEventListener("change", (event) => {
  if (event.target.dataset.action === "change-node-filter") {
    changeNodeFilter(event.target.dataset.nodeLevel, event.target.value, event.target.dataset.parentId || "").catch((error) => {
      if (state.page === "manager") {
        setMessage(error.message, "error");
      }
    });
  }
  if (event.target.name === "provider") {
    if (!state.settings) {
      return;
    }
    state.settingHistoryDropdownOpen = "";
    state.settingsEditingProvider = event.target.value;
    state.settingsProviderDraftIsNew = false;
    clearSettingsDirty();
    renderSettings();
  }
  if (
    event.target.name === "adapter"
    || event.target.name === "output_format"
    || event.target.name === "openai_call_method"
    || event.target.name === "openai_example_mode"
    || event.target.name === "proxy_mode"
    || event.target.name === "google_stream"
  ) {
    const form = event.target.closest("[data-settings-form]");
    const switchedOpenAIExampleMode = event.target.name === "openai_example_mode";
    const switchedAdapter = event.target.name === "adapter";
    syncSettingsProviderDraftFromForm(form);
    markSettingsDirty();
    if (switchedOpenAIExampleMode || switchedAdapter) {
      state.settingsCodeExample.editDraft = "";
    }
    renderSettings();
  }
  if (event.target.name === "generation_count") {
    const count = parseGenerationCount(event.target.value);
    if (!count) {
      return;
    }
    state.operation.generation_count = count;
    state.operation.text_generation_count = count;
    persistUiState();
    saveDefaultCount(count).catch((error) => {
      if (state.page === "manager") {
        setMessage(`数量已用于当前页面，但保存默认值失败：${error.message}`, "error");
      }
    });
  }
  if (event.target.name === "custom_resolution") {
    state.operation.custom_resolution = event.target.value || "";
    saveDefaultResolution("custom", state.operation.custom_resolution).catch((error) => {
      if (state.page === "manager") {
        setMessage(`分辨率已用于当前页面，但保存默认值失败：${error.message}`, "error");
      }
    });
  }
  if (
    event.target.name === "history_status"
    || event.target.name === "history_provider"
    || event.target.name === "history_size"
    || event.target.name === "history_mode"
    || event.target.name === "history_call_method"
    || event.target.name === "history_model"
    || event.target.name === "history_number_type"
    || event.target.name === "history_start_date"
    || event.target.name === "history_end_date"
    || event.target.name === "history_per_page"
  ) {
    const form = event.target.closest("[data-history-toolbar]");
    if (form) {
      applyHistoryFilters(form);
    }
  }
  if (event.target.name === "history_cleanup_before_date") {
    state.history.cleanup = {
      ...(state.history.cleanup || {}),
      before_date: event.target.value || "",
    };
  }
  if (event.target.name === "tag_management_q") {
    state.tagManagement.q = event.target.value || "";
  }
  if (event.target.name === "history_q") {
    state.history.q = event.target.value || "";
  }
  if (event.target.name === "history_tag_filter_search") {
    state.history.tag_search = event.target.value || "";
    renderHistoryPage();
    document.querySelector('[name="history_tag_filter_search"]')?.focus();
  }
  if (event.target.name === "history_cleanup_before_date") {
    state.history.cleanup = {
      ...(state.history.cleanup || {}),
      before_date: event.target.value || "",
    };
  }
});

app.addEventListener("input", (event) => {
  const settingsForm = event.target.closest?.("[data-settings-form]");
  if (settingsForm) {
    syncSettingsProviderDraftFromForm(settingsForm);
    markSettingsDirty();
  }
  if (event.target.matches("textarea")) {
    autoGrowPromptTextarea(event.target);
    if (event.target.name === "prompt") {
      state.operation.prompt = event.target.value || "";
      persistUiState();
    }
    if (event.target.name === "instance_prompt") {
      const card = event.target.closest("[data-instance-card]");
      if (card?.dataset.id) {
        syncInstanceDraftFromDom(card.dataset.id);
      }
    }
  }
  if (event.target.name === "tag_draft") {
    updateTagDraft("operation", "", event.target.value);
  }
  if (event.target.name === "instance_tag_draft") {
    const card = event.target.closest("[data-instance-card]");
    if (card?.dataset.id) {
      updateTagDraft("instance", card.dataset.id, event.target.value);
    }
  }
  if (event.target.name === "custom_resolution") {
    state.operation.custom_resolution = event.target.value || "";
  }
  if (event.target.name === "custom_generation_size") {
    state.operation.custom_generation_size = event.target.value || "";
    persistUiState();
  }
  if (event.target.name === "generation_path") {
    state.operation.generation_path = event.target.value || "";
    state.generationPathDropdownOpen = Boolean(state.generationPathHistory?.length);
    persistUiState();
  }
  if (event.target.name === "generation_count") {
    state.operation.generation_count = event.target.value || "";
    state.operation.text_generation_count = state.operation.generation_count;
    persistUiState();
  }
  if (event.target.name === "custom_script") {
    const form = event.target.closest("[data-settings-form]");
    syncSettingsProviderDraftFromForm(form);
    markSettingsDirty();
  }
  if (event.target.name === "tag_management_q") {
    state.tagManagement.q = event.target.value || "";
  }
});

app.addEventListener("focusin", (event) => {
  if (event.target.matches("textarea")) {
    autoGrowPromptTextarea(event.target);
  }
});

app.addEventListener("focusout", (event) => {
  if (event.target.matches("textarea")) {
    resetPromptTextareaHeight(event.target);
  }
});

app.addEventListener("compositionstart", (event) => {
  if (event.target.matches("textarea")) {
    state.isComposingPrompt = true;
  }
});

app.addEventListener("compositionend", (event) => {
  if (event.target.matches("textarea")) {
    state.isComposingPrompt = false;
    autoGrowPromptTextarea(event.target);
    if (event.target.name === "prompt") {
      state.operation.prompt = event.target.value || "";
    }
    if (event.target.name === "instance_prompt") {
      const card = event.target.closest("[data-instance-card]");
      if (card?.dataset.id) {
        syncInstanceDraftFromDom(card.dataset.id);
      }
    }
  }
});

window.addEventListener("beforeunload", () => {
  syncOperationFromDom();
  persistUiState();
});

function canUseCtrlEnterGenerate(event) {
  if (!event.ctrlKey || event.key !== "Enter") {
    return false;
  }
  if (event.repeat || event.isComposing || state.isComposingPrompt) {
    return false;
  }
  if (state.page !== "manager") {
    return false;
  }
  if (state.lightbox.path) {
    return false;
  }
  if (document.querySelector("[data-path-replace-dialog], [data-lightbox-backdrop], .modal-backdrop")) {
    return false;
  }
  return true;
}

function canUseAltNAddDraft(event) {
  if (!event.altKey || String(event.key || "").toLowerCase() !== "n") {
    return false;
  }
  if (event.repeat || event.isComposing || state.isComposingPrompt) {
    return false;
  }
  if (state.page !== "manager") {
    return false;
  }
  if (state.lightbox.path || hasBlockingSaveAreaKeyboardLayer()) {
    return false;
  }
  return true;
}

function isSaveAreaKeyboardTextTarget(target) {
  return Boolean(target?.closest?.(
    "input, textarea, select, [contenteditable='true'], "
      + ".prompt-field, .tag-selector-input-wrap, "
      + "[data-node-name-dialog], [data-move-dialog], [data-settings-form]",
  ));
}

function isSaveAreaKeyboardFloatingTarget(target) {
  return Boolean(target?.closest?.(
    "[data-lightbox-backdrop], .modal-backdrop, .modal, "
      + ".tag-filter-menu, .tag-selector-menu, .node-menu, .node-context-menu, "
      + "[data-node-name-dialog], [data-move-dialog], [data-path-replace-dialog], "
      + "[data-history-popover]",
  ));
}

function hasBlockingSaveAreaKeyboardLayer() {
  return Boolean(
    state.lightbox.path
      || state.nodeMenu?.openKey
      || state.nodeContextMenu?.open
      || state.filters.tag_dropdown_open
      || state.operation.aspect_ratio_picker_open
      || state.operation.clarity_picker_open
      || state.operation.size_picker_open
      || state.operation.resolution_picker_open
      || document.querySelector(
        "[data-lightbox-backdrop], .modal-backdrop, .modal.is-open, .dialog.is-open, "
          + ".popover.is-open, .tag-selector.is-open, .tag-filter-menu, "
          + ".node-menu, .node-context-menu, [data-path-replace-dialog], "
          + "[data-history-popover].is-pinned",
      ),
  );
}

function isHistoryKeyboardTextTarget(target) {
  return Boolean(target?.closest?.(
    "input, textarea, select, [contenteditable='true'], [contenteditable='']",
  ));
}

function hasBlockingHistoryKeyboardLayer() {
  return Boolean(
    state.lightbox.path
      || hasPinnedHistoryTextPopover()
      || document.querySelector(
        "[data-lightbox-backdrop], .modal-backdrop, .modal.is-open, .dialog.is-open, "
          + ".popover.is-open, .tag-filter-menu, [data-history-popover].is-pinned",
      ),
  );
}

function handleHistoryKeyboardPaging(event) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
    return false;
  }
  if (event.ctrlKey || event.shiftKey || event.altKey || event.metaKey || event.isComposing) {
    return false;
  }
  if (state.page !== "history") {
    return false;
  }
  if (isHistoryKeyboardTextTarget(event.target) || hasBlockingHistoryKeyboardLayer()) {
    return false;
  }

  const totalPages = Math.max(1, Math.ceil((state.history.total || 0) / (state.history.per_page || 50)));
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    if (state.history.page <= 1) {
      return true;
    }
    changeHistoryPage(-1);
    return true;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    if (state.history.page >= totalPages) {
      return true;
    }
    changeHistoryPage(1);
    return true;
  }
  return false;
}

function handleEscapeEditingInstances(event) {
  if (
    event.key !== "Escape"
    || state.page !== "manager"
    || !state.editing?.size
    || hasBlockingSaveAreaKeyboardLayer()
  ) {
    return false;
  }
  event.preventDefault();
  cancelAllEditingInstances();
  return true;
}

function updateSaveAreaKeyboardFocusFromTarget(target) {
  if (state.page !== "manager" || isSaveAreaKeyboardFloatingTarget(target)) {
    state.saveAreaKeyboardFocus = false;
    return;
  }
  state.saveAreaKeyboardFocus = Boolean(target?.closest?.("[data-save-area]"));
}

function handleSaveAreaKeyboardFocusPointerDown(event) {
  updateSaveAreaKeyboardFocusFromTarget(event.target);
}

function handleSaveAreaKeyboardFocusIn(event) {
  updateSaveAreaKeyboardFocusFromTarget(event.target);
}

function handleSaveAreaKeyboardPaging(event) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
    return false;
  }
  if (event.ctrlKey || event.shiftKey || event.altKey || event.metaKey) {
    return false;
  }
  if (state.page !== "manager" || !state.saveAreaKeyboardFocus) {
    return false;
  }
  if (isSaveAreaKeyboardTextTarget(event.target) || hasBlockingSaveAreaKeyboardLayer()) {
    return false;
  }

  const totalPages = Math.max(1, Math.ceil((state.total || 0) / (state.filters.per_page || 50)));
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    if (state.filters.page <= 1) {
      return true;
    }
    changeSavePage(-1);
    return true;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    if (state.filters.page >= totalPages) {
      return true;
    }
    changeSavePage(1);
    return true;
  }
  return false;
}

document.addEventListener("pointerdown", handleSaveAreaKeyboardFocusPointerDown, true);
document.addEventListener("focusin", handleSaveAreaKeyboardFocusIn, true);
document.addEventListener("pointerdown", (event) => {
  markManagerInteraction(event.target);
}, true);
document.addEventListener("pointerdown", closeNodeMenusForOutsidePointerDown, true);

document.addEventListener("click", (event) => {
  if (
    state.page === "history"
    && state.history.history_tag_dropdown_open
    && !event.target.closest?.(".history-tag-filter")
  ) {
    state.history.history_tag_dropdown_open = false;
    renderHistoryPage();
  }
  if (
    state.page === "manager"
    && (state.nodeMenu?.openKey || state.nodeContextMenu?.open)
    && !isNodeMenuInteractiveTarget(event.target)
  ) {
    closeNodeMenus();
    renderManagerIfActive();
  }
});

document.addEventListener("keydown", (event) => {
  if (canUseCtrlEnterGenerate(event)) {
    event.preventDefault();
    submitSelectedInstances();
    return;
  }
  if (canUseAltNAddDraft(event)) {
    event.preventDefault();
    addOperationDraft();
    return;
  }
  if (event.key === "Escape" && state.lightbox.path) {
    event.preventDefault();
    closeImageLightbox();
    return;
  }
  if (event.key === "Escape" && (state.nodeMenu?.openKey || state.nodeContextMenu?.open)) {
    event.preventDefault();
    closeNodeMenus();
    renderManagerIfActive();
    return;
  }
  if (event.key === "Escape" && hasPinnedHistoryTextPopover()) {
    event.preventDefault();
    suppressHistoryPopoverHoverUntilLeave = true;
    document.querySelectorAll("[data-history-popover-source]").forEach((source) => {
      if (source.matches(":hover")) {
        source.dataset.historyPopoverSuppressHover = "true";
      }
    });
    closeHistoryTextPopover();
    return;
  }
  if (event.key === "Escape" && state.tagManagement?.mergeDialog?.open) {
    event.preventDefault();
    closeMergeTagManagement();
    return;
  }
  if (handleEscapeEditingInstances(event)) {
    return;
  }
  if (event.key === "Escape" && state.page === "manager" && hasSelectedInstances()) {
    event.preventDefault();
    clearCurrentPageSelection();
    renderManagerIfActive();
    return;
  }
  if (
    event.key === "Delete"
    && state.page === "manager"
    && hasSelectedInstances()
    && !isSaveAreaKeyboardTextTarget(event.target)
    && !hasBlockingSaveAreaKeyboardLayer()
  ) {
    event.preventDefault();
    batchDeleteInstances();
    return;
  }
  if (event.key === "ArrowLeft" && state.lightbox.path) {
    event.preventDefault();
    switchLightboxImage(-1);
    return;
  }
  if (event.key === "ArrowRight" && state.lightbox.path) {
    event.preventDefault();
    switchLightboxImage(1);
    return;
  }
  if (handleSaveAreaKeyboardPaging(event)) {
    return;
  }
  if (handleHistoryKeyboardPaging(event)) {
    return;
  }
  if (event.key === "Escape" && (
    state.operation.aspect_ratio_picker_open
    || state.operation.clarity_picker_open
    || state.operation.size_picker_open
    || state.operation.resolution_picker_open
    || state.operation.provider_dropdown_open
    || state.filters.tag_dropdown_open
    || state.history.history_tag_dropdown_open
    || state.generationPathDropdownOpen
    || state.settingHistoryDropdownOpen
  )) {
    event.preventDefault();
    syncOperationFromDom();
    state.operation.aspect_ratio_picker_open = false;
    state.operation.clarity_picker_open = false;
    state.operation.size_picker_open = false;
    state.operation.resolution_picker_open = false;
    state.operation.provider_dropdown_open = false;
    state.filters.tag_dropdown_open = false;
    state.history.history_tag_dropdown_open = false;
    state.generationPathDropdownOpen = false;
    state.settingHistoryDropdownOpen = "";
    render();
    return;
  }
  if ((event.key === "Enter" || event.key === " ") && event.target.closest("[data-image-path]")) {
    event.preventDefault();
    const imageSlot = event.target.closest("[data-image-path]");
    hideImageHoverPreview();
    openImageLightbox(imageSlot.dataset.imagePath, imageSlot);
    return;
  }
  if (event.target.name === "tag_draft" && event.key === "Enter") {
    event.preventDefault();
    addOperationTag();
  }
  if (event.target.name === "custom_generation_size" && event.key === "Enter") {
    event.preventDefault();
    syncOperationFromDom();
    setCustomGenerationSize(state.operation.custom_generation_size);
  }
  if (event.target.name === "custom_resolution" && event.key === "Enter") {
    event.preventDefault();
    syncOperationFromDom();
    state.operation.resolution_picker_open = false;
    renderManager();
    saveDefaultResolution("custom", state.operation.custom_resolution).catch((error) => {
      if (state.page === "manager") {
        setMessage(`分辨率已用于当前页面，但保存默认值失败：${error.message}`, "error");
      }
    });
  }
  if (event.target.name === "tag_filter_search" && event.key === "Enter") {
    event.preventDefault();
  }
  if (event.target.name === "history_tag_filter_search" && event.key === "Enter") {
    event.preventDefault();
  }
  if (event.target.name === "instance_tag_draft" && event.key === "Enter") {
    event.preventDefault();
    const card = event.target.closest("[data-instance-card]");
    if (card?.dataset.id) {
      addInstanceTag(card.dataset.id);
    }
  }
});

document.addEventListener("click", handleDocumentBatchSaveBoundary, true);

document.addEventListener("paste", (event) => {
  if (state.page !== "manager" || !state.clipboardImageTarget) {
    return;
  }
  if (event.target.closest?.("textarea, input, select, [contenteditable='true']")) {
    return;
  }
  event.preventDefault();
  pasteClipboardImagePaths();
});

app.addEventListener(
  "wheel",
  (event) => {
    if (!state.lightbox.path || !event.target.closest("[data-lightbox-backdrop]")) {
      return;
    }

    event.preventDefault();
    zoomLightbox(event.deltaY < 0 ? LIGHTBOX_ZOOM_STEP : -LIGHTBOX_ZOOM_STEP);
  },
  { passive: false },
);

app.addEventListener("mousedown", (event) => {
  startLightboxDrag(event);
});

app.addEventListener("mousemove", (event) => {
  moveLightboxDrag(event);
});

app.addEventListener("mouseup", () => {
  endLightboxDrag();
});

app.addEventListener("mouseleave", () => {
  endLightboxDrag();
});

app.addEventListener(
  "error",
  (event) => {
    if (event.target.classList?.contains("lightbox-image")) {
      markLightboxError();
    }
  },
  true,
);

app.addEventListener("submit", (event) => {
  const saveToolbar = event.target.closest("[data-save-toolbar]");
  if (saveToolbar) {
    event.preventDefault();
    applySaveFilters(saveToolbar);
    return;
  }

  const historyToolbar = event.target.closest("[data-history-toolbar]");
  if (historyToolbar) {
    event.preventDefault();
    applyHistoryFilters(historyToolbar);
    return;
  }

  const tagManagementToolbar = event.target.closest("[data-tag-management-toolbar]");
  if (tagManagementToolbar) {
    event.preventDefault();
    applyTagManagementSearch(tagManagementToolbar);
    return;
  }

  const operationForm = event.target.closest("[data-operation-form]");
  if (operationForm) {
    event.preventDefault();
    addOperationDraft();
    return;
  }

  const form = event.target.closest("[data-settings-form]");
  if (!form) {
    return;
  }

  event.preventDefault();
  saveSettings(form);
});



Object.assign(globalThis, {
  boot,
  canUseCtrlEnterGenerate,
  canUseAltNAddDraft,
  isSaveAreaKeyboardTextTarget,
  hasBlockingSaveAreaKeyboardLayer,
  handleSaveAreaKeyboardPaging,
});
