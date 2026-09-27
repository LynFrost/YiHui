const PROVIDER_ADAPTER_MARKERS = {
  "openai": "(c)",
  "openai-google": "(og)",
  "sysrv-google": "(sg)",
  "apimart-openai": "(ao)",
  "google": "(g)",
  "other": "(o)",
};

const ADAPTER_CAPABILITIES = {
  "openai": {
    label: "openai",
    marker: PROVIDER_ADAPTER_MARKERS.openai,
    implemented: true,
    settingsKind: "openai",
    callMethods: {
      "gpt-image-2": {
        label: "gpt-image-2",
        supportsTextToImage: true,
        supportsImageToImage: true,
        supportsCount: true,
        imageToImageCount: 1,
        supportsCustomScript: true,
      },
      "response": {
        label: "response",
        supportsTextToImage: true,
        supportsImageToImage: false,
        supportsCount: false,
        imageToImageCount: 1,
        supportsCustomScript: true,
        message: "Responses API 图生图暂未实现。",
      },
    },
  },
  "openai-google": {
    label: "openai-google",
    marker: PROVIDER_ADAPTER_MARKERS["openai-google"],
    implemented: true,
    settingsKind: "openai-google",
    callMethods: {
      "gpt-image-2": {
        label: "openai-google",
        supportsTextToImage: true,
        supportsImageToImage: true,
        supportsCount: true,
        imageToImageCount: 1,
        supportsCustomScript: true,
      },
    },
  },
  "sysrv-google": {
    label: "sysrv-google",
    marker: PROVIDER_ADAPTER_MARKERS["sysrv-google"],
    implemented: true,
    settingsKind: "sysrv-google",
    callMethods: {
      "gpt-image-2": {
        label: "sysrv-google",
        supportsTextToImage: true,
        supportsImageToImage: true,
        supportsCount: true,
        imageToImageCount: 1,
        supportsCustomScript: true,
      },
    },
  },
  "apimart-openai": {
    label: "apimart-openai",
    marker: PROVIDER_ADAPTER_MARKERS["apimart-openai"],
    implemented: true,
    settingsKind: "apimart-openai",
    callMethods: {
      "gpt-image-2": {
        label: "apimart-openai",
        supportsTextToImage: true,
        supportsImageToImage: true,
        supportsCount: true,
        imageToImageCount: 1,
        supportsCustomScript: true,
      },
    },
  },
  "google": {
    label: "google",
    marker: PROVIDER_ADAPTER_MARKERS.google,
    implemented: false,
    settingsKind: "placeholder",
    message: "Google adapter 暂未实现。",
    callMethods: {},
  },
  "other": {
    label: "other",
    marker: PROVIDER_ADAPTER_MARKERS.other,
    implemented: false,
    settingsKind: "placeholder",
    message: "Other adapter 暂未实现。",
    callMethods: {},
  },
};

const AVAILABLE_PROVIDER_ADAPTERS = Object.entries(ADAPTER_CAPABILITIES)
  .map(([value, capability]) => ({
    value,
    label: capability.label,
  }));

function normalizeProviderAdapter(adapter) {
  const cleanAdapter = String(adapter || "").trim();
  if (cleanAdapter === "aiapis_gpt_image_2") {
    return "openai";
  }
  return Object.prototype.hasOwnProperty.call(ADAPTER_CAPABILITIES, cleanAdapter)
    ? cleanAdapter
    : "openai";
}

function providerCapability(providerOrAdapter = {}) {
  const adapter = typeof providerOrAdapter === "string"
    ? providerOrAdapter
    : providerOrAdapter?.adapter;
  return ADAPTER_CAPABILITIES[normalizeProviderAdapter(adapter)];
}

function providerCallMethodCapability(provider = {}) {
  const capability = providerCapability(provider);
  const callMethods = capability.callMethods || {};
  const callMethod = String(provider?.openai_call_method || "gpt-image-2").trim();
  return callMethods[callMethod] || callMethods["gpt-image-2"] || {};
}

function isProviderImplemented(provider = {}) {
  return Boolean(providerCapability(provider).implemented);
}

function providerUnavailableMessage(provider = {}) {
  const capability = providerCapability(provider);
  return capability.implemented ? "" : capability.message || `${capability.label} adapter 暂未实现。`;
}

