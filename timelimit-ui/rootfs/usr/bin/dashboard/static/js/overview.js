import { apiFetch } from "./api.js";
import { t } from "./i18n.js";
import { formatDuration, statusLabel } from "./format.js";

let lastChildren = null;

function card(child) {
  const li = document.createElement("li");
  li.dataset.childId = child.id;
  const link = document.createElement("a");
  link.href = `/children/${encodeURIComponent(child.id)}`;
  link.className = "card-title";
  link.textContent = child.name;
  const status = document.createElement("span");
  status.className = "badge";
  status.dataset.status = child.status;
  status.textContent = statusLabel(child.status);
  const facts = document.createElement("p");
  facts.className = "muted facts";
  facts.textContent = `${t("child.used_today")}: ${formatDuration(child.used_today_ms)} · ${child.category_count} ${t("child.categories").toLowerCase()} · ${child.device_count} ${t("child.devices").toLowerCase()}`;
  li.append(link, status, facts);
  if (!child.on_server) {
    const gone = document.createElement("span");
    gone.className = "badge";
    gone.dataset.status = "gone";
    gone.textContent = t("child.not_on_server");
    li.append(gone);
  }
  return li;
}

function render() {
  const list = document.getElementById("overview-list");
  const empty = document.getElementById("overview-empty");
  if (!list || lastChildren === null) return;
  list.replaceChildren(...lastChildren.map(card));
  empty.hidden = lastChildren.length > 0;
  empty.textContent = t("overview.empty");
}

export async function refreshOverview() {
  const empty = document.getElementById("overview-empty");
  try {
    lastChildren = (await apiFetch("/api/children")).children;
    render();
  } catch (error) {
    empty.hidden = false;
    empty.textContent = t(`error.${error.code}`) || t("error.unknown");
  }
}

document.addEventListener("dashboard:language", render);
