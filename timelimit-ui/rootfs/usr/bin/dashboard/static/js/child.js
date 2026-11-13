import { apiFetch } from "./api.js";
import { formatDuration, statusLabel } from "./format.js";
import { t } from "./i18n.js";
import { initBlocked, renderBlocked } from "./blocked.js";
import { initCategories, renderCategoryActions } from "./categories.js";
import { initRules, renderRules } from "./rules.js";

const $ = (id) => document.getElementById(id);
let data = null;

function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function badge(status, text) {
  const span = document.createElement("span");
  span.className = "badge";
  span.dataset.status = status;
  span.textContent = text;
  return span;
}

function renderCategories() {
  const body = $("categories-body");
  body.replaceChildren(
    ...data.categories.map((category) => {
      const row = document.createElement("tr");
      row.dataset.categoryId = category.id;
      const title = cell(category.title, "indent");
      title.dataset.depth = String(category.depth);
      if (!category.on_server) title.append(" ", badge("gone", t("child.not_on_server")));
      row.append(title, cell(formatDuration(category.used_today_ms)), cell(category.extra_time_ms ? `+${formatDuration(category.extra_time_ms)}` : "-"));
      const state = document.createElement("td");
      if (category.temp_blocked) state.append(badge("temp_blocked", statusLabel("temp_blocked")));
      if (category.limits_disabled) state.append(badge("limits_disabled", statusLabel("limits_disabled")));
      row.append(state, cell(String(category.app_count)), cell(String(category.rule_count)));
      return row;
    }),
  );
  $("categories-empty").hidden = data.categories.length > 0;
  renderCategoryActions(data);
}

function renderDevices() {
  const body = $("devices-body");
  body.replaceChildren(
    ...data.devices.map((device) => {
      const row = document.createElement("tr");
      row.dataset.deviceId = device.id;
      const added = device.added_at ? new Date(device.added_at).toLocaleDateString() : "-";
      row.append(cell(device.name), cell(device.model), cell(added));
      return row;
    }),
  );
  $("devices-empty").hidden = data.devices.length > 0;
}

function render() {
  if (!data) return;
  const { child } = data;
  $("child-name").textContent = child.name;
  const status = $("child-status");
  status.dataset.status = child.status;
  status.textContent = statusLabel(child.status);
  $("child-used").textContent = formatDuration(child.used_today_ms);
  $("child-zone").textContent = child.time_zone;
  $("child-gone").hidden = child.on_server;
  const warning = child.time_zone_warning;
  $("child-zone-warning").hidden = !warning;
  if (warning) {
    $("child-zone-warning-text").textContent = t("rules.zone_warning").replace("{child}", warning.child).replace("{dashboard}", warning.dashboard);
  }
  document.title = `${child.name} - TimeLimit Dashboard`;
  renderCategories();
  renderRules(data);
  renderBlocked(data);
  renderDevices();
}

export async function refreshChild() {
  const page = $("child-page");
  try {
    data = await apiFetch(`/api/children/${encodeURIComponent(page.dataset.childId)}`);
    $("child-unknown").hidden = true;
    $("child-content").hidden = false;
    render();
  } catch (error) {
    if (error.code === "NOT_FOUND") {
      $("child-content").hidden = true;
      $("child-unknown").hidden = false;
    } else {
      $("child-error").textContent = t(`error.${error.code}`);
      $("child-error").hidden = false;
    }
  }
}

function selectTab(name) {
  for (const tab of document.querySelectorAll('[role="tab"]')) {
    const on = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
  }
  for (const panel of document.querySelectorAll('[role="tabpanel"]')) {
    panel.hidden = panel.dataset.panel !== name;
  }
}

export function initChild() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  for (const tab of tabs) {
    tab.addEventListener("click", () => selectTab(tab.dataset.tab));
    tab.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step) return;
      const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
      selectTab(next.dataset.tab);
      next.focus();
    });
  }
  initRules(() => data);
  initBlocked(() => data);
  initCategories(() => data);
  selectTab("categories");
  document.addEventListener("dashboard:language", render);
}
