function renderSettingSection(title, content, headerControl = "") {
  return `
    <section class="settings-section">
      <div class="section-title-row">
        <h2>${escapeHtml(title)}</h2>
        ${headerControl ? `<div class="settings-section-control">${headerControl}</div>` : ""}
      </div>
      ${content}
    </section>
  `;
}

function renderParamNote(text) {
  return `<span class="param-note">${escapeHtml(text)}</span>`;
}

function settingsProviderConfigFieldValues(field) {
  if (!["api_key_env", "model", "user_agent"].includes(field)) {
    return [];
  }
  const providers = state.settings?.providers || {};
  return cleanStringArray(
    Object.values(providers)
      .map((provider) => provider?.[field] || ""),
  );
}

function providerFieldHistoryValues(field) {
  return [
    ...(state.settingsSharedProviderFieldHistory?.[field] || []),
    ...(state.successfulProviderFieldHistory?.[field] || []),
    ...settingsProviderConfigFieldValues(field),
  ];
}

function settingHistoryValues(field, currentValue = "") {
  const history = providerFieldHistoryValues(field);
  return [...new Set(cleanStringArray([
    currentValue,
    ...history,
  ]))].filter(Boolean);
}

function renderSettingHistoryInput(field, value, options = {}) {
  const historyValues = settingHistoryValues(field, value);
  const isOpen = state.settingHistoryDropdownOpen === field && historyValues.length > 0;
  const label = options.label || field;
  const extraClass = options.className ? ` ${escapeHtml(options.className)}` : "";
  const inputClass = options.inputClass ? ` class="${escapeHtml(options.inputClass)}"` : "";
  const placeholder = options.placeholder ? ` placeholder="${escapeHtml(options.placeholder)}"` : "";
  return `
    <div class="setting-history-combobox${extraClass}" data-setting-history-field="${escapeHtml(field)}">
      <input${inputClass} name="${escapeHtml(field)}" value="${escapeHtml(value || "")}" title="${escapeHtml(value || "")}" autocomplete="off"${placeholder}>
      <button type="button" class="setting-history-toggle" data-action="toggle-setting-history" data-setting-history-field="${escapeHtml(field)}" aria-label="选择${escapeHtml(label)}历史值">▾</button>
      ${
        isOpen
          ? `
            <div class="setting-history-dropdown">
              ${historyValues.map((item) => `
                <button type="button" data-action="select-setting-history" data-setting-history-field="${escapeHtml(field)}" data-setting-history-value="${escapeHtml(item)}" title="${escapeHtml(item)}">
                  ${escapeHtml(item)}
                </button>
              `).join("")}
            </div>
          `
          : ""
      }
    </div>
  `;
}

function renderSoftwareParam(name, value = "来自软件") {
  return `
    <label class="field param-field">
      <span>${escapeHtml(name)}</span>
      <input value="${escapeHtml(value)}" disabled>
    </label>
  `;
}

function openAICallMethod(provider) {
  return provider.openai_call_method === "response" ? "response" : "gpt-image-2";
}

function openAIExampleMode(provider) {
  return provider.openai_example_mode === "image_to_image" ? "image_to_image" : "text_to_image";
}

function providerProxyMode(provider) {
  const mode = String(provider?.proxy_mode || "system").trim();
  return ["system", "custom", "none"].includes(mode) ? mode : "system";
}

function providerCodeValue(provider, group, callMethod, exampleMode) {
  return provider?.[group]?.[callMethod]?.[exampleMode] || "";
}

function defaultCodeExample(callMethod, exampleMode) {
  if (callMethod === "sysrv-google") {
    const script = exampleMode === "image_to_image"
      ? state.sysrvGoogleScriptExamples.image_to_image
      : state.sysrvGoogleScriptExamples.text_to_image;
    return script || "# 正在加载调用示例...";
  }
  if (callMethod === "apimart-openai") {
    const script = exampleMode === "image_to_image"
      ? state.apimartOpenAIScriptExamples.image_to_image
      : state.apimartOpenAIScriptExamples.text_to_image;
    return script || "# 正在加载调用示例...";
  }
  if (callMethod === "openai-google") {
    const script = exampleMode === "image_to_image"
      ? state.openaiGoogleScriptExamples.image_to_image
      : state.openaiGoogleScriptExamples.text_to_image;
    return script || "# 正在加载调用示例...";
  }
  if (callMethod === "response") {
    return exampleMode === "image_to_image"
      ? `# response 图生图示例待完善
# 当前不影响实际生成逻辑。`
      : `# response 文生图示例待完善
# 当前不影响实际生成逻辑。`;
  }

  const script = exampleMode === "image_to_image"
    ? state.openaiScriptExamples.image_to_image
    : state.openaiScriptExamples.text_to_image;
  return script || "# 正在加载调用示例...";
}

function fixedCodeExample(_provider, callMethod, exampleMode) {
  return defaultCodeExample(callMethod, exampleMode);
}

