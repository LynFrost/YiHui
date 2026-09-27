function cloneSettings() {
  return JSON.parse(JSON.stringify(state.settings || {}));
}

function updateProviderCodeMap(existingMap, formData, fieldName, callMethod, exampleMode) {
  const nextMap = JSON.parse(JSON.stringify(existingMap || {}));
  if (!formData.has(fieldName)) {
    return nextMap;
  }
  nextMap[callMethod] = nextMap[callMethod] || {};
  nextMap[callMethod][exampleMode] = String(formData.get(fieldName) || "");
  return nextMap;
}

function providerAdapterFromForm(formData, existingProvider = {}) {
  return String(formData.get("adapter") || existingProvider.adapter || "openai").trim() || "openai";
}

function providerCodeMethodFromForm(formData, existingProvider = {}) {
  const adapter = providerAdapterFromForm(formData, existingProvider);
  if (["openai-google", "sysrv-google", "apimart-openai"].includes(adapter)) {
    return adapter;
  }
  return formData.get("openai_call_method")
    || existingProvider.openai_call_method
    || "gpt-image-2";
}

function adapterDefaultedConnectionValue(adapter, field, value) {
  const cleanValue = String(value || "").trim();
  if (adapter === "sysrv-google") {
    if (field === "api_key_env" && (!cleanValue || cleanValue === "IMG_API_KEY")) {
      return "SYSRV_GOOGLE_API_KEY";
    }
    if (field === "model" && (!cleanValue || cleanValue === "gpt-image-2")) {
      return "gemini-3.1-flash-image-preview";
    }
    return cleanValue;
  }
  if (adapter === "apimart-openai") {
    if (field === "base_url" && (!cleanValue || cleanValue === "https://img.aiapis.help/v1")) {
      return "https://api.apimart.ai/v1";
    }
    if (field === "api_key_env" && (!cleanValue || cleanValue === "IMG_API_KEY")) {
      return "APIMART_API_KEY";
    }
    return cleanValue;
  }
  if (adapter !== "openai-google") {
    return cleanValue;
  }
  if (field === "base_url" && (!cleanValue || cleanValue === "https://img.aiapis.help/v1")) {
    return "https://www.xiaoyunapi.com/v1";
  }
  if (field === "api_key_env" && (!cleanValue || cleanValue === "IMG_API_KEY")) {
    return "XIAOYUN_API_KEY";
  }
  if (field === "model" && (!cleanValue || cleanValue === "gpt-image-2")) {
    return "gemini-3.1-flash-image-preview";
  }
  return cleanValue;
}

function googleFormOptionalValue(formData, fieldName) {
  const value = String(formData.get(fieldName) || "").trim();
  return value.toLowerCase() === "none" ? "" : value;
}

function googleProviderFormValues(formData, existingProvider = {}) {
  return {
    google_role: formData.get("google_role") || existingProvider.google_role || "user",
    google_max_tokens: formData.get("google_max_tokens")
      || existingProvider.google_max_tokens
      || 4096,
    google_temperature: googleFormOptionalValue(formData, "google_temperature"),
    google_top_p: googleFormOptionalValue(formData, "google_top_p"),
    google_stream: formData.get("google_stream") === "on",
    google_stop: googleFormOptionalValue(formData, "google_stop"),
    google_presence_penalty: googleFormOptionalValue(formData, "google_presence_penalty"),
    google_frequency_penalty: googleFormOptionalValue(formData, "google_frequency_penalty"),
    google_logit_bias: googleFormOptionalValue(formData, "google_logit_bias"),
    google_user: googleFormOptionalValue(formData, "google_user"),
    google_response_format: googleFormOptionalValue(formData, "google_response_format"),
    google_seen: googleFormOptionalValue(formData, "google_seen"),
    google_tools: googleFormOptionalValue(formData, "google_tools"),
    google_tool_choice: googleFormOptionalValue(formData, "google_tool_choice"),
  };
}

function numericProviderFormValue(formData, fieldName, existingProvider = {}, fallback = "") {
  const value = String(formData.get(fieldName) || "").trim();
  return value || existingProvider[fieldName] || fallback;
}

