// Every browser request goes through apiFetch: it always has a timeout (TR-303).

export class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

let timeoutMs = 10000;

export function configureApi({ browserTimeout }) {
  timeoutMs = browserTimeout * 1000;
}

export async function apiFetch(path, { method = "GET", body } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    let data = null;
    try {
      data = await response.json();
    } catch {
      /* not JSON: handled below */
    }
    if (!response.ok) {
      const code = data && data.code ? data.code : "INTERNAL_ERROR";
      throw new ApiError(code, (data && data.message) || response.statusText, response.status);
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    // aborted (too slow) or no connection at all: the backend itself is unreachable
    throw new ApiError("SERVER_UNREACHABLE", String(error && error.message), 0);
  } finally {
    clearTimeout(timer);
  }
}