function customScriptCode(provider, callMethod, exampleMode) {
  return providerCodeValue(provider, "custom_scripts", callMethod, exampleMode);
}

function parameterIntroCode(provider, callMethod, exampleMode) {
  const adapter = normalizeProviderAdapter(provider?.adapter);
  const modeLabel = exampleMode === "image_to_image" ? "图生图" : "文生图";
  const lines = [
    `接口类型：${adapter}`,
    `调用方式：${callMethod}`,
    `生图方式：${modeLabel}`,
    "",
    "说明：参数介绍只用于阅读和复制，不会保存到 Provider 配置，也不会作为自定义代码执行。实际可接受范围以接口官网和服务商兼容实现为准。",
    "",
    "格式：参数名 | 含义 | 默认值 | 参数范围 | 一般怎么选",
    "",
    "连接参数",
    "base_url | 接口地址 | 新建 Provider 为空 | 服务商提供的根地址或 /v1 地址 | 按服务商文档填写，OpenAI 兼容接口通常以 /v1 结尾",
    "api_key | 直接密钥 | 空 | 服务商密钥字符串 | 临时或单机使用可直接填写；填写后优先于 api_key_env",
    "api_key_env | 环境变量名 | 新建 Provider 为空 | 系统环境变量名称 | 多电脑或避免明文密钥时使用",
    "model | 模型名称 | 新建 Provider 为空 | 当前服务商支持的模型 | 按服务商后台实际模型名填写",
    "user_agent | 请求 User-Agent | 空 | 任意请求头字符串 | 服务商要求特定 UA 时填写，否则留空",
    "proxy_mode / proxy_url | 代理方式和地址 | system / 空 | system、custom、none | 网络直连失败时再尝试 custom",
    "",
    "软件注入参数",
    "prompt | 操作区提示词 | 操作区输入 | 文本 | 写清主体、动作、风格和限制",
    "output_path | 目标输出路径 | 软件生成 | 本地文件路径 | 由保存路径和实例编号生成，脚本最终写入这里",
    "size | 图片尺寸 | 操作区尺寸 | 例如 1024x1024 或服务商支持尺寸 | 先用 1K 测通，再提高到 2K/4K",
  ];

  if (exampleMode === "image_to_image") {
    lines.push(
      "input_images | 输入图列表 | 操作区上传顺序 | 本地图片路径数组 | 图1、图2按上传顺序传入，可和提示词中的图序对应",
      "image | 单图兼容字段 | input_images 的第一张 | 本地图片路径 | 旧脚本或单图接口可使用",
      "mask | 遮罩图 | 暂不启用 | 本地图片路径或空 | 当前软件不主动提供，通常留空",
    );
  } else {
    lines.push(
      "n | 生成数量 | 操作区数量 | 正整数，图生图固定为 1 | 批量出图时提高，接口不稳定时建议先用 1",
    );
  }

  if (adapter === "openai-google") {
    lines.push(
      "",
      "openai-google 参数",
      "google_role | 消息角色 | user | user、assistant 等兼容角色 | 一般保持 user",
      "google_max_tokens | 最大输出 token | 4096 | 正整数，受服务商限制 | 图片响应较长时可适当提高",
      "google_temperature | 随机性 | 空 | 0 到 2 或服务商兼容值 | 想稳定留空或低值，想发散用较高值",
      "google_top_p | 采样范围 | 空 | 0 到 1 | 通常和 temperature 二选一调",
      "google_stream | 流式响应 | false | 当前固定 false | 当前脚本按完整 JSON 解析图片，不建议修改",
      "google_stop | 停止词 | 空 | 字符串或数组 JSON | 普通生图通常留空",
      "google_presence_penalty / google_frequency_penalty | 惩罚参数 | 空 | 服务商兼容数字 | 普通生图通常留空",
      "google_logit_bias | token 偏置 | 空 | JSON 对象 | 普通生图通常留空",
      "google_user | 用户标识 | 空 | 字符串 | 需要审计或区分用户时填写",
      "google_response_format | 响应格式 | 空 | JSON 字符串 | 服务商明确要求时填写",
      "google_seen / google_tools / google_tool_choice | 扩展兼容字段 | 空 | 服务商兼容格式 | 不确定时留空",
    );
    if (exampleMode === "image_to_image") {
      lines.push("input_images | 图生图输入图 | 操作区上传顺序 | 一张或多张本地图片 | 多图按顺序注入，脚本逐张读取。");
    }
    return lines.join("\n");
  }

  if (adapter === "sysrv-google") {
    lines.push(
      "",
      "sysrv-google 参数",
      "google_role | 消息角色 | user | user、assistant 等兼容角色 | 一般保持 user",
      "request_timeout_seconds | 请求超时秒数 | 300 | 正整数 | 服务商响应慢时提高",
      "download_timeout_seconds | 下载超时秒数 | 120 | 正整数 | 图片 URL 下载慢时提高",
      "max_retry_attempts | 最大尝试次数 | 5 | 正整数 | 服务端波动时适当提高",
    );
    if (exampleMode === "image_to_image") {
      lines.push("input_images | 图生图输入图 | 操作区上传顺序 | 一张或多张本地图片 | 多图按顺序注入。");
    }
    lines.push("尺寸 / 分辨率 / 数量 | 不参与 sysrv-google 请求 | 空 | 当前脚本不读取 | UI 状态保留但不发送。");
    return lines.join("\n");
  }

  if (adapter === "apimart-openai") {
    lines.push(
      "",
      "apimart-openai 参数",
      "quality | 图片质量 | high | low、medium、high、auto | 速度优先选 low/medium，质量优先选 high",
      "output_format | 输出格式 | png | png、jpeg、webp | 透明或无损倾向 png，体积优先 webp/jpeg",
      "output_compression | 压缩质量 | 80 | 0 到 100，png 时不可用 | jpeg/webp 体积过大时降低",
      "background | 背景 | auto | auto、opaque | 不确定保持 auto",
      "request_timeout_seconds | 请求超时秒数 | 300 | 正整数 | 服务商响应慢时提高",
      "download_timeout_seconds | 下载超时秒数 | 120 | 正整数 | 图片 URL 下载慢时提高",
      "max_retry_attempts | 最大尝试次数 | 5 | 正整数 | 服务端波动时适当提高",
      "apimart_task_timeout_seconds | APIMart 任务轮询超时 | 420 | 正整数 | 异步任务等待上限",
      "apimart_task_poll_interval_seconds | APIMart 任务轮询间隔 | 5 | 正整数 | 不宜过低",
    );
    if (exampleMode === "text_to_image") {
      lines.push("moderation | 审核强度 | low | low、auto | 文生图脚本使用。");
    } else {
      lines.push(
        "input_images | 图生图输入图 | 操作区上传顺序 | 一张或多张本地图片 | 多图按顺序注入。",
        "input_fidelity | 输入图保真度 | 空 | high、low、auto 或空 | 当前模型支持时再填写",
        "mask_path | 遮罩图路径 | 空 | 本地图片路径或空 | 当前软件没有遮罩选择入口，通常留空",
      );
    }
    return lines.join("\n");
  }

  if (adapter === "google") {
    return [
      ...lines,
      "",
      "google 接口类型当前暂未接入实际生图参数。",
      "可以保存 Provider 配置，但点击生成时会按未实现接口提示，不会执行生图。",
    ].join("\n");
  }

  if (adapter === "other") {
    return [
      ...lines,
      "",
      "other 接口类型用于后续自定义接口预留。",
      "当前暂未接入实际生图参数，可以保存配置，但不会执行生图。",
    ].join("\n");
  }

  if (callMethod === "response") {
    return [
      ...lines,
      "",
      "OpenAI response 参数",
      "response 调用方式当前示例仍处于待完善状态；文生图参数说明仅作占位参考，图生图当前不作为实际可用路径。",
      "model | 模型名称 | 设置页 model | 支持 Responses 图像能力的模型 | 以服务商实际支持为准",
      "prompt | 输入文本 | 操作区提示词 | 文本 | 先用短提示词测通，再增加复杂描述",
      "size | 输出尺寸 | 操作区尺寸 | 服务商支持尺寸 | 不确定时先用 1K",
    ].join("\n");
  }

  lines.push(
    "",
    "OpenAI gpt-image-2 参数",
    "quality | 图片质量 | high | low、medium、high、auto | 速度优先选 low/medium，质量优先选 high",
    "output_format | 输出格式 | png | png、jpeg、webp | 透明或无损倾向 png，体积优先 webp/jpeg",
    "output_compression | 压缩质量 | 80 | 0 到 100，png 时不可用 | jpeg/webp 体积过大时降低",
    "background | 背景 | auto | auto、opaque，response 可含 transparent | 不确定保持 auto",
    "moderation | 审核强度 | low | low、auto | 普通使用保持 low 或按服务商要求调整",
    "user | 用户标识 | 空 | 字符串 | 需要追踪调用来源时填写",
  );
  if (exampleMode === "image_to_image") {
    lines.push("input_fidelity | 输入图保真度 | high | high、low、auto | 参考图越重要越应保持 high");
  }
  return lines.join("\n");
}