function sharedScriptProviderFormValues(formData, existingProvider = {}) {
  return {
    request_timeout_seconds: numericProviderFormValue(formData, "request_timeout_seconds", existingProvider, 300),
    download_timeout_seconds: numericProviderFormValue(formData, "download_timeout_seconds", existingProvider, 120),
    max_retry_attempts: numericProviderFormValue(formData, "max_retry_attempts", existingProvider, 5),
    apimart_task_timeout_seconds: numericProviderFormValue(formData, "apimart_task_timeout_seconds", existingProvider, 420),
    apimart_task_poll_interval_seconds: numericProviderFormValue(formData, "apimart_task_poll_interval_seconds", existingProvider, 5),
    input_fidelity: googleFormOptionalValue(formData, "input_fidelity"),
    mask_path: googleFormOptionalValue(formData, "mask_path"),
  };
}

async function chooseDefaultDir() {
  const form = document.querySelector("[data-settings-form]");
  const input = form?.elements.default_output_dir;
  if (!input) {
    return;
  }

  try {
    setMessage("");
    const data = await api("/api/dialogs/directory", {
      method: "POST",
      body: { initial_dir: input.value },
    });
    if (data.path) {
      input.value = data.path;
    }
  } catch (error) {
    if (state.page === "settings") {
      setMessage(error.message, "error");
    }
  }
}

function syncOperationFromDom() {
  normalizeOperation();

  const form = document.querySelector("[data-operation-form]");
  if (!form) {
    return;
  }

  state.operation.prompt = form.elements.prompt?.value || "";
  state.operation.generation_path = form.elements.generation_path?.value || "";
  state.operation.generation_clarity = state.operation.generation_clarity || defaultGenerationClarity();
  state.operation.resolution = state.operation.generation_clarity;
  state.operation.custom_resolution = "";
  state.operation.mode = state.operation.input_image_paths.length ? "image_to_image" : "text_to_image";
  state.operation.generation_count = form.elements.generation_count?.value
    || state.operation.generation_count
    || DEFAULT_GENERATION_COUNT;
  state.operation.text_generation_count = state.operation.generation_count;
  state.operation.tag_draft = form.elements.tag_draft?.value || "";
  state.operation.custom_generation_size = form.elements.custom_generation_size?.value
    || state.operation.custom_generation_size
    || state.operation.generation_size;
}

async function saveGenerationDefaults(updates = {}) {
  if (!state.settings) {
    return;
  }
  const nextSettings = cloneSettings();
  if (Object.prototype.hasOwnProperty.call(updates, "aspectRatio")) {
    nextSettings.default_aspect_ratio = updates.aspectRatio;
  }
  if (Object.prototype.hasOwnProperty.call(updates, "clarity")) {
    nextSettings.default_clarity = updates.clarity;
    nextSettings.default_resolution = updates.clarity;
  }
  if (Object.prototype.hasOwnProperty.call(updates, "size")) {
    nextSettings.default_size = updates.size;
  }
  if (Object.prototype.hasOwnProperty.call(updates, "customSizes")) {
    nextSettings.custom_generation_sizes = updates.customSizes;
  }
  nextSettings.default_aspect_ratio = nextSettings.default_aspect_ratio || "1:1";
  nextSettings.default_clarity = nextSettings.default_clarity || nextSettings.default_resolution || "1K";
  nextSettings.default_resolution = nextSettings.default_clarity;
  nextSettings.default_custom_resolution = "";
  if (nextSettings.providers && typeof nextSettings.providers === "object") {
    for (const provider of Object.values(nextSettings.providers)) {
      if (provider && typeof provider === "object") {
        delete provider.default_size;
      }
    }
  }
  const data = await api("/api/settings", {
    method: "PUT",
    body: nextSettings,
  });
  state.settings = data.settings;
}

async function saveDefaultSize(size) {
  await saveGenerationDefaults({
    aspectRatio: state.operation.aspect_ratio,
    clarity: state.operation.generation_clarity,
    size,
  });
}

async function saveDefaultResolution(resolution, customResolution = state.operation.custom_resolution) {
  await saveGenerationDefaults({
    aspectRatio: state.operation.aspect_ratio,
    clarity: resolution,
    size: state.operation.generation_size,
  });
}

async function saveDefaultCount(count) {
  if (!state.settings) {
    return;
  }
  const nextSettings = cloneSettings();
  nextSettings.default_count = count;
  const data = await api("/api/settings", {
    method: "PUT",
    body: nextSettings,
  });
  state.settings = data.settings;
}

async function saveDefaultOutputDir(path) {
  if (!state.settings) {
    return;
  }
  const nextSettings = cloneSettings();
  nextSettings.default_output_dir = path || "";
  const data = await api("/api/settings", {
    method: "PUT",
    body: nextSettings,
  });
  state.settings = data.settings;
}

