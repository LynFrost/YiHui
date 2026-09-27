const app = document.querySelector("#app");
const brand = document.querySelector(".brand");
const tabs = document.querySelectorAll(".tab");
const APP_VERSION = "V0.71";
const SIZE_MAP = {
  "1:1":  {"1K": "1024x1024", "2K": "2048x2048", "4K": "2880x2880"},
  "5:4":  {"1K": "1280x1024", "2K": "2560x2048", "4K": "3200x2560"},
  "9:16": {"1K": "864x1536",  "2K": "1152x2048", "4K": "2160x3840"},
  "21:9": {"1K": "2016x864",  "2K": "2688x1152", "4K": "3808x1632"},
  "16:9": {"1K": "1536x864",  "2K": "2048x1152", "4K": "3840x2160"},
  "4:3":  {"1K": "1024x768",  "2K": "2048x1536", "4K": "3264x2448"},
  "3:2":  {"1K": "1536x1024", "2K": "2016x1344", "4K": "3504x2336"},
  "4:5":  {"1K": "1024x1280", "2K": "2048x2560", "4K": "2560x3200"},
  "3:4":  {"1K": "768x1024",  "2K": "1536x2048", "4K": "2448x3264"},
  "2:3":  {"1K": "1024x1536", "2K": "1344x2016", "4K": "2336x3504"},
};
const ASPECT_RATIO_PRESETS = Object.keys(SIZE_MAP);
const CLARITY_PRESETS = ["1K", "2K", "4K", "custom"];
const GENERATION_RESOLUTION_PRESETS = ["1K", "2K", "4K", "custom"];
const PRESET_RESOLUTIONS = ["1K", "2K", "4K"];
const GENERATION_SIZE_PATTERN = /^[1-9][0-9]*x[1-9][0-9]*$/;
const DEFAULT_GENERATION_SIZE = "1024x1024";
const DEFAULT_GENERATION_RESOLUTION = "1K";
const DEFAULT_GENERATION_COUNT = 1;
const UI_STATE_STORAGE_KEY = "AIImageManager.uiState.v1";
const SAVE_PER_PAGE_OPTIONS = [10, 20, 50, 100, 200];
const HISTORY_PER_PAGE_OPTIONS = [10, 20, 50, 100, 200];
const SAVE_SORT_OPTIONS = ["created_desc", "created_asc", "number_asc", "number_desc", "prompt_asc", "prompt_desc", "provider_asc", "provider_desc"];
const SAVE_MODE_FILTER_OPTIONS = ["all", "text_to_image", "image_to_image", "has_output", "no_output"];
const SAVE_STATUS_FILTER_OPTIONS = ["running", "prepared", "failed", "generated", "other"];
const UNTAGGED_FILTER_VALUE = "__untagged__";
const HISTORY_STATUS_OPTIONS = ["all", "success", "failed", "running", "other"];

Object.assign(globalThis, {
  app,
  brand,
  tabs,
  APP_VERSION,
  SIZE_MAP,
  ASPECT_RATIO_PRESETS,
  CLARITY_PRESETS,
  GENERATION_RESOLUTION_PRESETS,
  PRESET_RESOLUTIONS,
  GENERATION_SIZE_PATTERN,
  DEFAULT_GENERATION_SIZE,
  DEFAULT_GENERATION_RESOLUTION,
  DEFAULT_GENERATION_COUNT,
  UI_STATE_STORAGE_KEY,
  SAVE_PER_PAGE_OPTIONS,
  HISTORY_PER_PAGE_OPTIONS,
  SAVE_SORT_OPTIONS,
  SAVE_MODE_FILTER_OPTIONS,
  SAVE_STATUS_FILTER_OPTIONS,
  UNTAGGED_FILTER_VALUE,
  HISTORY_STATUS_OPTIONS,
});












