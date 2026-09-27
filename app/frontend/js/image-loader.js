let saveAreaImageObserver = null;
let saveAreaImageVerifyRunId = 0;

const SAVE_IMAGE_VERIFY_DELAYS = [0, 80, 240, 600];
const SAVE_IMAGE_VERIFY_TIMEOUT_MS = 5000;
const SAVE_IMAGE_VERIFY_INTERVAL_MS = 200;
const SAVE_IMAGE_MAX_RETRIES = 2;

function resetSaveAreaImageObserver() {
  if (saveAreaImageObserver) {
    saveAreaImageObserver.disconnect();
  }
  saveAreaImageObserver = typeof IntersectionObserver === "undefined"
    ? null
    : new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting || entry.intersectionRatio > 0) {
          loadLazyImageSlot(entry.target);
        }
      }
    }, { rootMargin: "600px 0px" });
}

function isImageReady(img) {
  return Boolean(img && img.complete && img.naturalWidth > 0);
}

function retryCountForSlot(slot) {
  const count = Number.parseInt(slot?.dataset?.lazyRetryCount || "0", 10);
  return Number.isFinite(count) ? count : 0;
}

function imageSrcMatchesPath(img, path) {
  if (!img || !path) {
    return false;
  }
  const src = img.getAttribute("src") || "";
  const expectedThumbnail = thumbnailUrl(path);
  return Boolean(src && (
    src.includes(encodeURIComponent(path))
    || src.startsWith(expectedThumbnail)
  ));
}

function lazyImageDisplayUrl(path, retry = false) {
  const baseSrc = thumbnailUrl(path);
  return retry ? `${baseSrc}&retry=${Date.now()}` : baseSrc;
}

function loadLazyImageSlot(slot, retry = false, options = {}) {
  const img = slot?.querySelector?.("img");
  const path = slot?.dataset?.lazyImagePath || slot?.dataset?.imagePath || "";
  if (!img || !path) {
    return;
  }
  if (options.forceVisible) {
    img.loading = "eager";
  }
  const retryCount = retryCountForSlot(slot);
  if (retry && img.getAttribute("src") && !img.complete) {
    return;
  }
  if (retry && retryCount >= SAVE_IMAGE_MAX_RETRIES) {
    return;
  }
  const src = lazyImageDisplayUrl(path, retry);
  const needsSrc = !img.getAttribute("src") || !imageSrcMatchesPath(img, path);
  const failedImage = img.complete && img.naturalWidth === 0;
  if (needsSrc || failedImage || retry) {
    if (retry) {
      slot.dataset.lazyRetryCount = String(retryCount + 1);
    }
    img.setAttribute("src", src);
  }
  if (!img.dataset.lazyRetryBound) {
    img.dataset.lazyRetryBound = "true";
    img.addEventListener("error", () => {
      loadLazyImageSlot(slot, true, { forceVisible: true });
    });
  }
}

function isSlotNearViewport(slot, forceVisible = false) {
  if (forceVisible) {
    return true;
  }
  const rect = slot.getBoundingClientRect();
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
  return rect.bottom >= -400 && rect.top <= viewportHeight + 800;
}

function observeSaveAreaImageSlot(slot, forceVisible = false) {
  if (!slot) {
    return;
  }
  if (saveAreaImageObserver) {
    saveAreaImageObserver.observe(slot);
  }
  if (isSlotNearViewport(slot, forceVisible)) {
    loadLazyImageSlot(slot, false, { forceVisible });
  }
}

function describeUnresolvedSaveAreaImage(slot, img, path, reason) {
  const rect = slot.getBoundingClientRect?.();
  return {
    reason,
    path,
    src: img?.getAttribute?.("src") || "",
    complete: Boolean(img?.complete),
    naturalWidth: img?.naturalWidth || 0,
    retryCount: retryCountForSlot(slot),
    rect: rect
      ? {
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      }
      : null,
  };
}