function renderCodeExampleActions(displayCodeTab) {
  if (displayCodeTab === "custom-code") {
    return `
      <div class="code-example-actions">
        <button type="button" class="is-editing" data-action="edit-code-example">编辑</button>
        <button type="button" data-action="save-code-example">保存</button>
        <button type="button" data-action="cancel-code-example">取消</button>
        <button type="button" data-action="copy-code-example" data-code-target="custom-code">复制</button>
        <button type="button" data-action="clear-custom-script">清空自定义代码</button>
      </div>
    `;
  }
  if (displayCodeTab === "param-intro") {
    return `
      <div class="code-example-actions">
        <button type="button" data-action="copy-code-example" data-code-target="param-intro">复制</button>
      </div>
    `;
  }
  return `
    <div class="code-example-actions">
      <button type="button" data-action="copy-code-example" data-code-target="fixed-example">复制</button>
    </div>
  `;
}

function codeExampleRows(code) {
  const lines = String(code || "").split("\n").length;
  return Math.max(10, lines + 1);
}

function renderCodeExampleTabs(provider, callMethod, exampleMode) {
  const customCode = customScriptCode(provider, callMethod, exampleMode);
  const customCodeHasContent = Boolean(String(customCode || "").trim());
  const requestedCodeTab = state.settingsCodeExample.tab === "param-intro"
    ? "param-intro"
    : state.settingsCodeExample.tab === "custom-code"
      ? "custom-code"
      : "fixed-example";
  const displayCodeTab = requestedCodeTab === "param-intro"
    ? "param-intro"
    : requestedCodeTab === "custom-code"
    && (customCodeHasContent || state.settingsCodeExample.customTabExplicit)
      ? "custom-code"
      : "fixed-example";
  const fixedStoredCode = fixedCodeExample(provider, callMethod, exampleMode);
  const fixedCode = fixedStoredCode;
  const paramIntro = parameterIntroCode(provider, callMethod, exampleMode);
  const customWarning = String(customCode || "").trim()
    ? `<div class="custom-script-warning">当前自定义代码已启用，生成将使用自定义代码。</div>`
    : "";
  const visibleCode = displayCodeTab === "custom-code"
    ? customCode
    : displayCodeTab === "param-intro"
      ? paramIntro
      : fixedCode;
  const visibleRows = codeExampleRows(visibleCode);

  return `
    <div class="code-example-shell">
      <div class="code-example-title-row">
        <div class="code-example-tabs" role="tablist">
          <button type="button" class="${displayCodeTab === "fixed-example" ? "is-active" : ""}" data-action="show-code-example-tab" data-code-tab="fixed-example">调用示例</button>
          <button type="button" class="${displayCodeTab === "custom-code" ? "is-active" : ""}" data-action="show-code-example-tab" data-code-tab="custom-code">自定义代码</button>
          <button type="button" class="${displayCodeTab === "param-intro" ? "is-active" : ""}" data-action="show-code-example-tab" data-code-tab="param-intro">参数介绍</button>
        </div>
        ${renderCodeExampleActions(displayCodeTab)}
      </div>
      ${
        displayCodeTab === "fixed-example"
          ? `
            <div class="code-example-panel is-active" data-code-panel="fixed-example">
              <textarea class="code-example code-example-editor" name="fixed_code_example" rows="${escapeHtml(visibleRows)}" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" readonly>${escapeHtml(fixedCode)}</textarea>
            </div>
          `
          : displayCodeTab === "param-intro"
            ? `
              <div class="code-example-panel is-active" data-code-panel="param-intro">
                <textarea class="code-example code-example-editor" name="param_intro" rows="${escapeHtml(visibleRows)}" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" readonly>${escapeHtml(paramIntro)}</textarea>
              </div>
            `
            : `
            <div class="code-example-panel is-active" data-code-panel="custom-code">
              ${customWarning}
              <textarea class="code-example code-example-editor" name="custom_script" rows="${escapeHtml(visibleRows)}" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off">${escapeHtml(customCode)}</textarea>
            </div>
          `
      }
    </div>
  `;
}

