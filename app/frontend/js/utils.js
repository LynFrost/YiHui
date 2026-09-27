function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderAppVersionBadge() {
  return `<span class="app-version">${escapeHtml(APP_VERSION)}</span>`;
}

function renderAppBrandMeta() {
  return `
    ${renderAppVersionBadge()}
    <img class="app-logo" src="/static/assets/logo.png" alt="雾岛凛 LOGO">
    <span class="app-author">雾岛凛</span>
  `;
}

function mountAppVersionBadge() {
  if (!brand) {
    return;
  }
  if (!brand.querySelector(".app-logo")) {
    brand.insertAdjacentHTML("beforeend", renderAppBrandMeta());
  }
}

function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function cleanString(value) {
  return String(value ?? "");
}

function cleanStringArray(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
}

function normalizePositiveInteger(value, fallback = 1) {
  const number = Number.parseInt(value, 10);
  return Number.isFinite(number) && number >= 1 ? number : fallback;
}

function normalizeOption(value, options, fallback) {
  const cleanValue = String(value ?? "").trim();
  return options.includes(cleanValue) ? cleanValue : fallback;
}

function normalizeSavePerPage(value) {
  const number = Number.parseInt(value, 10);
  return SAVE_PER_PAGE_OPTIONS.includes(number) ? number : 50;
}

function normalizeHistoryPerPage(value) {
  const number = Number.parseInt(value, 10);
  return HISTORY_PER_PAGE_OPTIONS.includes(number) ? number : 50;
}

function normalizeSaveModeFilter(value) {
  return normalizeOption(value, SAVE_MODE_FILTER_OPTIONS, "all");
}

const SIZE_GROUP_ORDER = ["1K", "2K", "4K"];

function presetSizeSortRank(sizeValue) {
  const cleanSize = String(sizeValue || "").trim();
  if (!cleanSize) {
    return {
      groupIndex: -2,
      presetIndex: -1,
      label: "",
    };
  }
  if (cleanSize === "all") {
    return {
      groupIndex: -2,
      presetIndex: -1,
      label: cleanSize,
    };
  }
  if (cleanSize === "__empty__") {
    return {
      groupIndex: -1,
      presetIndex: -1,
      label: cleanSize,
    };
  }
  let presetIndex = 0;
  for (const ratio of ASPECT_RATIO_PRESETS || []) {
    const sizes = SIZE_MAP?.[ratio] || {};
    for (const group of SIZE_GROUP_ORDER) {
      if (String(sizes[group] || "").trim() === cleanSize) {
        return {
          groupIndex: SIZE_GROUP_ORDER.indexOf(group),
          presetIndex,
          label: cleanSize,
        };
      }
    }
    presetIndex += 1;
  }
  return {
    groupIndex: Number.MAX_SAFE_INTEGER,
    presetIndex: Number.MAX_SAFE_INTEGER,
    label: cleanSize,
  };
}

function sortPresetSizeFilterValues(values) {
  return [...values].sort((left, right) => {
    const leftRank = presetSizeSortRank(left);
    const rightRank = presetSizeSortRank(right);
    if (leftRank.groupIndex !== rightRank.groupIndex) {
      return leftRank.groupIndex - rightRank.groupIndex;
    }
    if (leftRank.presetIndex !== rightRank.presetIndex) {
      return leftRank.presetIndex - rightRank.presetIndex;
    }
    return leftRank.label.localeCompare(rightRank.label, "zh-Hans-CN", { numeric: true });
  });
}

function presetSizePrefix(sizeValue) {
  const cleanSize = String(sizeValue || "").trim();
  if (!cleanSize) {
    return "";
  }
  for (const sizes of Object.values(SIZE_MAP || {})) {
    for (const [clarity, size] of Object.entries(sizes || {})) {
      if (String(size || "").trim() === cleanSize) {
        return clarity;
      }
    }
  }
  return "";
}

function formatPresetSizeLabel(sizeValue) {
  const cleanSize = String(sizeValue || "").trim();
  if (!cleanSize) {
    return "";
  }
  const prefix = presetSizePrefix(cleanSize);
  return prefix ? `${prefix}：${cleanSize}` : cleanSize;
}


Object.assign(globalThis, {
  escapeHtml,
  renderAppVersionBadge,
  renderAppBrandMeta,
  mountAppVersionBadge,
  safeObject,
  cleanString,
  cleanStringArray,
  normalizePositiveInteger,
  normalizeOption,
  normalizeSavePerPage,
  normalizeHistoryPerPage,
  normalizeSaveModeFilter,
  SIZE_GROUP_ORDER,
  presetSizeSortRank,
  sortPresetSizeFilterValues,
  presetSizePrefix,
  formatPresetSizeLabel,
});