function collectUnresolvedSaveAreaImages(options = {}) {
  const saveArea = document.querySelector("[data-save-area]");
  if (!saveArea) {
    return [];
  }
  const forceVisible = Boolean(options.forceVisible);
  const unresolvedSaveAreaImages = [];
  for (const slot of saveArea.querySelectorAll("[data-lazy-image-path]")) {
    const img = slot.querySelector("img");
    const path = slot.dataset.lazyImagePath || slot.dataset.imagePath || "";
    if (!img || !path) {
      continue;
    }
    observeSaveAreaImageSlot(slot, forceVisible);
    if (forceVisible) {
      img.loading = "eager";
    }
    let unresolvedReason = "";
    if (!imageSrcMatchesPath(img, path)) {
      loadLazyImageSlot(slot, false, { forceVisible });
      unresolvedReason = "src_mismatch";
    } else if (!isImageReady(img) && isSlotNearViewport(slot, forceVisible)) {
      loadLazyImageSlot(slot, true, { forceVisible });
      unresolvedReason = img.complete ? "empty_image" : "not_complete";
    } else if (!isImageReady(img)) {
      unresolvedReason = "not_ready";
    }
    if (unresolvedReason) {
      unresolvedSaveAreaImages.push(describeUnresolvedSaveAreaImage(slot, img, path, unresolvedReason));
    }
  }
  return unresolvedSaveAreaImages;
}

function scheduleNextSaveAreaImageVerification(options = {}) {
  const runId = Number(options.runId || 0);
  if (runId && runId !== saveAreaImageVerifyRunId) {
    return;
  }
  const startedAtMs = Number(options.startedAtMs || performance.now());
  const unresolvedSaveAreaImages = collectUnresolvedSaveAreaImages(options);
  if (!unresolvedSaveAreaImages.length) {
    return;
  }
  const elapsedMs = performance.now() - startedAtMs;
  if (elapsedMs >= SAVE_IMAGE_VERIFY_TIMEOUT_MS) {
    console.warn("Save-area images still not ready after verification", unresolvedSaveAreaImages);
    return;
  }
  window.setTimeout(() => scheduleNextSaveAreaImageVerification({
    ...options,
    runId,
    startedAtMs,
  }), SAVE_IMAGE_VERIFY_INTERVAL_MS);
}

function verifySaveAreaImages(options = {}) {
  const runId = Number(options.runId || 0);
  if (runId && runId !== saveAreaImageVerifyRunId) {
    return;
  }
  const unresolvedSaveAreaImages = collectUnresolvedSaveAreaImages(options);
  if (options.finalPass && unresolvedSaveAreaImages.length) {
    scheduleNextSaveAreaImageVerification(options);
  }
}

function stabilizeSaveAreaImages(options = {}) {
  const runId = saveAreaImageVerifyRunId + 1;
  saveAreaImageVerifyRunId = runId;
  const startedAtMs = performance.now();
  requestAnimationFrame(() => {
    verifySaveAreaImages({ ...options, runId, startedAtMs });
    SAVE_IMAGE_VERIFY_DELAYS.forEach((delay, index) => {
      const finalPass = index === SAVE_IMAGE_VERIFY_DELAYS.length - 1;
      window.setTimeout(() => verifySaveAreaImages({
        ...options,
        runId,
        startedAtMs,
        finalPass,
      }), delay);
    });
  });
}

function installSaveAreaImageWakeListeners() {
  const wake = () => globalThis.wakeVisibleSaveImages?.({ forceVisible: true });
  window.addEventListener("scroll", wake, { passive: true });
  window.addEventListener("resize", wake);
  window.addEventListener("focus", wake);
  document.addEventListener("visibilitychange", wake);
}

installSaveAreaImageWakeListeners();

Object.assign(globalThis, {
  resetSaveAreaImageObserver,
  loadLazyImageSlot,
  lazyImageDisplayUrl,
  observeSaveAreaImageSlot,
  collectUnresolvedSaveAreaImages,
  scheduleNextSaveAreaImageVerification,
  verifySaveAreaImages,
  stabilizeSaveAreaImages,
  installSaveAreaImageWakeListeners,
});