function renderOpenAIGoogleOptionalInput(name, provider, label = name) {
  const value = provider?.[name] || "";
  return `
    <label class="field">
      <span>${escapeHtml(label)}</span>
      <input
        class="openai-google-none-input"
        name="${escapeHtml(name)}"
        value="${escapeHtml(value)}"
        placeholder="None"
      >
    </label>
  `;
}

function renderOpenAIProviderSettings(provider) {
  const callMethod = openAICallMethod(provider);
  const exampleMode = openAIExampleMode(provider);
  const qualityOptions = ["low", "medium", "high", "auto"]
    .map((value) => renderSelectedOption(value, value, provider.quality || "high"))
    .join("");
  const outputFormat = provider.output_format || "png";
  const outputFormatOptions = ["png", "jpeg", "webp"]
    .map((value) => renderSelectedOption(value, value, outputFormat))
    .join("");
  const backgroundChoices = callMethod === "response"
    ? ["transparent", "opaque", "auto"]
    : ["auto", "opaque"];
  const selectedBackground = backgroundChoices.includes(provider.background)
    ? provider.background
    : "auto";
  const backgroundOptions = backgroundChoices
    .map((value) => renderSelectedOption(value, value, selectedBackground))
    .join("");
  const moderationOptions = ["auto", "low"]
    .map((value) => renderSelectedOption(value, value, provider.moderation || "low"))
    .join("");
  const compressionDisabled = outputFormat === "png" ? "disabled" : "";
  const callMethodOptions = [
    renderSelectedOption("gpt-image-2", "gpt-image-2", callMethod),
    renderSelectedOption("response", "response", callMethod),
  ].join("");
  const providerExampleMarkers = "client.images.generate client.responses.create gpt-image-1.5";
  const exampleModeOptions = [
    renderSelectedOption("text_to_image", "文生图", exampleMode),
    renderSelectedOption("image_to_image", "图生图", exampleMode),
  ].join("");
  const nParam = exampleMode === "image_to_image"
    ? renderSoftwareParam("n", "固定为 1")
    : renderSoftwareParam("n");
  const imageParam = exampleMode === "image_to_image"
    ? renderSoftwareParam("image / input_images")
    : "";
  const maskParam = exampleMode === "image_to_image"
    ? renderSoftwareParam("mask", "暂不启用")
    : "";
  const inputFidelityField = exampleMode === "image_to_image"
    ? `
        <label class="field">
          <span>input_fidelity</span>
          <select name="input_fidelity">
            ${renderSelectedOption("high", "high", "high")}
            ${renderSelectedOption("low", "low", "high")}
            ${renderSelectedOption("auto", "auto", "high")}
          </select>
        </label>
      `
    : "";
  const userField = callMethod === "gpt-image-2"
    ? `
        <label class="field">
          <span>user</span>
          <input name="user" value="${escapeHtml(provider.user || "")}">
        </label>
      `
    : "";

  return `
    <!-- ${escapeHtml(providerExampleMarkers)} -->
    ${renderSettingSection("OpenAI API 参数", `
      <div class="provider-settings-grid">
        <label class="field">
          <span>调用方式</span>
          <select name="openai_call_method">${callMethodOptions}</select>
        </label>
        <label class="field">
          <span>生图方式</span>
          <select name="openai_example_mode">${exampleModeOptions}</select>
        </label>
        ${renderSoftwareParam("prompt")}
        ${imageParam}
        ${renderSoftwareParam("size")}
        ${nParam}
        ${renderSoftwareParam("保存路径")}
        <label class="field">
          <span>quality</span>
          <select name="quality">${qualityOptions}</select>
        </label>
        <label class="field">
          <span>output_format</span>
          <select name="output_format" data-output-format-select>${outputFormatOptions}</select>
        </label>
        <label class="field param-field">
          <span>output_compression</span>
          <input name="output_compression" type="number" min="0" max="100" value="${escapeHtml(provider.output_compression ?? 80)}" ${compressionDisabled}>
        </label>
        <label class="field">
          <span>background</span>
          <select name="background">${backgroundOptions}</select>
        </label>
        <label class="field">
          <span>moderation</span>
          <select name="moderation">${moderationOptions}</select>
        </label>
        ${inputFidelityField}
        ${maskParam}
        ${userField}
      </div>
    `)}
    <section class="code-example-section">
      ${renderCodeExampleTabs(provider, callMethod, exampleMode)}
    </section>
  `;
}

