function defaultPersistedUiState() {
  return {
    operation: {},
    filters: {
      q: "",
      tags: [],
      mode_filter: "all",
      provider: "all",
      status: "all",
      statuses: [],
      size: "all",
      call_method: "all",
      model: "all",
      start_date: "",
      end_date: "",
      sort: "created_desc",
      page: 1,
      per_page: 50,
    },
    history: {
      q: "",
      tags: [],
      status: "all",
      provider: "all",
      size: "all",
      mode: "all",
      call_method: "all",
      model: "all",
      start_date: "",
      end_date: "",
      page: 1,
      per_page: 50,
    },
    save_view_mode: "list",
    provider_markers: {},
    generation_path_history: [],
    successful_provider_field_history: {
      api_key_env: [],
      model: [],
      user_agent: [],
    },
    node_filter_path: [{ selection: "all", node_id: null }],
  };
}

function persistedOperationState() {
  return {
    mode: normalizeOption(state.operation.mode, ["text_to_image", "image_to_image"], "text_to_image"),
    prompt: cleanString(state.operation.prompt),
    input_image_paths: cleanStringArray(state.operation.input_image_paths),
    tags: cleanStringArray(state.operation.tags),
    generation_path: cleanString(state.operation.generation_path),
    aspect_ratio: normalizeOption(state.operation.aspect_ratio, ASPECT_RATIO_PRESETS, "1:1"),
    generation_size: isValidGenerationSize(state.operation.generation_size)
      ? String(state.operation.generation_size).trim()
      : DEFAULT_GENERATION_SIZE,
    generation_clarity: isValidGenerationResolution(state.operation.generation_clarity)
      ? String(state.operation.generation_clarity).trim()
      : DEFAULT_GENERATION_RESOLUTION,
    resolution: isValidGenerationResolution(state.operation.resolution)
      ? String(state.operation.resolution).trim()
      : DEFAULT_GENERATION_RESOLUTION,
    custom_generation_size: isValidGenerationSize(state.operation.custom_generation_size)
      ? String(state.operation.custom_generation_size).trim()
      : "",
    generation_count: normalizeGenerationCount(state.operation.generation_count),
    text_generation_count: normalizeGenerationCount(state.operation.text_generation_count),
  };
}

function normalizeSavedStatuses(value, legacyStatus = "") {
  const values = Array.isArray(value) ? value : [];
  const result = [];
  const seen = new Set();
  for (const item of values) {
    const clean = normalizeOption(String(item || ""), SAVE_STATUS_FILTER_OPTIONS, "");
    if (clean && !seen.has(clean)) {
      seen.add(clean);
      result.push(clean);
    }
  }
  if (result.length) {
    return result;
  }
  const legacy = normalizeOption(String(legacyStatus || ""), ["all", ...SAVE_STATUS_FILTER_OPTIONS], "all");
  return legacy === "all" ? [] : [legacy];
}

function persistedSaveFilterState() {
  const statuses = normalizeSavedStatuses(state.filters.statuses, state.filters.status);
  return {
    q: cleanString(state.filters.q),
    tags: cleanStringArray(state.filters.tags),
    mode_filter: normalizeSaveModeFilter(state.filters.mode_filter),
    provider: cleanString(state.filters.provider || "all") || "all",
    status: statuses.length ? statuses[0] : "all",
    statuses,
    size: cleanString(state.filters.size || "all") || "all",
    call_method: cleanString(state.filters.call_method || "all") || "all",
    model: cleanString(state.filters.model || "all") || "all",
    start_date: cleanString(state.filters.start_date),
    end_date: cleanString(state.filters.end_date),
    sort: normalizeOption(state.filters.sort, SAVE_SORT_OPTIONS, "created_desc"),
    page: normalizePositiveInteger(state.filters.page),
    per_page: normalizeSavePerPage(state.filters.per_page),
  };
}

function persistedHistoryState() {
  return {
    q: cleanString(state.history.q),
    tags: cleanStringArray(state.history.tags),
    status: normalizeOption(state.history.status, HISTORY_STATUS_OPTIONS, "all"),
    provider: cleanString(state.history.provider || "all") || "all",
    size: cleanString(state.history.size || "all") || "all",
    mode: cleanString(state.history.mode || "all") || "all",
    call_method: cleanString(state.history.call_method || "all") || "all",
    model: cleanString(state.history.model || "all") || "all",
    number_type: normalizeOption(state.history.number_type, ["all", "#", "H", "instance", "history"], "all"),
    start_date: cleanString(state.history.start_date),
    end_date: cleanString(state.history.end_date),
    page: normalizePositiveInteger(state.history.page),
    per_page: normalizeHistoryPerPage(state.history.per_page),
  };
}

function persistedSaveViewMode() {
  return normalizeOption(state.saveViewMode, ["list", "thumbnail"], "list");
}

