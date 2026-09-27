function imageUrl(path) {
  return `/api/image?path=${encodeURIComponent(path)}`;
}

function thumbnailUrl(path) {
  return `/api/thumbnail?path=${encodeURIComponent(path)}`;
}

function renderImageHoverPreview() {
  const path = state.hoverPreview?.path || "";
  if (!path) {
    return "";
  }
  return `
    <div class="image-hover-preview" data-image-hover-preview data-skip-batch-save="true" aria-hidden="true">
      <img src="${escapeHtml(thumbnailUrl(path))}" alt="">
    </div>
  `;
}

function syncImageHoverPreviewDom() {
  document.querySelector("[data-image-hover-preview]")?.remove();
  const previewHtml = renderImageHoverPreview();
  if (previewHtml) {
    document.body.insertAdjacentHTML("beforeend", previewHtml);
  }
}

function showImageHoverPreview(path) {
  if (!path || state.lightbox.path) {
    return;
  }
  state.hoverPreview = { path };
  syncImageHoverPreviewDom();
}

function hideImageHoverPreview() {
  state.hoverPreview = { path: "" };
  syncImageHoverPreviewDom();
}

function clampLightboxZoom(value) {
  return Math.min(
    LIGHTBOX_MAX_ZOOM,
    Math.max(LIGHTBOX_MIN_ZOOM, Number(value.toFixed(2))),
  );
}

function setMessage(message = "", type = "info") {
  const messageNode = document.querySelector("[data-message]");
  if (!messageNode) {
    return;
  }

  messageNode.textContent = message;
  messageNode.className = `message ${type ? `is-${type}` : ""}`.trim();
}

function setGenerationStatus({
  inProgress = false,
  message = "",
  type = "info",
  error = "",
  startedAt = "",
} = {}) {
  state.generationStatus = {
    inProgress: Boolean(inProgress),
    message,
    type,
    error,
    startedAt,
  };
}

function generationStatusMessage() {
  if (state.generationStatus.inProgress) {
    return state.generationStatus.message || "生成中";
  }
  return state.generationStatus.message || state.generationStatus.error || "";
}

function generationStatusType() {
  if (state.generationStatus.inProgress) {
    return "loading";
  }
  return state.generationStatus.type || (state.generationStatus.error ? "error" : "info");
}