function renderOpenAIGoogleProviderSettings(provider) {
  const exampleMode = openAIExampleMode(provider);
  const exampleModeOptions = [
    renderSelectedOption("text_to_image", "文生图", exampleMode),
    renderSelectedOption("image_to_image", "图生图", exampleMode),
  ].join("");
  const imageParam = exampleMode === "image_to_image"
    ? renderSoftwareParam("input_images")
    : "";
  const streamValue = provider.google_stream === true ? "true" : "false";

  return `
    ${renderSettingSection("Google API 参数", `
      <div class="provider-settings-grid">
        <label class="field">
          <span>生图方式</span>
          <select name="openai_example_mode">${exampleModeOptions}</select>
        </label>
        ${renderSoftwareParam("prompt")}
        ${imageParam}
        ${renderSoftwareParam("保存路径")}
        <label class="field">
          <span>role</span>
          <input name="google_role" value="${escapeHtml(provider.google_role || "user")}">
        </label>
        <label class="field">
          <span>max_tokens</span>
          <input name="google_max_tokens" type="number" min="1" value="${escapeHtml(provider.google_max_tokens ?? 4096)}">
        </label>
        ${renderOpenAIGoogleOptionalInput("google_temperature", provider, "temperature")}
        ${renderOpenAIGoogleOptionalInput("google_top_p", provider, "top_p")}
        <label class="field param-field">
          <span>stream</span>
          <select name="google_stream" disabled title="当前脚本按完整 JSON 响应解析图片，stream 固定为 false。">
            ${renderSelectedOption("false", "false", streamValue)}
            ${renderSelectedOption("true", "true", streamValue)}
          </select>
        </label>
        ${renderOpenAIGoogleOptionalInput("google_stop", provider, "stop")}
        ${renderOpenAIGoogleOptionalInput("google_presence_penalty", provider, "presence_penalty")}
        ${renderOpenAIGoogleOptionalInput("google_frequency_penalty", provider, "frequency_penalty")}
        ${renderOpenAIGoogleOptionalInput("google_logit_bias", provider, "logit_bias")}
        ${renderOpenAIGoogleOptionalInput("google_user", provider, "user")}
        ${renderOpenAIGoogleOptionalInput("google_response_format", provider, "response_format")}
        ${renderOpenAIGoogleOptionalInput("google_seen", provider, "seen")}
        ${renderOpenAIGoogleOptionalInput("google_tools", provider, "tools")}
        ${renderOpenAIGoogleOptionalInput("google_tool_choice", provider, "tool_choice")}
      </div>
    `)}
    <section class="code-example-section">
      ${renderCodeExampleTabs(provider, "openai-google", exampleMode)}
    </section>
  `;
}