function activeProviderName() {
  return state.settings?.active_provider || "";
}

function activeProvider() {
  const providers = state.settings?.providers || {};
  return providers[activeProviderName()] || {};
}

function firstProviderName() {
  return Object.keys(state.settings?.providers || {})[0] || "";
}

function settingsEditingProviderName() {
  const providers = state.settings?.providers || {};
  const currentName = String(state.settingsEditingProvider || "").trim();
  if (currentName && Object.prototype.hasOwnProperty.call(providers, currentName)) {
    return currentName;
  }

  const activeName = activeProviderName();
  if (activeName && Object.prototype.hasOwnProperty.call(providers, activeName)) {
    state.settingsEditingProvider = activeName;
    return activeName;
  }

  const fallbackName = firstProviderName();
  state.settingsEditingProvider = fallbackName;
  return fallbackName;
}

function settingsEditingProvider() {
  const providers = state.settings?.providers || {};
  return providers[settingsEditingProviderName()] || {};
}

function providerFieldDefaults() {
  return {
    display_name: "",
    adapter: "openai",
    base_url: "https://img.aiapis.help/v1",
    api_key: "",
    api_key_env: "IMG_API_KEY",
    user_agent: "",
    model: "gpt-image-2",
    proxy_mode: "system",
    proxy_url: "",
    allow_untrusted_proxy_certificate: true,
    openai_call_method: "gpt-image-2",
    quality: "high",
    output_format: "png",
    output_compression: 80,
    background: "auto",
    moderation: "low",
    user: "",
    google_role: "user",
    google_max_tokens: 4096,
    google_temperature: "",
    google_top_p: "",
    google_stream: false,
    google_stop: "",
    google_presence_penalty: "",
    google_frequency_penalty: "",
    google_logit_bias: "",
    google_user: "",
    google_response_format: "",
    google_seen: "",
    google_tools: "",
    google_tool_choice: "",
    request_timeout_seconds: 300,
    download_timeout_seconds: 120,
    max_retry_attempts: 5,
    apimart_task_timeout_seconds: 420,
    apimart_task_poll_interval_seconds: 5,
    input_fidelity: "",
    mask_path: "",
    openai_example_mode: "text_to_image",
    code_examples: {},
    custom_scripts: {},
  };
}

function blankProviderFieldDefaults() {
  return {
    ...providerFieldDefaults(),
    display_name: "",
    base_url: "",
    api_key: "",
    api_key_env: "",
    user_agent: "",
    model: "",
    proxy_url: "",
  };
}

function isImageToImageMode() {
  return state.operation.mode === "image_to_image";
}

function providerAdapterMarker(adapter) {
  const cleanAdapter = String(adapter || "").trim();
  return ADAPTER_CAPABILITIES[cleanAdapter]?.marker || "";
}

function providerDisplayNameWithAdapter(providerName, provider = {}) {
  const displayName = provider?.display_name || providerName || "未选择 provider";
  const marker = providerAdapterMarker(provider?.adapter);
  return marker ? `${displayName} ${marker}` : displayName;
}

function providerSortLabel(providerName, provider = {}) {
  return String(provider?.display_name || providerName || "").trim().toLocaleLowerCase();
}

function sortedProviderEntries(providerMap = null) {
  const providers = providerMap || state.settings?.providers || {};
  return Object.entries(providers).sort(([nameA, providerA], [nameB, providerB]) => {
    const labelA = providerSortLabel(nameA, providerA);
    const labelB = providerSortLabel(nameB, providerB);
    return labelA.localeCompare(labelB, "en", { sensitivity: "base" })
      || String(nameA).localeCompare(String(nameB), "en", { sensitivity: "base" });
  });
}

function sortedProviderNames(providerMap = null) {
  return sortedProviderEntries(providerMap).map(([name]) => name);
}