async function loadSharedScriptExamples() {
  const sharedData = await api("/api/shared-script-examples");
  state.openaiScriptExamples = {
    text_to_image: sharedData.openai?.text_to_image || "",
    image_to_image: sharedData.openai?.image_to_image || "",
  };
  state.openaiGoogleScriptExamples = {
    text_to_image: sharedData["openai-google"]?.text_to_image || "",
    image_to_image: sharedData["openai-google"]?.image_to_image || "",
  };
  state.sysrvGoogleScriptExamples = {
    text_to_image: sharedData["sysrv-google"]?.text_to_image || "",
    image_to_image: sharedData["sysrv-google"]?.image_to_image || "",
  };
  state.apimartOpenAIScriptExamples = {
    text_to_image: sharedData["apimart-openai"]?.text_to_image || "",
    image_to_image: sharedData["apimart-openai"]?.image_to_image || "",
  };
}

async function loadOpenAIScriptExamples() {
  try {
    await loadSharedScriptExamples();
    return;
  } catch (error) {
    // Older servers may not expose the consolidated endpoint during local upgrades.
  }
  const data = await api("/api/openai-script-examples");
  const googleData = await api("/api/openai-google-script-examples");
  state.openaiScriptExamples = {
    text_to_image: data.text_to_image || "",
    image_to_image: data.image_to_image || "",
  };
  state.openaiGoogleScriptExamples = {
    text_to_image: googleData.text_to_image || "",
    image_to_image: googleData.image_to_image || "",
  };
}

function nextProviderKey(providers) {
  let index = 1;
  const prefix = "provider_";
  let key = `${prefix}${String(index).padStart(4, "0")}`;
  while (Object.prototype.hasOwnProperty.call(providers, key)) {
    index += 1;
    key = `${prefix}${String(index).padStart(4, "0")}`;
  }
  return key;
}

function updateSettingsDirtyButtons(isDirty) {
  const buttons = document.querySelectorAll('[form="settings-form"][data-settings-dirty]');
  for (const button of buttons) {
    button.dataset.settingsDirty = isDirty ? "true" : "false";
    button.disabled = !isDirty;
  }
}

function markSettingsDirty() {
  state.settingsDirty = true;
  updateSettingsDirtyButtons(true);
}

function clearSettingsDirty() {
  state.settingsDirty = false;
  updateSettingsDirtyButtons(false);
}

function createProviderDraft() {
  if (!state.settings) {
    return;
  }
  const nextSettings = cloneSettings();
  nextSettings.providers = nextSettings.providers || {};
  const key = nextProviderKey(nextSettings.providers);
  nextSettings.providers[key] = {
    ...blankProviderFieldDefaults(),
    display_name: "",
    base_url: "",
    api_key: "",
    api_key_env: "",
    model: "",
    user_agent: "",
    proxy_url: "",
  };
  state.settings = nextSettings;
  state.settingsEditingProvider = key;
  state.settingsProviderDraftIsNew = true;
  markSettingsDirty();
  renderSettings();
  document.querySelector('[name="display_name"]')?.focus();
}

function copyProviderDraft() {
  if (!state.settings) {
    return;
  }
  const currentProviderName = settingsEditingProviderName();
  const currentProvider = settingsEditingProvider();
  if (!currentProviderName || !currentProvider) {
    setMessage("未选择 provider", "error");
    return;
  }
  const form = currentSettingsForm();
  if (form) {
    syncSettingsProviderDraftFromForm(form);
  }
  const refreshedProvider = settingsEditingProvider();
  const nextSettings = cloneSettings();
  nextSettings.providers = nextSettings.providers || {};
  const key = nextProviderKey(nextSettings.providers);
  const copiedProvider = JSON.parse(JSON.stringify(currentProvider));
  Object.assign(copiedProvider, JSON.parse(JSON.stringify(refreshedProvider || {})));
  const copiedName = String(copiedProvider.display_name || "").trim();
  copiedProvider.display_name = copiedName ? `${copiedName} 副本` : "";
  nextSettings.providers[key] = copiedProvider;
  state.settings = nextSettings;
  state.settingsEditingProvider = key;
  state.settingsProviderDraftIsNew = true;
  markSettingsDirty();
  renderSettings();
  document.querySelector('[name="display_name"]')?.focus();
}