function renderTimeoutFields(provider, options = {}) {
  const includeApimart = options.includeApimart === true;
  return `
    <label class="field param-field">
      <span>request_timeout_seconds</span>
      <input name="request_timeout_seconds" type="number" min="1" value="${escapeHtml(provider.request_timeout_seconds ?? 300)}">
    </label>
    <label class="field param-field">
      <span>download_timeout_seconds</span>
      <input name="download_timeout_seconds" type="number" min="1" value="${escapeHtml(provider.download_timeout_seconds ?? 120)}">
    </label>
    <label class="field param-field">
      <span>max_retry_attempts</span>
      <input name="max_retry_attempts" type="number" min="1" value="${escapeHtml(provider.max_retry_attempts ?? 5)}">
    </label>
    ${
      includeApimart
        ? `
          <label class="field param-field">
            <span>apimart_task_timeout_seconds</span>
            <input name="apimart_task_timeout_seconds" type="number" min="1" value="${escapeHtml(provider.apimart_task_timeout_seconds ?? 420)}">
          </label>
          <label class="field param-field">
            <span>apimart_task_poll_interval_seconds</span>
            <input name="apimart_task_poll_interval_seconds" type="number" min="1" value="${escapeHtml(provider.apimart_task_poll_interval_seconds ?? 5)}">
          </label>
        `
        : ""
    }
  `;
}

function renderSysrvGoogleProviderSettings(provider) {
  const exampleMode = openAIExampleMode(provider);
  const exampleModeOptions = [
    renderSelectedOption("text_to_image", "文生图", exampleMode),
    renderSelectedOption("image_to_image", "图生图", exampleMode),
  ].join("");
  const imageParam = exampleMode === "image_to_image"
    ? renderSoftwareParam("input_images")
    : "";

  return `
    ${renderSettingSection("Google API 参数", `
      <div class="provider-settings-grid">
        <label class="field">
          <span>生图方式</span>
          <select name="openai_example_mode">${exampleModeOptions}</select>
        </label>
        ${renderSoftwareParam("prompt / operation_prompt")}
        ${imageParam}
        ${renderSoftwareParam("保存路径 / output_path / result_json_path")}
        <label class="field">
          <span>role</span>
          <input name="google_role" value="${escapeHtml(provider.google_role || "user")}">
        </label>
        ${renderTimeoutFields(provider)}
      </div>
    `)}
    <section class="code-example-section">
      ${renderCodeExampleTabs(provider, "sysrv-google", exampleMode)}
    </section>
  `;
}