function providerFilterOptionEntries(historyValues = [], selectedValue = "", options = {}) {
  const emptyLabel = options.emptyLabel || "未填写";
  const entries = [{ value: "all", label: "全部" }];
  const seen = new Set(["all"]);
  for (const [providerName, provider] of sortedProviderEntries()) {
    entries.push({
      value: providerName,
      label: providerDisplayNameWithAdapter(providerName, provider),
    });
    seen.add(providerName);
  }

  const historicalValues = [...(historyValues || [])]
    .map((value) => String(value || "__empty__"))
    .filter((value) => value !== "all" && value !== "__empty__" && !seen.has(value));
  historicalValues.sort((left, right) =>
    providerSortLabel(left, {}).localeCompare(providerSortLabel(right, {}), "en", { sensitivity: "base" })
      || left.localeCompare(right, "en", { sensitivity: "base" })
  );
  for (const value of historicalValues) {
    entries.push({ value, label: `${value}（历史）` });
    seen.add(value);
  }

  if (selectedValue && selectedValue !== "all" && selectedValue !== "__empty__" && !seen.has(selectedValue)) {
    entries.push({ value: selectedValue, label: `${selectedValue}（历史）` });
    seen.add(selectedValue);
  }
  entries.push({ value: "__empty__", label: emptyLabel });
  return entries;
}

function activeProviderDisplayName() {
  const name = activeProviderName();
  const provider = activeProvider();
  return providerDisplayNameWithAdapter(name, provider);
}

function providerDisplayName(providerName) {
  if (!providerName) {
    return "";
  }
  const provider = state.settings?.providers?.[providerName] || {};
  return providerDisplayNameWithAdapter(providerName, provider);
}

function providerOptionsSelect(selectedValue = "") {
  const options = [];
  options.push(renderSelectedOption("", "未填写", selectedValue || ""));
  for (const [name, provider] of sortedProviderEntries()) {
    options.push(renderSelectedOption(name, providerDisplayNameWithAdapter(name, provider), selectedValue || ""));
  }
  return options.join("");
}

function instanceProviderText(providerName) {
  return providerName ? providerDisplayName(providerName) : "未填写";
}

function providerMarkerState(providerName) {
  const marker = state.providerMarkers?.[providerName];
  return ["checked", "unused", "rejected"].includes(marker) ? marker : "rejected";
}

function providerMarkerLabel(marker) {
  return marker === "checked" ? "√" : marker === "unused" ? "-" : "X";
}

function renderProviderMarkerBadge(providerName, options = {}) {
  const marker = providerMarkerState(providerName);
  const label = providerMarkerLabel(marker);
  const asButton = options.button !== false;
  const title = marker === "checked"
    ? "已标记为 √"
    : marker === "unused"
      ? "已标记为 -，当前没在用了"
      : "已标记为 X";
  if (!asButton) {
    return `
      <span class="operation-provider-marker is-${marker}" title="${escapeHtml(title)}" aria-hidden="true">
        ${escapeHtml(label)}
      </span>
    `;
  }
  return `
    <button
      type="button"
      class="operation-provider-marker is-${marker}"
      data-action="toggle-operation-provider-marker"
      data-provider-key="${escapeHtml(providerName)}"
      title="${escapeHtml(title)}"
      aria-label="切换 ${escapeHtml(providerDisplayName(providerName))} 标记"
    >${escapeHtml(label)}</button>
  `;
}

function closeOperationProviderDropdown({ render = true } = {}) {
  if (!state.operation?.provider_dropdown_open) {
    return false;
  }
  state.operation.provider_dropdown_open = false;
  if (render) {
    renderManagerIfActive();
  }
  return true;
}

function toggleProviderMarker(providerName) {
  const key = String(providerName || "").trim();
  if (!key) {
    return;
  }
  state.providerMarkers = safeObject(state.providerMarkers);
  if (providerMarkerState(key) === "checked") {
    state.providerMarkers[key] = "unused";
  } else if (providerMarkerState(key) === "unused") {
    delete state.providerMarkers[key];
  } else {
    state.providerMarkers[key] = "checked";
  }
  persistUiState();
  renderManagerIfActive();
}