async function cancelSettingsChanges() {
  if (!state.settingsDirty) {
    return;
  }
  try {
    setMessage("");
    const previousProvider = settingsEditingProviderName();
    const data = await api("/api/settings");
    state.settings = data.settings;
    const providers = state.settings?.providers || {};
    state.settingsEditingProvider = Object.prototype.hasOwnProperty.call(providers, previousProvider)
      ? previousProvider
      : activeProviderName() || firstProviderName();
    state.settingsProviderDraftIsNew = false;
    clearSettingsDirty();
    if (renderSettingsIfActive()) {
      setMessage("已取消未保存修改", "info");
    }
  } catch (error) {
    if (state.page === "settings") {
      setMessage(error.message, "error");
    }
  }
}

async function deleteProvider() {
  if (!state.settings) {
    return;
  }
  const providerName = settingsEditingProviderName();
  if (!providerName) {
    setMessage("未选择 provider", "error");
    return;
  }
  if (providerName === activeProviderName()) {
    setMessage("当前 Provider 正在操作区使用，请先到生图管理页切换 Provider 后再删除。", "error");
    return;
  }
  const confirmed = window.confirm("确认删除这个 Provider？\n这只会删除配置，不会修改历史实例和图片文件。");
  if (!confirmed) {
    return;
  }

  const nextSettings = cloneSettings();
  nextSettings.providers = nextSettings.providers || {};
  delete nextSettings.providers[providerName];
  if (
    nextSettings.active_provider
    && !Object.prototype.hasOwnProperty.call(nextSettings.providers, nextSettings.active_provider)
  ) {
    nextSettings.active_provider = Object.keys(nextSettings.providers)[0] || "";
  }
  const nextEditingProvider = Object.keys(nextSettings.providers)[0] || "";

  try {
    setMessage("");
    const data = await api("/api/settings", {
      method: "PUT",
      body: nextSettings,
    });
    state.settings = data.settings;
    state.settingsEditingProvider = nextEditingProvider;
    state.settingsProviderDraftIsNew = false;
    if (renderSettingsIfActive()) {
      setMessage("已删除 Provider", "success");
    }
  } catch (error) {
    if (state.page === "settings") {
      setMessage(error.message, "error");
    }
  }
}

function currentSettingsForm() {
  return document.querySelector("[data-settings-form]");
}

function showCodeExampleTab(tab) {
  const form = currentSettingsForm();
  syncSettingsProviderDraftFromForm(form);
  state.settingsCodeExample.tab = tab === "param-intro"
    ? "param-intro"
    : tab === "custom-code"
      ? "custom-code"
      : "fixed-example";
  state.settingsCodeExample.customTabExplicit = state.settingsCodeExample.tab === "custom-code";
  state.settingsCodeExample.editDraft = "";
  if (state.settingsCodeExample.tab === "custom-code") {
    const provider = settingsEditingProvider();
    state.settingsCodeExample.customEditOrigin = form?.querySelector('[name="custom_script"]')?.value
      || customScriptCode(provider, openAICallMethod(provider), openAIExampleMode(provider));
  }
  renderSettingsIfActive();
}

function editCodeExample() {
  const form = currentSettingsForm();
  form?.querySelector('[name="custom_script"]')?.focus();
}

async function saveCodeExample() {
  const form = currentSettingsForm();
  if (!form) {
    return;
  }
  syncSettingsProviderDraftFromForm(form);
  await saveSettings(form);
}

function cancelCodeExample() {
  const form = currentSettingsForm();
  const textarea = form?.querySelector('[name="custom_script"]');
  if (textarea) {
    textarea.value = state.settingsCodeExample.customEditOrigin || "";
    syncSettingsProviderDraftFromForm(form);
  }
  renderSettingsIfActive();
}

async function copyTextToClipboard(text) {
  let copied = false;
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch (error) {
      copied = false;
    }
  }
  if (!copied) {
    fallbackCopyText(text);
  }
}

async function copyCodeExample(target) {
  const form = currentSettingsForm();
  const activeTarget = target || state.settingsCodeExample.tab;
  const selector = activeTarget === "param-intro"
    ? '[name="param_intro"]'
    : activeTarget === "custom-code"
      ? '[name="custom_script"]'
      : '[data-code-panel="fixed-example"] textarea';
  const code = form?.querySelector(selector)?.value || "";
  try {
    await copyTextToClipboard(code);
    setMessage("已复制代码", "success");
  } catch (error) {
    setMessage(`复制失败：${error.message}`, "error");
  }
}