function renderApimartOpenAIProviderSettings(provider) {
  const exampleMode = openAIExampleMode(provider);
  const exampleModeOptions = [
    renderSelectedOption("text_to_image", "文生图", exampleMode),
    renderSelectedOption("image_to_image", "图生图", exampleMode),
  ].join("");
  const outputFormat = provider.output_format || "png";
  const outputFormatOptions = ["png", "jpeg", "webp"]
    .map((value) => renderSelectedOption(value, value, outputFormat))
    .join("");
  const compressionDisabled = outputFormat === "png" ? "disabled" : "";
  const backgroundOptions = ["auto", "opaque"]
    .map((value) => renderSelectedOption(value, value, provider.background || "auto"))
    .join("");
  const moderationOptions = ["auto", "low"]
    .map((value) => renderSelectedOption(value, value, provider.moderation || "low"))
    .join("");
  const imageParam = exampleMode === "image_to_image"
    ? renderSoftwareParam("input_images")
    : "";
  const moderationField = exampleMode === "text_to_image"
    ? `
        <label class="field">
          <span>moderation</span>
          <select name="moderation">${moderationOptions}</select>
        </label>
      `
    : "";
  const imageOnlyFields = exampleMode === "image_to_image"
    ? `
        <label class="field">
          <span>input_fidelity</span>
          <input name="input_fidelity" value="${escapeHtml(provider.input_fidelity || "")}" placeholder="None">
        </label>
        <label class="field">
          <span>mask_path</span>
          <input name="mask_path" value="${escapeHtml(provider.mask_path || "")}" placeholder="暂不启用">
        </label>
      `
    : "";

  return `
    ${renderSettingSection("Openai API 参数", `
      <div class="provider-settings-grid">
        <label class="field">
          <span>生图方式</span>
          <select name="openai_example_mode">${exampleModeOptions}</select>
        </label>
        ${renderSoftwareParam("prompt / operation_prompt")}
        ${imageParam}
        ${renderSoftwareParam("size / resolved_size")}
        ${renderSoftwareParam("n")}
        ${renderSoftwareParam("保存路径 / output_dir / output_path / result_json_path")}
        <label class="field">
          <span>quality</span>
          <select name="quality">
            ${["low", "medium", "high", "auto"].map((value) => renderSelectedOption(value, value, provider.quality || "high")).join("")}
          </select>
        </label>
        <label class="field">
          <span>output_format</span>
          <select name="output_format" data-output-format-select>${outputFormatOptions}</select>
        </label>
        <label class="field param-field">
          <span>output_compression</span>
          <input name="output_compression" type="number" min="0" max="100" value="${escapeHtml(provider.output_compression ?? 80)}" ${compressionDisabled}>
        </label>
        <label class="field">
          <span>background</span>
          <select name="background">${backgroundOptions}</select>
        </label>
        ${moderationField}
        <label class="field">
          <span>user</span>
          <input name="user" value="${escapeHtml(provider.user || "")}">
        </label>
        ${imageOnlyFields}
        ${renderTimeoutFields(provider, { includeApimart: true })}
      </div>
    `)}
    <section class="code-example-section">
      ${renderCodeExampleTabs(provider, "apimart-openai", exampleMode)}
    </section>
  `;
}

function renderAdapterSpecificSettings(provider) {
  const capability = providerCapability(provider);
  const unavailableMessage = providerUnavailableMessage(provider);

  if (capability.implemented && normalizeProviderAdapter(provider.adapter) === "openai-google") {
    return renderOpenAIGoogleProviderSettings(provider);
  }

  if (capability.implemented && normalizeProviderAdapter(provider.adapter) === "sysrv-google") {
    return renderSysrvGoogleProviderSettings(provider);
  }

  if (capability.implemented && normalizeProviderAdapter(provider.adapter) === "apimart-openai") {
    return renderApimartOpenAIProviderSettings(provider);
  }

  if (!capability.implemented && normalizeProviderAdapter(provider.adapter) === "google") {
    return renderSettingSection("调用示例", `
      <div class="settings-placeholder">
        <p>Google adapter 尚未接入具体调用代码。选择 google 后可以先保存 Provider 配置，但点击生成时应提示：${escapeHtml(unavailableMessage)}</p>
        <p>后续接入 Google 时，需要根据 Google 官方生图接口文档补齐参数表和调用示例。</p>
      </div>
    `);
  }
  if (!capability.implemented && normalizeProviderAdapter(provider.adapter) === "other") {
    return renderSettingSection("调用示例", `
      <div class="settings-placeholder">
        <p>Other adapter 用于后续自定义接口。当前只允许保存配置，不执行生图。</p>
        <p>点击生成时应提示：${escapeHtml(unavailableMessage)}</p>
      </div>
    `);
  }
  return renderOpenAIProviderSettings(provider);
}

