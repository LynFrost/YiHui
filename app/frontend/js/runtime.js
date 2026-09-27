export const runtime = {
  render: () => {},
  renderManagerIfActive: () => false,
  renderSettingsIfActive: () => false,
  renderDataSafetyIfActive: () => false,
  setMessage: () => {},
};

export function registerRuntime(nextRuntime) {
  Object.assign(runtime, nextRuntime);
}

Object.assign(globalThis, { runtime, registerRuntime });