async function saveCustomScript() {
  const form = currentSettingsForm();
  if (!form) {
    return;
  }
  syncSettingsProviderDraftFromForm(form);
  await saveSettings(form);
}

async function clearCustomScript() {
  const form = currentSettingsForm();
  const textarea = form?.querySelector('[name="custom_script"]');
  if (!form || !textarea) {
    return;
  }
  textarea.value = "";
  syncSettingsProviderDraftFromForm(form);
  state.settingsCodeExample.tab = "fixed-example";
  state.settingsCodeExample.customTabExplicit = false;
  await saveSettings(form);
}

async function saveLayoutPreference(layout) {
  if (!state.settings) {
    return;
  }
  const nextLayout = layout === "single" ? "single" : "double";
  const nextSettings = cloneSettings();
  nextSettings.save_layout = nextLayout;
  const data = await api("/api/settings", {
    method: "PUT",
    body: nextSettings,
  });
  state.settings = data.settings;
}

async function setGenerationSize(size) {
  if (isActiveOpenAIGoogleProvider()) {
    return;
  }
  return setCustomGenerationSize(size);
}

async function setAspectRatio(aspectRatio) {
  if (isActiveOpenAIGoogleProvider()) {
    return;
  }
  syncOperationFromDom();
  const nextAspectRatio = String(aspectRatio || "").trim();
  if (!ASPECT_RATIO_PRESETS.includes(nextAspectRatio)) {
    setMessage("分辨率只能选择已有宽高比", "error");
    return;
  }

  state.operation.aspect_ratio = nextAspectRatio;
  if (isPresetClarity(state.operation.generation_clarity)) {
    state.operation.generation_size = sizeForAspectRatio(
      nextAspectRatio,
      state.operation.generation_clarity,
    );
    state.operation.custom_generation_size = state.operation.generation_size;
  }
  state.operation.size_error = "";
  state.operation.aspect_ratio_picker_open = false;
  state.operation.clarity_picker_open = false;
  state.operation.size_picker_open = false;
  state.operation.resolution_picker_open = false;
  persistUiState();
  renderManager();

  try {
    await saveGenerationDefaults({
      aspectRatio: state.operation.aspect_ratio,
      clarity: state.operation.generation_clarity,
      size: state.operation.generation_size,
    });
  } catch (error) {
    if (state.page === "manager") {
      setMessage(`分辨率已用于当前页面，但保存默认值失败：${error.message}`, "error");
    }
  }
}

async function setCustomGenerationSize(size) {
  if (isActiveOpenAIGoogleProvider()) {
    return;
  }
  syncOperationFromDom();
  const nextSize = String(size || "").trim();
  if (!isValidGenerationSize(nextSize)) {
    state.operation.size_error = "尺寸格式必须是数字x数字";
    state.operation.aspect_ratio_picker_open = true;
    state.operation.size_picker_open = true;
    renderManager();
    return;
  }

  state.operation.generation_clarity = "custom";
  state.operation.resolution = "custom";
  state.operation.generation_size = nextSize;
  state.operation.custom_generation_size = nextSize;
  state.operation.size_error = "";
  state.operation.aspect_ratio_picker_open = false;
  state.operation.clarity_picker_open = false;
  state.operation.size_picker_open = false;
  state.operation.resolution_picker_open = false;
  const customSizes = addCustomGenerationSize(nextSize);
  persistUiState();
  renderManager();

  try {
    await saveGenerationDefaults({
      aspectRatio: state.operation.aspect_ratio,
      clarity: "custom",
      size: nextSize,
      customSizes,
    });
  } catch (error) {
    if (state.page === "manager") {
      setMessage(`尺寸已用于当前页面，但保存默认值失败：${error.message}`, "error");
    }
  }
}

async function setGenerationResolution(resolution) {
  if (isActiveOpenAIGoogleProvider()) {
    return;
  }
  return setGenerationClarity(resolution);
}

