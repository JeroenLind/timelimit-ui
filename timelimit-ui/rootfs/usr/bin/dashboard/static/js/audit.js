// The audit log: tab "Changes" per child and "Other changes" in the settings (plan E12, FR-1100, FR-1101).

import { apiFetch } from "./api.js";
import { currentLanguage, t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let path = null;
let general = false;

function label(entry) {
  const known = t(`audit.action.${entry.action}`);
  return known.startsWith("audit.action.") ? entry.action : known;
}

function detail(entry) {
  const name = entry.detail.title || entry.detail.name;
  return name ? ` \u2013 ${name}` : "";
}

async function load() {
  try {
    const data = await apiFetch(path);
    $("audit-error").hidden = true;
    $("audit-empty").hidden = data.entries.length > 0;
    $("audit-table").hidden = data.entries.length === 0;
    $("audit-body").replaceChildren(
      ...data.entries.map((entry) => {
        const row = document.createElement("tr");
        row.dataset.action = entry.action;
        row.dataset.result = entry.result;
        const when = document.createElement("td");
        when.textContent = new Date(entry.at).toLocaleString(currentLanguage());
        const what = document.createElement("td");
        what.textContent = label(entry) + detail(entry);
        row.append(when, what);
        if (!general) {
          const category = document.createElement("td");
          category.textContent = entry.category_title || "";
          row.append(category);
        }
        const result = document.createElement("td");
        result.textContent = t(`audit.result.${entry.result}`);
        row.append(result);
        return row;
      }),
    );
  } catch (error) {
    $("audit-error").textContent = t(`error.${error.code}`);
    $("audit-error").hidden = false;
  }
}

/** Tab "Changes" of a child detail page. */
export function initChildAudit(childId) {
  path = `/api/children/${encodeURIComponent(childId)}/audit`;
  general = false;
  $("tab-changes").addEventListener("click", load);
  document.addEventListener("dashboard:changed", () => !$("panel-changes").hidden && load());
}

/** "Other changes" on the settings page, shown while the dashboard is linked. */
export function refreshGeneralAudit(linkState) {
  const show = linkState === "ready" || linkState === "registered";
  $("audit-section").hidden = !show;
  if (!show) return;
  path = "/api/audit";
  general = true;
  load();
}
