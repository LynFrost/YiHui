import { registerRuntime } from "./js/runtime.js";
import "./js/constants.js";
import "./js/state.js";
import "./js/runtime.js";
import "./js/utils.js";
import "./js/persistence.js";
import "./js/api.js";
import "./js/providers.js";
import "./js/nodes.js";
import "./js/image-loader.js";
import "./js/render-operation.js";
import "./js/render-save.js";
import "./js/render-history.js";
import "./js/render-data-safety.js";
import "./js/render-tag-management.js";
import "./js/render-instance.js";
import "./js/render-settings.js";
import "./js/actions-settings.js";
import "./js/tags.js";
import "./js/actions-manager.js";
import "./js/actions-data-safety.js";
import "./js/actions-tag-management.js";
import "./js/lightbox.js";
import "./js/events.js";

registerRuntime({
  render: globalThis.render,
  renderManagerIfActive: globalThis.renderManagerIfActive,
  renderSettingsIfActive: globalThis.renderSettingsIfActive,
  renderDataSafetyIfActive: globalThis.renderDataSafetyIfActive,
  setMessage: globalThis.setMessage,
});

globalThis.boot();