async function setGenerationClarity(clarity) {
  if (isActiveOpenAIGoogleProvider()) {
    return;
  }
  syncOperationFromDom();
  const nextClarity = String(clarity || "").trim();
  if (!isValidGenerationResolution(nextClarity)) {
    setMessage("清晰度只能是 1K、2K、4K 或自定义", "error");
    return;
  }

  state.operation.generation_clarity = nextClarity;
  state.operation.resolution = nextClarity;
  if (isPresetClarity(nextClarity)) {
    const nextSize = sizeForAspectRatio(state.operation.aspect_ratio, nextClarity);
    state.operation.generation_size = nextSize || DEFAULT_GENERATION_SIZE;
    state.operation.custom_generation_size = state.operation.generation_size;
    state.operation.aspect_ratio_picker_open = false;
  } else {
    const customSizes = customGenerationSizes();
    const nextSize = isValidGenerationSize(state.operation.custom_generation_size)
      ? state.operation.custom_generation_size
      : customSizes[0] || state.operation.generation_size || DEFAULT_GENERATION_SIZE;
    state.operation.generation_size = nextSize;
    state.operation.custom_generation_size = nextSize;
    state.operation.aspect_ratio_picker_open = true;
  }
  state.operation.clarity_picker_open = false;
  state.operation.size_picker_open = false;
  state.operation.resolution_picker_open = false;
  state.operation.size_error = "";
  persistUiState();
  renderManager();
  try {
    await saveGenerationDefaults({
      aspectRatio: state.operation.aspect_ratio,
      clarity: nextClarity,
      size: state.operation.generation_size,
    });
  } catch (error) {
    if (state.page === "manager") {
      setMessage(`清晰度已用于当前页面，但保存默认值失败：${error.message}`, "error");
    }
  }
}

function addCustomGenerationSize(size) {
  const cleanSize = String(size || "").trim();
  const sizes = customGenerationSizes();
  if (isValidGenerationSize(cleanSize) && !sizes.includes(cleanSize)) {
    sizes.push(cleanSize);
  }
  if (state.settings) {
    state.settings.custom_generation_sizes = sizes;
  }
  return sizes;
}

async function removeCustomGenerationSize(size) {
  syncOperationFromDom();
  const removeSize = String(size || "").trim();
  const customSizes = customGenerationSizes().filter((customSize) => customSize !== removeSize);
  if (state.settings) {
    state.settings.custom_generation_sizes = customSizes;
  }
  if (state.operation.generation_clarity === "custom" && state.operation.generation_size === removeSize) {
    state.operation.aspect_ratio = "1:1";
    state.operation.generation_clarity = "1K";
    state.operation.resolution = "1K";
    state.operation.generation_size = "1024x1024";
    state.operation.custom_generation_size = "";
    state.operation.aspect_ratio_picker_open = false;
  } else {
    state.operation.aspect_ratio_picker_open = true;
  }
  state.operation.size_error = "";
  persistUiState();
  renderManager();
  try {
    await saveGenerationDefaults({
      aspectRatio: state.operation.aspect_ratio,
      clarity: state.operation.generation_clarity,
      size: state.operation.generation_size,
      customSizes,
    });
  } catch (error) {
    if (state.page === "manager") {
      setMessage(`自定义尺寸已删除，但保存默认值失败：${error.message}`, "error");
    }
  }
}

function toggleAspectRatioPicker() {
  syncOperationFromDom();
  state.operation.aspect_ratio_picker_open = !state.operation.aspect_ratio_picker_open;
  state.operation.size_picker_open = state.operation.aspect_ratio_picker_open;
  state.operation.clarity_picker_open = false;
  state.operation.resolution_picker_open = false;
  state.operation.size_error = "";
  renderManager();
}

function toggleSizePicker() {
  toggleAspectRatioPicker();
}

function toggleClarityPicker() {
  syncOperationFromDom();
  state.operation.clarity_picker_open = !state.operation.clarity_picker_open;
  state.operation.resolution_picker_open = state.operation.clarity_picker_open;
  state.operation.aspect_ratio_picker_open = false;
  state.operation.size_picker_open = false;
  state.operation.size_error = "";
  renderManager();
}

function toggleResolutionPicker() {
  toggleClarityPicker();
}


