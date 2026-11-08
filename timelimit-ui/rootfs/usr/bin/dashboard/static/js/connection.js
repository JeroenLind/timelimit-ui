// Server-down handling: health check on load, banner, read-only mode, back-off polling (FR-1000..1003).

import { apiFetch } from "./api.js";
import { applyTranslations, t } from "./i18n.js";
import { getState, setServer } from "./state.js";

export const nextDelay = (attempt, initial, max) => Math.min(initial * 2 ** attempt, max);

export function startConnection(timings, { onBack }) {
  const banner = document.getElementById("server-banner");
  const text = document.getElementById("server-banner-text");
  const retry = document.getElementById("retry-connection");
  let timer = null;
  let attempt = 0;
  let busy = false;

  function render({ server, code }) {
    banner.dataset.state = server;
    banner.dataset.code = code || "";
    banner.hidden = server === "up" || server === "unknown";
    retry.hidden = server !== "down";
    text.textContent = server === "down" ? t("banner.down") : server === "not_configured" ? t("banner.not_configured") : "";
    const offline = server === "down";
    for (const control of document.querySelectorAll("[data-change-control]")) {
      control.disabled = offline;
    }
    document.body.dataset.server = server;
  }

  async function check() {
    if (busy) return;
    busy = true;
    clearTimeout(timer);
    const before = getState().server;
    try {
      const status = await apiFetch("/api/server/status");
      setServer(status.state, status.code);
    } catch (error) {
      setServer("down", error.code);
    }
    busy = false;
    const now = getState().server;
    render(getState());
    if (now === "down") {
      timer = setTimeout(check, nextDelay(attempt++, timings.backoffInitial, timings.backoffMax) * 1000);
    } else {
      attempt = 0;
      timer = setTimeout(check, timings.healthInterval * 1000);
      if (before === "down") onBack();
    }
  }

  retry.addEventListener("click", check);
  applyTranslations(banner);
  return check();
}