function generationTaskId() {
  return `task-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createGenerationTask(payload) {
  const task = {
    id: generationTaskId(),
    status: "running",
    prompt: payload?.prompt || "",
    startedAt: new Date().toISOString(),
    finishedAt: "",
    durationMs: 0,
    error: "",
    outputImagePaths: [],
  };
  state.generationTasks.push(task);
  return task;
}

function updateGenerationTask(taskId, updates = {}) {
  const task = state.generationTasks.find((item) => item.id === taskId);
  if (!task) {
    return null;
  }
  Object.assign(task, updates);
  if (updates.status && updates.status !== "running") {
    task.finishedAt = task.finishedAt || new Date().toISOString();
    task.durationMs = Math.max(0, Date.parse(task.finishedAt) - Date.parse(task.startedAt));
  }
  return task;
}

function generationTaskSummary() {
  const tasks = state.generationTasks || [];
  const running = tasks.filter((task) => task.status === "running");
  const success = tasks.filter((task) => task.status === "success");
  const failed = tasks.filter((task) => task.status === "failed");
  const latest = [...tasks].reverse().find((task) => task.status !== "running");

  if (running.length) {
    return {
      message: `生成中 ${running.length} 个 · 已完成 ${success.length} · 失败 ${failed.length}`,
      type: "loading",
    };
  }
  if (latest?.status === "success") {
    return { message: "已生成", type: "success" };
  }
  if (latest?.status === "failed") {
    return { message: latest.error || "生成失败", type: "error" };
  }
  return {
    message: generationStatusMessage(),
    type: generationStatusType(),
  };
}

function compactOperationStatusMessage(message) {
  const text = String(message || "").trim();
  if (!text) {
    return "";
  }
  const parts = text
    .split(/(?<=[。！？.!?])\s+|\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const compact = parts.length > 2 ? parts.slice(-2).join(" ") : text;
  return compact.length > 96 ? `…${compact.slice(-96)}` : compact;
}

function renderGenerationTaskDetails() {
  const recentTasks = [...(state.generationTasks || [])].slice(-4).reverse();
  if (!recentTasks.length) {
    return "";
  }

  return `
    <div class="generation-task-list" aria-label="生成任务状态">
      ${recentTasks
        .map((task) => {
          const label = task.status === "running"
            ? "生成中"
            : task.status === "success"
              ? "完成"
              : "失败";
          return `
            <span class="generation-task is-${escapeHtml(task.status)}" data-generation-task-id="${escapeHtml(task.id)}">
              ${escapeHtml(label)}
            </span>
          `;
        })
        .join("")}
    </div>
  `;
}


function instanceById(instanceId) {
  return state.instances.find((instance) => String(instance.id) === String(instanceId));
}

function syncInstanceDraftFromDom(instanceId) {
  const draft = state.editing.get(Number(instanceId)) || state.editing.get(String(instanceId));
  if (!draft) {
    return null;
  }

  const card = document.querySelector(`[data-instance-card][data-id="${CSS.escape(String(instanceId))}"]`);
  if (card) {
    draft.prompt = card.querySelector('[name="instance_prompt"]')?.value || "";
    const providerSelect = card.querySelector('[name="instance_provider"]');
    if (providerSelect) {
      draft.provider = providerSelect.value || "";
      draft.generation_params = draft.generation_params && typeof draft.generation_params === "object"
        ? { ...draft.generation_params }
        : {};
      draft.generation_params.provider_key = draft.provider;
    }
    const countInput = card.querySelector('[name="instance_generation_count"]');
    if (countInput) {
      const count = parseGenerationCount(countInput.value);
      if (count) {
        draft.generation_params = draft.generation_params && typeof draft.generation_params === "object"
          ? { ...draft.generation_params }
          : {};
        draft.generation_params.n = count;
        draft.generation_params.count = count;
      }
    }
    draft.tag_draft = card.querySelector('[name="instance_tag_draft"]')?.value || "";
  }
  return draft;
}

function syncVisibleManagerState(sourceNode = null) {
  if (state.page !== "manager") {
    return;
  }

  syncOperationFromDom();
  const card = sourceNode?.closest?.("[data-instance-card]");
  if (card?.dataset.id) {
    syncInstanceDraftFromDom(card.dataset.id);
  }
}

function compactGallery(paths) {
  const result = [];
  for (const path of paths) {
    if (path && !result.includes(path)) {
      result.push(path);
    }
  }
  return result;
}

function buildOperationGallery() {
  syncOperationFromDom();
  return compactGallery([
    ...(state.operation.input_image_paths || []),
  ]);
}

function buildInstanceGallery(instanceId) {
  const item = syncInstanceDraftFromDom(instanceId) || instanceById(instanceId);
  if (!item) {
    return [];
  }
  return compactGallery([
    ...(Array.isArray(item.input_image_paths) ? item.input_image_paths : []),
    ...instanceOutputImagePaths(item),
  ]);
}

function galleryForThumbnailGrid(sourceNode) {
  const grid = sourceNode?.closest?.(".save-thumbnail-grid");
  if (!grid) {
    return [];
  }
  return compactGallery(
    [...grid.querySelectorAll("[data-image-path]")]
      .map((node) => node.dataset.imagePath || ""),
  );
}

function galleryForImageSource(sourceNode, path) {
  if (sourceNode?.closest?.("[data-operation-form]")) {
    return buildOperationGallery();
  }
  const thumbnailGallery = galleryForThumbnailGrid(sourceNode);
  if (thumbnailGallery.length) {
    return thumbnailGallery;
  }
  const card = sourceNode?.closest?.("[data-instance-card]");
  if (card?.dataset.id) {
    return buildInstanceGallery(card.dataset.id);
  }
  return compactGallery([path]);
}

function lightboxState(overrides = {}) {
  return {
    path: "",
    gallery: [],
    galleryIndex: 0,
    zoom: 1,
    error: "",
    panX: 0,
    panY: 0,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    dragOriginX: 0,
    dragOriginY: 0,
    ...overrides,
  };
}

function openImageLightbox(path, sourceNode = null) {
  if (!path) {
    return;
  }

  hideImageHoverPreview();
  syncVisibleManagerState(sourceNode);
  const gallery = galleryForImageSource(sourceNode, path);
  const galleryIndex = Math.max(0, gallery.indexOf(path));
  state.lightbox = lightboxState({
    path,
    gallery: gallery.length ? gallery : [path],
    galleryIndex,
  });
  renderManagerIfActive();
}

function closeImageLightbox() {
  state.lightbox = lightboxState();
  renderManagerIfActive();
}

function switchLightboxImage(delta) {
  const gallery = Array.isArray(state.lightbox.gallery) ? state.lightbox.gallery : [];
  if (!state.lightbox.path || gallery.length <= 1) {
    return;
  }
  const nextIndex = (state.lightbox.galleryIndex + delta + gallery.length) % gallery.length;
  state.lightbox = lightboxState({
    path: gallery[nextIndex],
    gallery,
    galleryIndex: nextIndex,
  });
  renderManagerIfActive();
}

function zoomLightbox(delta) {
  if (!state.lightbox.path) {
    return;
  }

  state.lightbox.zoom = clampLightboxZoom(state.lightbox.zoom + delta);
  renderManagerIfActive();
}

function resetLightboxZoom() {
  if (!state.lightbox.path) {
    return;
  }

  state.lightbox.zoom = 1;
  state.lightbox.panX = 0;
  state.lightbox.panY = 0;
  renderManagerIfActive();
}

function startLightboxDrag(event) {
  if (!state.lightbox.path || !event.target.classList?.contains("lightbox-image")) {
    return;
  }
  event.preventDefault();
  state.lightbox.isDragging = true;
  state.lightbox.dragStartX = event.clientX;
  state.lightbox.dragStartY = event.clientY;
  state.lightbox.dragOriginX = state.lightbox.panX || 0;
  state.lightbox.dragOriginY = state.lightbox.panY || 0;
  event.target.classList.add("is-dragging");
}

function applyLightboxPanToDom() {
  const image = document.querySelector(".lightbox-image");
  if (!image) {
    return;
  }
  image.style.setProperty("--lightbox-pan-x", `${state.lightbox.panX || 0}px`);
  image.style.setProperty("--lightbox-pan-y", `${state.lightbox.panY || 0}px`);
}

function moveLightboxDrag(event) {
  if (!state.lightbox.isDragging) {
    return;
  }
  event.preventDefault();
  state.lightbox.panX = state.lightbox.dragOriginX + event.clientX - state.lightbox.dragStartX;
  state.lightbox.panY = state.lightbox.dragOriginY + event.clientY - state.lightbox.dragStartY;
  applyLightboxPanToDom();
}

function endLightboxDrag() {
  if (!state.lightbox.isDragging) {
    return;
  }
  state.lightbox.isDragging = false;
  document.querySelector(".lightbox-image")?.classList.remove("is-dragging");
}

function markLightboxError() {
  if (!state.lightbox.path || state.lightbox.error) {
    return;
  }

  state.lightbox.error = "图片加载失败";
  renderManagerIfActive();
}


Object.assign(globalThis, {
  imageUrl,
  thumbnailUrl,
  renderImageHoverPreview,
  syncImageHoverPreviewDom,
  showImageHoverPreview,
  hideImageHoverPreview,
  clampLightboxZoom,
  setMessage,
  setGenerationStatus,
  generationStatusMessage,
  generationStatusType,
  generationTaskId,
  createGenerationTask,
  updateGenerationTask,
  generationTaskSummary,
  compactOperationStatusMessage,
  renderGenerationTaskDetails,
  instanceById,
  syncInstanceDraftFromDom,
  syncVisibleManagerState,
  compactGallery,
  buildOperationGallery,
  buildInstanceGallery,
  galleryForThumbnailGrid,
  galleryForImageSource,
  lightboxState,
  openImageLightbox,
  closeImageLightbox,
  switchLightboxImage,
  zoomLightbox,
  resetLightboxZoom,
  startLightboxDrag,
  applyLightboxPanToDom,
  moveLightboxDrag,
  endLightboxDrag,
  markLightboxError,
});