function renderOperationProviderSelect() {
  const providerNames = sortedProviderNames();
  const selectedProvider = activeProviderName();
  const selectedLabel = selectedProvider && state.settings?.providers?.[selectedProvider]
    ? providerDisplayName(selectedProvider)
    : "未选择 provider";
  const disabled = providerNames.length ? "" : "disabled aria-disabled=\"true\"";
  const options = providerNames.length
    ? providerNames.map((providerName) => {
        const selectedClass = providerName === selectedProvider ? " is-selected" : "";
        const provider = state.settings?.providers?.[providerName] || {};
        const adapter = normalizeProviderAdapter(provider.adapter);
        return `
          <div class="operation-provider-option${selectedClass}" role="option" aria-selected="${providerName === selectedProvider ? "true" : "false"}">
            <button
              type="button"
              class="operation-provider-option-main"
              data-action="select-operation-provider"
              data-provider-key="${escapeHtml(providerName)}"
              title="${escapeHtml(providerDisplayName(providerName))}"
            >
              <span class="operation-provider-option-name">${escapeHtml(providerDisplayName(providerName))}</span>
              <span class="operation-provider-option-meta">${escapeHtml(providerName)} · ${escapeHtml(adapter)}</span>
            </button>
            ${renderProviderMarkerBadge(providerName)}
          </div>
        `;
      }).join("")
    : `<div class="operation-provider-empty">未选择 provider</div>`;
  return `
    <div class="operation-provider-note operation-provider-select ${state.operation.provider_dropdown_open ? "is-open" : ""}">
      <span>Provider：</span>
      <div class="operation-provider-combobox">
        <button
          type="button"
          class="operation-provider-trigger"
          data-action="toggle-operation-provider-dropdown"
          title="${escapeHtml(selectedLabel)}"
          aria-haspopup="listbox"
          aria-expanded="${state.operation.provider_dropdown_open ? "true" : "false"}"
          ${disabled}
        >
          <span class="operation-provider-current-name">${escapeHtml(selectedLabel)}</span>
          ${selectedProvider ? renderProviderMarkerBadge(selectedProvider, { button: false }) : ""}
          <span class="operation-provider-arrow" aria-hidden="true">▾</span>
        </button>
        ${state.operation.provider_dropdown_open ? `
          <div class="operation-provider-dropdown" role="listbox">
            ${options}
          </div>
        ` : ""}
      </div>
    </div>
  `;
}

function currentSaveLayout() {
  return state.settings?.save_layout === "single" ? "single" : "double";
}

function saveLayoutClass() {
  return `is-${currentSaveLayout()}`;
}

function shouldShowOperationInputImages() {
  return state.operation.mode === "image_to_image";
}

function isValidGenerationSize(size) {
  return GENERATION_SIZE_PATTERN.test(String(size || "").trim());
}

function isPresetClarity(clarity) {
  return PRESET_RESOLUTIONS.includes(String(clarity || "").trim());
}

function isPresetResolution(resolution) {
  return isPresetClarity(resolution);
}

function defaultGenerationClarity() {
  const clarity = String(
    state.settings?.default_clarity
    || state.settings?.default_resolution
    || DEFAULT_GENERATION_RESOLUTION,
  ).trim();
  return CLARITY_PRESETS.includes(clarity) ? clarity : DEFAULT_GENERATION_RESOLUTION;
}

function isCustomResolutionMode() {
  return state.operation.generation_clarity === "custom";
}

function aspectRatioForSize(size, clarity = state.operation.generation_clarity) {
  const cleanSize = String(size || "").trim();
  const cleanClarity = String(clarity || "").trim();
  if (isPresetClarity(cleanClarity)) {
    for (const [ratio, values] of Object.entries(SIZE_MAP)) {
      if (values[cleanClarity] === cleanSize) {
        return ratio;
      }
    }
  }
  for (const [ratio, values] of Object.entries(SIZE_MAP)) {
    if (Object.values(values).includes(cleanSize)) {
      return ratio;
    }
  }
  return "";
}

function sizeForAspectRatio(aspectRatio, clarity) {
  return SIZE_MAP[aspectRatio]?.[clarity] || "";
}

function defaultAspectRatio() {
  const ratio = String(state.settings?.default_aspect_ratio || "").trim();
  if (ASPECT_RATIO_PRESETS.includes(ratio)) {
    return ratio;
  }
  const configuredSize = String(state.settings?.default_size || "").trim();
  return aspectRatioForSize(configuredSize, defaultGenerationClarity())
    || aspectRatioForSize(configuredSize)
    || "1:1";
}