function persistedNodeFilterPath() {
  const path = Array.isArray(state.nodeFilter?.path) ? state.nodeFilter.path : [];
  const cleanPath = path
    .map((entry) => ({
      selection: normalizeOption(String(entry?.selection || "all"), ["all", "unassigned", "node"], "all"),
      node_id: entry?.node_id ? normalizePositiveInteger(entry.node_id, 0) : null,
    }))
    .filter((entry, index) => index === 0 || entry.selection === "node" || entry.selection === "all" || entry.selection === "unassigned");
  return cleanPath.length ? cleanPath : [{ selection: "all", node_id: null }];
}

function persistedSuccessfulProviderFieldHistory() {
  const source = safeObject(state.successfulProviderFieldHistory);
  return {
    api_key_env: cleanStringArray(source.api_key_env).slice(0, 20),
    model: cleanStringArray(source.model).slice(0, 20),
    user_agent: cleanStringArray(source.user_agent).slice(0, 20),
  };
}

function persistedProviderMarkers() {
  const source = safeObject(state.providerMarkers);
  const markers = {};
  for (const [providerKey, marker] of Object.entries(source)) {
    const key = String(providerKey || "").trim();
    const value = normalizeOption(String(marker || ""), ["checked", "unused", "rejected"], "rejected");
    if (key && value !== "rejected") {
      markers[key] = value;
    }
  }
  return markers;
}

function loadPersistedUiState() {
  try {
    const stored = localStorage.getItem(UI_STATE_STORAGE_KEY);
    if (!stored) {
      return defaultPersistedUiState();
    }
    const parsed = JSON.parse(stored);
    if (!parsed || typeof parsed !== "object") {
      return defaultPersistedUiState();
    }
    return {
      ...defaultPersistedUiState(),
      ...parsed,
    };
  } catch (error) {
    return defaultPersistedUiState();
  }
}

function persistUiState() {
  try {
    const payload = {
      operation: persistedOperationState(),
      filters: persistedSaveFilterState(),
      history: persistedHistoryState(),
      save_view_mode: persistedSaveViewMode(),
      provider_markers: persistedProviderMarkers(),
      generation_path_history: cleanStringArray(state.generationPathHistory).slice(0, 20),
      successful_provider_field_history: persistedSuccessfulProviderFieldHistory(),
      node_filter_path: persistedNodeFilterPath(),
    };
    localStorage.setItem(UI_STATE_STORAGE_KEY, JSON.stringify(payload));
  } catch (error) {
    // localStorage can be unavailable in privacy modes; normal app behavior should continue.
  }
}