async function saveSettings(form) {
  if (!state.settings) {
    return;
  }

  syncSettingsProviderDraftFromForm(form);
  const formData = new FormData(form);
  const providerName = String(formData.get("provider") || settingsEditingProviderName() || "").trim();
  const providerKey = String(formData.get("provider_key") || providerName || "").trim();
  if (!providerName) {
    setMessage("请先新建或选择 provider", "error");
    return;
  }
  if (!providerKey) {
    setMessage("provider key 不能为空", "error");
    return;
  }

  const nextSettings = cloneSettings();
  nextSettings.providers = nextSettings.providers || {};
  if (
    state.settingsProviderDraftIsNew
    && providerKey !== providerName
    && Object.prototype.hasOwnProperty.call(nextSettings.providers, providerKey)
  ) {
    setMessage("provider key 已存在", "error");
    return;
  }

  if (!state.settingsProviderDraftIsNew && providerKey !== providerName) {
    setMessage("已保存 provider 的 key 不能直接修改，请新建后删除旧 Provider", "error");
    return;
  }

  if (state.settingsProviderDraftIsNew && providerKey !== providerName) {
    nextSettings.providers[providerKey] = nextSettings.providers[providerName] || providerFieldDefaults();
    delete nextSettings.providers[providerName];
  }

  const existingProvider = nextSettings.providers[providerKey] || {};
  const providerAdapter = providerAdapterFromForm(formData, existingProvider);
  const providerCallMethod = formData.get("openai_call_method")
    || existingProvider.openai_call_method
    || "gpt-image-2";
  const providerCodeMethod = providerCodeMethodFromForm(formData, existingProvider);
  const providerExampleMode = formData.get("openai_example_mode")
    || existingProvider.openai_example_mode
    || "text_to_image";
  const customScripts = updateProviderCodeMap(
    existingProvider.custom_scripts,
    formData,
    "custom_script",
    providerCodeMethod,
    providerExampleMode,
  );
  nextSettings.providers[providerKey] = {
    ...existingProvider,
    display_name: formData.get("display_name") || "",
    adapter: providerAdapter,
    base_url: adapterDefaultedConnectionValue(providerAdapter, "base_url", formData.get("base_url")),
    api_key: formData.get("api_key") || "",
    api_key_env: adapterDefaultedConnectionValue(providerAdapter, "api_key_env", formData.get("api_key_env")),
    user_agent: formData.get("user_agent") || "",
    model: adapterDefaultedConnectionValue(
      providerAdapter,
      "model",
      formData.has("model") ? formData.get("model") : existingProvider.model || "",
    ),
    proxy_mode: formData.get("proxy_mode") || "system",
    proxy_url: formData.get("proxy_url") || "",
    allow_untrusted_proxy_certificate: formData.get("allow_untrusted_proxy_certificate") === "on",
    openai_call_method: providerCallMethod,
    openai_example_mode: providerExampleMode,
    quality: formData.get("quality") || existingProvider.quality || "high",
    output_format: formData.get("output_format") || existingProvider.output_format || "png",
    output_compression: formData.get("output_compression")
      || existingProvider.output_compression
      || 80,
    background: formData.get("background") || existingProvider.background || "auto",
    moderation: formData.get("moderation") || existingProvider.moderation || "low",
    user: formData.get("user") || "",
    ...googleProviderFormValues(formData, existingProvider),
    ...sharedScriptProviderFormValues(formData, existingProvider),
    code_examples: JSON.parse(JSON.stringify(existingProvider.code_examples || {})),
    custom_scripts: customScripts,
  };
  for (const provider of Object.values(nextSettings.providers)) {
    if (provider && typeof provider === "object") {
      delete provider.default_size;
    }
  }

  try {
    setMessage("");
    const data = await api("/api/settings", {
      method: "PUT",
      body: nextSettings,
    });
    state.settings = data.settings;
    state.settingsEditingProvider = providerKey;
    state.settingsProviderDraftIsNew = false;
    clearSettingsDirty();
    if (renderSettingsIfActive()) {
      setMessage("已保存", "success");
    }
  } catch (error) {
    if (state.page === "settings") {
      setMessage(error.message, "error");
    }
  }
}

async function changeOperationProvider(providerKey) {
  const nextProvider = String(providerKey || "").trim();
  if (!state.settings) {
    return;
  }
  if (!nextProvider || !state.settings.providers?.[nextProvider]) {
    setMessage("请选择有效 Provider", "error");
    renderManagerIfActive();
    return;
  }
  const previousProvider = state.settings.active_provider || "";
  if (nextProvider === previousProvider) {
    return;
  }

  state.settings.active_provider = nextProvider;
  renderManagerIfActive();

  try {
    const nextSettings = cloneSettings();
    nextSettings.active_provider = nextProvider;
    const data = await api("/api/settings", {
      method: "PUT",
      body: nextSettings,
    });
    state.settings = data.settings;
    if (renderManagerIfActive()) {
      setMessage("已切换 Provider", "success");
    }
    renderSettingsIfActive();
  } catch (error) {
    state.settings.active_provider = previousProvider;
    if (renderManagerIfActive()) {
      setMessage(error.message, "error");
    } else {
      setMessage(error.message, "error");
    }
  }
}