function customGenerationSizes() {
  const sizes = Array.isArray(state.settings?.custom_generation_sizes)
    ? state.settings.custom_generation_sizes
    : [];
  const unique = [];
  for (const size of sizes) {
    const cleanSize = String(size || "").trim();
    if (isValidGenerationSize(cleanSize) && !unique.includes(cleanSize)) {
      unique.push(cleanSize);
    }
  }
  return unique;
}

function defaultGenerationSize() {
  const clarity = defaultGenerationClarity();
  if (isPresetClarity(clarity)) {
    return sizeForAspectRatio(defaultAspectRatio(), clarity) || DEFAULT_GENERATION_SIZE;
  }
  const size = String(
    state.settings?.default_size
    || activeProvider().default_size
    || DEFAULT_GENERATION_SIZE,
  ).trim();
  return isValidGenerationSize(size) ? size : DEFAULT_GENERATION_SIZE;
}

function displaySizeLabel(size, clarity = state.operation.generation_clarity) {
  const cleanSize = String(size || "").trim();
  const ratio = aspectRatioForSize(cleanSize, clarity) || "自定义";
  return `${cleanSize} (${ratio})`;
}

function displayAspectRatioOption(aspectRatio, clarity = state.operation.generation_clarity) {
  return `${sizeForAspectRatio(aspectRatio, clarity)} (${aspectRatio})`;
}

function displayCustomSizeOption(size) {
  return `${String(size || "").trim()} (自定义)`;
}

function displayAspectRatioButtonText() {
  return state.operation.generation_clarity === "custom"
    ? (state.operation.generation_size || state.operation.custom_generation_size || "自定义")
    : state.operation.aspect_ratio || defaultAspectRatio();
}

function defaultGenerationResolution() {
  return defaultGenerationClarity();
}

function isValidGenerationResolution(resolution) {
  return CLARITY_PRESETS.includes(String(resolution || "").trim());
}

function defaultCustomResolution() {
  return "";
}

function activeGenerationClarity() {
  return state.operation.generation_clarity || defaultGenerationClarity();
}

function activeGenerationResolution() {
  return activeGenerationClarity();
}

function parseGenerationCount(value) {
  const text = String(value ?? "").trim();
  return /^[1-9][0-9]*$/.test(text) ? Number(text) : null;
}

function normalizeGenerationCount(value) {
  return parseGenerationCount(value) || DEFAULT_GENERATION_COUNT;
}

function defaultGenerationCount() {
  return normalizeGenerationCount(state.settings?.default_count);
}


Object.assign(globalThis, {
  PROVIDER_ADAPTER_MARKERS,
  ADAPTER_CAPABILITIES,
  AVAILABLE_PROVIDER_ADAPTERS,
  normalizeProviderAdapter,
  providerCapability,
  providerCallMethodCapability,
  isProviderImplemented,
  providerUnavailableMessage,
  activeProviderName,
  activeProvider,
  firstProviderName,
  settingsEditingProviderName,
  settingsEditingProvider,
  providerFieldDefaults,
  blankProviderFieldDefaults,
  isImageToImageMode,
  providerAdapterMarker,
  providerDisplayNameWithAdapter,
  providerSortLabel,
  sortedProviderEntries,
  sortedProviderNames,
  providerFilterOptionEntries,
  activeProviderDisplayName,
  providerDisplayName,
  providerOptionsSelect,
  instanceProviderText,
  providerMarkerState,
  providerMarkerLabel,
  renderProviderMarkerBadge,
  closeOperationProviderDropdown,
  toggleProviderMarker,
  renderOperationProviderSelect,
  currentSaveLayout,
  saveLayoutClass,
  shouldShowOperationInputImages,
  isValidGenerationSize,
  isPresetClarity,
  isPresetResolution,
  defaultGenerationClarity,
  isCustomResolutionMode,
  aspectRatioForSize,
  sizeForAspectRatio,
  defaultAspectRatio,
  customGenerationSizes,
  defaultGenerationSize,
  displaySizeLabel,
  displayAspectRatioOption,
  displayCustomSizeOption,
  displayAspectRatioButtonText,
  defaultGenerationResolution,
  isValidGenerationResolution,
  defaultCustomResolution,
  activeGenerationClarity,
  activeGenerationResolution,
  parseGenerationCount,
  normalizeGenerationCount,
  defaultGenerationCount,
});
