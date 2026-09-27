async function api(path, options = {}) {
  const requestOptions = { ...options };
  const headers = { ...(requestOptions.headers || {}) };

  if (
    requestOptions.body &&
    typeof requestOptions.body === "object" &&
    !(requestOptions.body instanceof FormData)
  ) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
    requestOptions.body = JSON.stringify(requestOptions.body);
  }

  requestOptions.headers = headers;

  const response = await fetch(path, requestOptions);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    throw new Error(data?.error || `HTTP ${response.status}`);
  }

  return data || {};
}


Object.assign(globalThis, {
  api,
});