function renderSettings() {
  document.body.classList.remove("has-lightbox");
  if (!state.settings) {
  app.innerHTML = `
    <section class="panel">
      <div class="panel-header settings-title-row">
        <h1>设置</h1>
      </div>
      <div class="message is-loading" data-message>加载中</div>
      </section>
    `;
    return;
  }

  const settings = state.settings || {};
  const providers = settings.providers || {};
  const providerName = settingsEditingProviderName();
  const provider = {
    ...providerFieldDefaults(),
    ...settingsEditingProvider(),
  };
  const proxyMode = providerProxyMode(provider);
  const proxyUrlDisabled = provider.proxy_mode === "custom" ? "" : "disabled";
  const providerOptions = sortedProviderEntries(providers)
    .map(([name, item]) => {
      const label = providerDisplayNameWithAdapter(name, item);
      const selected = name === providerName ? "selected" : "";
      return `<option value="${escapeHtml(name)}" ${selected}>${escapeHtml(label)}</option>`;
    })
    .join("");
  const adapterOptions = AVAILABLE_PROVIDER_ADAPTERS.map((adapter) =>
    renderSelectedOption(adapter.value, adapter.label, provider.adapter || "openai"),
  ).join("");
  const providerSelect = `
    <label class="settings-provider-select">
      <select name="provider">
        ${providerOptions || `<option value="">未选择 provider</option>`}
      </select>
    </label>
  `;
  const deleteDisabled = providerName ? "" : "disabled";
  const saveDisabled = state.settingsDirty ? "" : "disabled";
  const saveDisabledAttr = saveDisabled;
  const saveDirtyAttr = state.settingsDirty ? "true" : "false";
  const copyDisabled = providerName ? "" : "disabled";

  app.innerHTML = `
    <section class="panel">
      <div class="panel-header settings-title-row">
        <h1>设置</h1>
        ${providerSelect}
        <div class="actions settings-top-actions">
          <button type="button" data-action="copy-provider" ${copyDisabled}>复制</button>
          <button type="button" data-action="new-provider">新建 Provider</button>
          <button type="button" form="settings-form" data-action="cancel-settings-changes" data-settings-dirty="${saveDirtyAttr}" ${saveDisabledAttr}>取消</button>
          <button type="submit" class="primary" form="settings-form" data-settings-dirty="${saveDirtyAttr}" ${saveDisabledAttr}>保存设置</button>
          <button type="button" class="danger" data-action="delete-provider" ${deleteDisabled}>删除 Provider</button>
        </div>
      </div>
      <form id="settings-form" class="settings-form" data-settings-form>
        <section class="settings-section settings-identity-section">
          <div class="provider-identity-grid">
            <label class="field">
              <span>显示名称</span>
              <input name="display_name" value="${escapeHtml(provider.display_name || "")}">
            </label>
            <label class="field">
              <span>内部编号</span>
              <input name="provider_key" value="${escapeHtml(providerName)}" readonly aria-readonly="true">
            </label>
            <label class="field">
              <span>接口类型</span>
              <select name="adapter">
                ${adapterOptions}
              </select>
            </label>
          </div>
        </section>
        ${renderSettingSection("连接信息", `
          <div class="connection-settings-grid">
            <label class="field">
              <span>base_url</span>
              <input name="base_url" value="${escapeHtml(provider.base_url || "")}">
            </label>
            <label class="field connection-api-key-field">
              <div class="field-title-row">
                <span>api_key</span>
                <small class="inline-help">填写 api_key 时优先使用 api_key；api_key 为空时使用 api_key_env。</small>
              </div>
              <input name="api_key" autocomplete="off" value="${escapeHtml(provider.api_key || "")}" title="${escapeHtml(provider.api_key || "")}">
            </label>
            <label class="field connection-api-key-env-field">
              <span>api_key_env</span>
              ${renderSettingHistoryInput("api_key_env", provider.api_key_env || "", { label: "api_key_env" })}
            </label>
            <label class="field connection-model-field">
              <span>model</span>
              ${renderSettingHistoryInput("model", provider.model || "", { label: "model" })}
            </label>
            <label class="field connection-user-agent-field">
              <span>user_agent</span>
              ${renderSettingHistoryInput("user_agent", provider.user_agent || "", {
                label: "user_agent",
                className: normalizeProviderAdapter(provider.adapter) === "openai-google" ? "openai-google-user-agent-field" : "",
                inputClass: normalizeProviderAdapter(provider.adapter) === "openai-google" ? "openai-google-none-input" : "",
                placeholder: normalizeProviderAdapter(provider.adapter) === "openai-google" ? "None" : "",
              })}
            </label>
            <label class="field connection-proxy-mode-field">
              <span>代理模式</span>
              <select name="proxy_mode">
                ${renderSelectedOption("system", "系统代理", proxyMode)}
                ${renderSelectedOption("custom", "自定义代理", proxyMode)}
                ${renderSelectedOption("none", "不走代理", proxyMode)}
              </select>
            </label>
            <label class="field connection-proxy-url-field">
              <span>自定义代理</span>
              <input name="proxy_url" value="${escapeHtml(provider.proxy_url || "")}" placeholder="http://127.0.0.1:7890" ${proxyUrlDisabled}>
            </label>
            <label class="field connection-proxy-cert-field checkbox-field">
              <span>代理证书</span>
              <label class="inline-checkbox">
                <input type="checkbox" name="allow_untrusted_proxy_certificate" ${provider.allow_untrusted_proxy_certificate === false ? "" : "checked"}>
                <span>允许不受信任代理证书</span>
              </label>
            </label>
          </div>
        `)}
        ${renderAdapterSpecificSettings(provider)}
        <div class="message" data-message></div>
      </form>
    </section>
  `;
}


Object.assign(globalThis, {
  renderSettingSection,
  renderParamNote,
  settingHistoryValues,
  settingsProviderConfigFieldValues,
  providerFieldHistoryValues,
  renderSettingHistoryInput,
  renderSoftwareParam,
  openAICallMethod,
  openAIExampleMode,
  providerProxyMode,
  providerCodeValue,
  defaultCodeExample,
  fixedCodeExample,
  parameterIntroCode,
  renderCodeExampleActions,
  customScriptCode,
  codeExampleRows,
  renderCodeExampleTabs,
  renderOpenAIProviderSettings,
  renderOpenAIGoogleProviderSettings,
  renderSysrvGoogleProviderSettings,
  renderApimartOpenAIProviderSettings,
  renderAdapterSpecificSettings,
  renderSettings,
});