function applyPersistedUiState(savedState) {
  const saved = safeObject(savedState);
  const savedOperation = safeObject(saved.operation);
  const savedFilters = safeObject(saved.filters);
  const savedHistory = safeObject(saved.history);
  const savedProviderFieldHistory = safeObject(saved.successful_provider_field_history);
  const savedProviderMarkers = safeObject(saved.provider_markers);
  const savedNodePath = Array.isArray(saved.node_filter_path) ? saved.node_filter_path : [];
  state.saveViewMode = normalizeOption(saved.save_view_mode, ["list", "thumbnail"], "list");
  state.providerMarkers = {};
  for (const [providerKey, marker] of Object.entries(savedProviderMarkers)) {
    const key = String(providerKey || "").trim();
    const value = normalizeOption(String(marker || ""), ["checked", "unused", "rejected"], "rejected");
    if (key && value !== "rejected") {
      state.providerMarkers[key] = value;
    }
  }
  state.generationPathHistory = cleanStringArray(saved.generation_path_history).slice(0, 20);
  state.successfulProviderFieldHistory = {
    api_key_env: cleanStringArray(savedProviderFieldHistory.api_key_env).slice(0, 20),
    model: cleanStringArray(savedProviderFieldHistory.model).slice(0, 20),
    user_agent: cleanStringArray(savedProviderFieldHistory.user_agent).slice(0, 20),
  };

  if (Object.prototype.hasOwnProperty.call(savedOperation, "mode")) {
    state.operation.mode = normalizeOption(savedOperation.mode, ["text_to_image", "image_to_image"], "text_to_image");
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "prompt")) {
    state.operation.prompt = cleanString(savedOperation.prompt);
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "input_image_paths")) {
    state.operation.input_image_paths = cleanStringArray(savedOperation.input_image_paths);
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "tags")) {
    state.operation.tags = cleanStringArray(savedOperation.tags);
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "generation_path")) {
    state.operation.generation_path = cleanString(savedOperation.generation_path);
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "aspect_ratio")) {
    state.operation.aspect_ratio = normalizeOption(savedOperation.aspect_ratio, ASPECT_RATIO_PRESETS, state.operation.aspect_ratio || "1:1");
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "generation_clarity")) {
    state.operation.generation_clarity = normalizeOption(savedOperation.generation_clarity, CLARITY_PRESETS, state.operation.generation_clarity || DEFAULT_GENERATION_RESOLUTION);
    state.operation.resolution = state.operation.generation_clarity;
  }
  if (
    Object.prototype.hasOwnProperty.call(savedOperation, "generation_size")
    && isValidGenerationSize(savedOperation.generation_size)
  ) {
    state.operation.generation_size = String(savedOperation.generation_size).trim();
  }
  if (
    Object.prototype.hasOwnProperty.call(savedOperation, "custom_generation_size")
    && isValidGenerationSize(savedOperation.custom_generation_size)
  ) {
    state.operation.custom_generation_size = String(savedOperation.custom_generation_size).trim();
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "generation_count")) {
    state.operation.generation_count = normalizeGenerationCount(savedOperation.generation_count);
  }
  if (Object.prototype.hasOwnProperty.call(savedOperation, "text_generation_count")) {
    state.operation.text_generation_count = normalizeGenerationCount(savedOperation.text_generation_count);
  }
  normalizeOperation();

  state.filters.q = cleanString(savedFilters.q);
  state.filters.tags = cleanStringArray(savedFilters.tags);
  state.filters.source = "all";
  state.filters.mode_filter = normalizeSaveModeFilter(savedFilters.mode_filter);
  state.filters.provider = cleanString(savedFilters.provider || "all") || "all";
  state.filters.statuses = normalizeSavedStatuses(savedFilters.statuses, savedFilters.status);
  state.filters.status = state.filters.statuses[0] || "all";
  state.filters.size = cleanString(savedFilters.size || "all") || "all";
  state.filters.call_method = cleanString(savedFilters.call_method || "all") || "all";
  state.filters.model = cleanString(savedFilters.model || "all") || "all";
  state.filters.start_date = cleanString(savedFilters.start_date);
  state.filters.end_date = cleanString(savedFilters.end_date);
  state.filters.sort = normalizeOption(savedFilters.sort, SAVE_SORT_OPTIONS, "created_desc");
  state.filters.page = normalizePositiveInteger(savedFilters.page);
  state.filters.per_page = normalizeSavePerPage(savedFilters.per_page);
  state.filters.tag_search = "";
  state.filters.tag_dropdown_open = false;
  state.filters.status_dropdown_open = false;

  state.history.q = cleanString(savedHistory.q);
  state.history.tags = cleanStringArray(savedHistory.tags);
  state.history.status = normalizeOption(savedHistory.status, HISTORY_STATUS_OPTIONS, "all");
  state.history.provider = cleanString(savedHistory.provider || "all") || "all";
  state.history.size = cleanString(savedHistory.size || "all") || "all";
  state.history.mode = cleanString(savedHistory.mode || "all") || "all";
  state.history.call_method = cleanString(savedHistory.call_method || "all") || "all";
  state.history.model = cleanString(savedHistory.model || "all") || "all";
  state.history.number_type = normalizeOption(savedHistory.number_type, ["all", "#", "H", "instance", "history"], "all");
  state.history.start_date = cleanString(savedHistory.start_date);
  state.history.end_date = cleanString(savedHistory.end_date);
  state.history.page = normalizePositiveInteger(savedHistory.page);
  state.history.per_page = normalizeHistoryPerPage(savedHistory.per_page);
  state.history.tag_search = "";
  state.history.history_tag_dropdown_open = false;
  state.nodeFilter.path = savedNodePath.length
    ? savedNodePath.map((entry) => ({
      selection: normalizeOption(String(entry?.selection || "all"), ["all", "unassigned", "node"], "all"),
      node_id: entry?.node_id ? normalizePositiveInteger(entry.node_id, 0) : null,
    }))
    : [{ selection: "all", node_id: null }];
}

function maxPageForTotal(total, perPage) {
  const cleanTotal = Math.max(0, Number.parseInt(total, 10) || 0);
  const cleanPerPage = Math.max(1, Number.parseInt(perPage, 10) || 50);
  return cleanTotal > 0 ? Math.ceil(cleanTotal / cleanPerPage) : 1;
}

function normalizePageForTotal(page, total, perPage) {
  const cleanPage = normalizePositiveInteger(page);
  const maxPage = maxPageForTotal(total, perPage);
  return Math.min(Math.max(1, cleanPage), maxPage);
}

function shouldReloadForNormalizedPage(currentPage, normalizedPage) {
  return Number(currentPage) !== Number(normalizedPage);
}


Object.assign(globalThis, {
  defaultPersistedUiState,
  normalizeSavedStatuses,
  persistedOperationState,
  persistedSaveFilterState,
  persistedHistoryState,
  persistedSaveViewMode,
  persistedProviderMarkers,
  persistedNodeFilterPath,
  loadPersistedUiState,
  persistUiState,
  applyPersistedUiState,
  maxPageForTotal,
  normalizePageForTotal,
  shouldReloadForNormalizedPage,
});
