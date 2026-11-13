// Banners that appear on every page: untested server version, ended session (never blocking).

import { apiFetch } from "./api.js";
import { applyTranslations, t } from "./i18n.js";

let last = [];

function text(notice) {
  return t(`notice.${notice.code}`)
    .replace("{level}", String(notice.api_level ?? ""))
    .replace("{child}", notice.child ?? "")
    .replace("{category}", notice.category ?? "");
}

export function renderNotices() {
  const box = document.getElementById("notices");
  if (!box) return;
  box.replaceChildren(
    ...last.map((notice) => {
      const banner = document.createElement("div");
      banner.className = "banner";
      banner.dataset.state = "notice";
      banner.dataset.notice = notice.code;
      const span = document.createElement("span");
      span.textContent = text(notice);
      banner.append(span);
      if (notice.id !== undefined) {
        const close = document.createElement("button");
        close.type = "button";
        close.className = "secondary dismiss-notice";
        close.dataset.i18n = "notice.dismiss";
        close.addEventListener("click", async () => {
          try {
            await apiFetch(`/api/notices/${notice.id}`, { method: "DELETE" });
          } catch {
            /* the banner stays; the next refresh shows the truth */
          }
          await refreshNotices();
        });
        banner.append(close);
      }
      if (notice.code === "SESSION_INVALID") {
        const link = document.createElement("a");
        link.href = "/settings";
        link.dataset.i18n = "notice.SESSION_INVALID.link";
        banner.append(link);
      }
      return banner;
    }),
  );
  applyTranslations(box);
}

export async function refreshNotices() {
  try {
    last = (await apiFetch("/api/notices")).notices;
  } catch {
    last = [];
  }
  renderNotices();
}

document.addEventListener("dashboard:language", renderNotices);