function syncSettingsProviderDraftFromForm(form, options = {}) {
  if (!state.settings || !form) {
    return;
  }
  const formData = new FormData(form);
  const providerName = String(formData.get("provider") || settingsEditingProviderName() || "").trim();
  const providerKey = String(formData.get("provider_key") || providerName || "").trim();
  if (!providerKey) {
    return;
  }
  state.settings.providers = state.settings.providers || {};
  if (
    state.settingsProviderDraftIsNew
    && providerKey !== providerName
    && !Object.prototype.hasOwnProperty.call(state.settings.providers, providerKey)
  ) {
    state.settings.providers[providerKey] = state.settings.providers[providerName] || providerFieldDefaults();
    delete state.settings.providers[providerName];
  }
  state.settingsEditingProvider = providerKey;
  const existingProvider = state.settings.providers[providerKey] || {};
  const providerAdapter = providerAdapterFromForm(formData, existingProvider);
  const providerCallMethod = formData.get("openai_call_method")
    || existingProvider.openai_call_method
    || "gpt-image-2";
  const providerCodeMethod = providerCodeMethodFromForm(formData, existingProvider);
  const providerExampleMode = formData.get("openai_example_mode")
    || existingProvider.openai_example_mode
    || "text_to_image";
  const customScripts = updateProviderCodeMap(
    existingProvider.custom_scripts,
    formData,
    "custom_script",
    providerCodeMethod,
    providerExampleMode,
  );
  state.settings.providers[providerKey] = {
    ...existingProvider,
    display_name: formData.get("display_name") || "",
    adapter: providerAdapter,
    base_url: adapterDefaultedConnectionValue(providerAdapter, "base_url", formData.get("base_url")),
    api_key: formData.get("api_key") || "",
    api_key_env: adapterDefaultedConnectionValue(providerAdapter, "api_key_env", formData.get("api_key_env")),
    user_agent: formData.get("user_agent") || "",
    model: adapterDefaultedConnectionValue(
      providerAdapter,
      "model",
      formData.has("model") ? formData.get("model") : existingProvider.model || "",
    ),
    proxy_mode: formData.get("proxy_mode") || "system",
    proxy_url: formData.get("proxy_url") || "",
    allow_untrusted_proxy_certificate: formData.get("allow_untrusted_proxy_certificate") === "on",
    openai_call_method: providerCallMethod,
    openai_example_mode: providerExampleMode,
    quality: formData.get("quality") || "high",
    output_format: formData.get("output_format") || "png",
    output_compression: formData.get("output_compression")
      || state.settings.providers[providerKey]?.output_compression
      || 80,
    background: formData.get("background") || "auto",
    moderation: formData.get("moderation") || "low",
    user: formData.get("user") || "",
    ...googleProviderFormValues(formData, existingProvider),
    ...sharedScriptProviderFormValues(formData, existingProvider),
    code_examples: JSON.parse(JSON.stringify(existingProvider.code_examples || {})),
    custom_scripts: customScripts,
  };
}


Object.assign(globalThis, {
  cloneSettings,
  updateProviderCodeMap,
  providerAdapterFromForm,
  providerCodeMethodFromForm,
  adapterDefaultedConnectionValue,
  googleProviderFormValues,
  sharedScriptProviderFormValues,
  loadSharedScriptExamples,
  chooseDefaultDir,
  syncOperationFromDom,
  saveGenerationDefaults,
  saveDefaultSize,
  saveDefaultResolution,
  saveDefaultCount,
  saveDefaultOutputDir,
  loadOpenAIScriptExamples,
  nextProviderKey,
  markSettingsDirty,
  clearSettingsDirty,
  createProviderDraft,
  copyProviderDraft,
  cancelSettingsChanges,
  deleteProvider,
  currentSettingsForm,
  showCodeExampleTab,
  editCodeExample,
  saveCodeExample,
  cancelCodeExample,
  copyTextToClipboard,
  copyCodeExample,
  saveCustomScript,
  clearCustomScript,
  saveLayoutPreference,
  setGenerationSize,
  setAspectRatio,
  setCustomGenerationSize,
  setGenerationResolution,
  setGenerationClarity,
  addCustomGenerationSize,
  removeCustomGenerationSize,
  toggleAspectRatioPicker,
  toggleSizePicker,
  toggleClarityPicker,
  toggleResolutionPicker,
  saveSettings,
  changeOperationProvider,
  syncSettingsProviderDraftFromForm,
});
