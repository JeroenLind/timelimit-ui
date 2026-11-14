// Categories tab: add, rename, move below another category, order, delete, unassigned apps, disable limits (plan E6a).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { confirmDialog } from "./dialog.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let getData = () => null;
let editing = null; // null: new category, otherwise the category being edited
let limitsFor = null;
let settingsFor = null;
const WARNINGS = [1, 3, 5, 10, 15];
const busy = new Set(); // category ids with a change on its way

const childPath = () => `/api/children/${encodeURIComponent($("child-page").dataset.childId)}`;

function button(label, onClick, { disabled = false, title = "" } = {}) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "secondary small";
  b.textContent = label;
  b.dataset.changeControl = "";
  if (disabled) {
    b.disabled = true;
    b.dataset.keepDisabled = "";
  }
  if (title) b.title = title;
  b.addEventListener("click", onClick);
  return b;
}

/** Sends a change, shows its state, refreshes the view, and shows a failure under the toolbar. */
async function run(key, request) {
  $("categories-error").hidden = true;
  busy.add(key);
  redraw();
  try {
    await track(request);
    return true;
  } catch (error) {
    $("categories-error").textContent = error.field ? error.message : t(`error.${error.code}`);
    $("categories-error").hidden = false;
    return false;
  } finally {
    busy.delete(key);
    document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
    redraw();
  }
}

function redraw() {
  const data = getData();
  if (data) renderCategoryActions(data);
}

function descendants(categories, id) {
  const found = new Set();
  const pending = [id];
  while (pending.length) {
    const current = pending.pop();
    for (const c of categories) {
      if (c.parent_id === current && !found.has(c.id)) {
        found.add(c.id);
        pending.push(c.id);
      }
    }
  }
  return found;
}

/** The rows are drawn by child.js; this adds the action cell and the toolbar (called after every render). */
export function renderCategoryActions(data) {
  const live = data.categories.filter((c) => c.on_server);
  const select = $("category-unassigned");
  // keep the control as it is while the parent is using it; rebuild only when the choices changed
  const signature = JSON.stringify(live.map((c) => [c.id, c.title]));
  const rebuilt = select.dataset.signature !== signature;
  if (rebuilt) {
    select.replaceChildren(new Option(t("categories.unassigned.none"), ""), ...live.map((c) => new Option(c.title, c.id)));
    select.dataset.signature = signature;
  }
  // follow the server only when its value changed or the choices were rebuilt, never in the middle of a pick
  const serverValue = live.some((c) => c.id === data.child.category_for_unassigned) ? data.child.category_for_unassigned : "";
  if (select.dataset.server !== serverValue || rebuilt) {
    select.value = serverValue;
    select.dataset.server = serverValue;
  }
  for (const row of $("categories-body").querySelectorAll("tr")) {
    const category = data.categories.find((c) => c.id === row.dataset.categoryId);
    row.querySelector(".category-actions")?.remove();
    if (!category) continue;
    const cellEl = document.createElement("td");
    cellEl.className = "category-actions";
    if (category.on_server && !busy.has(category.id)) {
      const siblings = live.filter((c) => c.parent_id === category.parent_id);
      const at = siblings.findIndex((c) => c.id === category.id);
      cellEl.append(
        button(t("categories.edit"), () => openDialog(category)),
        button("\u2191", () => move(category, "up"), { disabled: at <= 0, title: t("categories.up") }),
        button("\u2193", () => move(category, "down"), { disabled: at === siblings.length - 1, title: t("categories.down") }),
        button(t("categories.settings"), () => openSettings(category)),
        category.limits_disabled
          ? button(t("categories.limits.enable"), () => setLimits(category, 0))
          : button(t("categories.limits.disable"), () => openLimits(category)),
        button(t("categories.delete"), () => remove(category, live)),
      );
      for (const b of cellEl.querySelectorAll("button")) b.setAttribute("aria-label", `${b.title || b.textContent} ${category.title}`);
    } else if (busy.has(category.id)) {
      cellEl.textContent = t("rules.waiting");
      row.dataset.pending = "";
    }
    row.append(cellEl);
  }
}

async function move(category, direction) {
  await run(category.id, () => apiFetch(`${childPath()}/categories/${encodeURIComponent(category.id)}/move`, { method: "POST", body: { direction } }));
}

async function remove(category, live) {
  const subs = live.some((c) => c.parent_id === category.id);
  if (subs) {
    $("categories-error").textContent = t("categories.delete.has_subs");
    $("categories-error").hidden = false;
    return;
  }
  const detail = [];
  if (category.rule_count) detail.push(t("categories.delete.rules").replace("{count}", String(category.rule_count)));
  if (category.app_count) detail.push(t("categories.delete.apps").replace("{count}", String(category.app_count)));
  const yes = await confirmDialog({
    title: t("categories.delete.title"),
    message: [t("categories.delete.text").replace("{name}", category.title), ...detail].join(" "),
    confirmLabel: t("categories.delete"),
    danger: true,
  });
  if (!yes) return;
  await run(category.id, () => apiFetch(`${childPath()}/categories/${encodeURIComponent(category.id)}`, { method: "DELETE" }));
}

function setLimits(category, minutes) {
  return run(category.id, () => apiFetch(`${childPath()}/categories/${encodeURIComponent(category.id)}/disable-limits`, { method: "PUT", body: { minutes } }));
}

function fieldError(field, message) {
  const span = document.querySelector(`#category-form [data-error-for="${field}"], #limits-form [data-error-for="${field}"], #settings-form [data-error-for="${field}"]`);
  if (!span) return;
  span.textContent = message ?? "";
  span.hidden = !message;
}

function openLimits(category) {
  limitsFor = category;
  fieldError("limit_minutes", "");
  $("limits-category").textContent = category.title;
  $("limits-dialog").showModal();
  $("limits-minutes").focus();
}

function openDialog(category) {
  editing = category;
  const data = getData();
  fieldError("title", "");
  fieldError("parent_id", "");
  $("category-title").textContent = t(category ? "categories.edit.title" : "categories.add.title");
  $("category-name").value = category ? category.title : "";
  const live = data.categories.filter((c) => c.on_server);
  const blocked = category ? new Set([category.id, ...descendants(live, category.id)]) : new Set();
  $("category-parent").replaceChildren(new Option(t("categories.parent.none"), ""), ...live.filter((c) => !blocked.has(c.id)).map((c) => new Option(c.title, c.id)));
  $("category-parent").value = category ? category.parent_id : "";
  $("category-dialog").showModal();
  $("category-name").focus();
}

async function submitCategory(event) {
  event.preventDefault();
  fieldError("title", "");
  const title = $("category-name").value.trim();
  if (!title) {
    fieldError("title", t("categories.name.required"));
    return;
  }
  const body = { title, parent_id: $("category-parent").value };
  const current = editing;
  $("category-dialog").close();
  const url = current ? `${childPath()}/categories/${encodeURIComponent(current.id)}` : `${childPath()}/categories`;
  await run(current ? current.id : "new", () => apiFetch(url, { method: current ? "PUT" : "POST", body }));
}

async function submitLimits(event) {
  event.preventDefault();
  const minutes = Number($("limits-minutes").value);
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 10080) {
    fieldError("limit_minutes", t("categories.limits.invalid"));
    return;
  }
  const category = limitsFor;
  $("limits-dialog").close();
  await setLimits(category, minutes);
}

function openSettings(category) {
  settingsFor = category;
  $("settings-error").hidden = true;
  for (const span of document.querySelectorAll("#settings-form .field-error")) span.hidden = true;
  $("settings-title").textContent = t("categories.settings.title").replace("{name}", category.title);
  $("set-notifications").checked = category.block_notifications;
  $("set-delay").value = String(category.notification_delay_minutes);
  const box = $("set-warnings");
  box.replaceChildren(
    ...WARNINGS.map((minutes) => {
      const label = document.createElement("label");
      label.className = "check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = String(minutes);
      input.checked = category.time_warning_minutes.includes(minutes);
      label.append(input, ` ${minutes}`);
      return label;
    }),
  );
  $("set-battery-charging").value = String(category.battery_charging);
  $("set-battery-mobile").value = String(category.battery_mobile);
  $("set-network-list").checked = category.network_list_enabled;
  $("set-network-count").textContent = t("settings.networks.count").replace("{count}", String(category.network_count));
  $("set-network-reset").disabled = category.network_count === 0;
  if (category.network_count === 0) $("set-network-reset").dataset.keepDisabled = "";
  else delete $("set-network-reset").dataset.keepDisabled;
  $("settings-dialog").showModal();
}

const whole = (id) => {
  const text = $(id).value.trim();
  return /^\d+$/.test(text) ? Number(text) : Number.NaN;
};

async function submitSettings(event) {
  event.preventDefault();
  const category = settingsFor;
  const base = `${childPath()}/categories/${encodeURIComponent(category.id)}`;
  for (const span of document.querySelectorAll("#settings-form .field-error")) span.hidden = true;
  const delay = whole("set-delay");
  const charging = whole("set-battery-charging");
  const mobile = whole("set-battery-mobile");
  let valid = true;
  for (const [field, value, max] of [["delay_minutes", delay, 10080], ["charging", charging, 100], ["mobile", mobile, 100]]) {
    if (Number.isNaN(value) || value > max) {
      fieldError(field, t("settings.invalid").replace("{max}", String(max)));
      valid = false;
    }
  }
  if (!valid) return;
  const warnings = [...$("set-warnings").querySelectorAll("input:checked")].map((i) => Number(i.value));
  const same = (a, b) => a.length === b.length && a.every((v) => b.includes(v));
  const calls = [];
  const blocked = $("set-notifications").checked;
  if (blocked !== category.block_notifications || delay !== category.notification_delay_minutes) {
    calls.push(["notifications", "PUT", { blocked, delay_minutes: delay }]);
  }
  if (!same(warnings, category.time_warning_minutes)) calls.push(["time-warnings", "PUT", { minutes: warnings }]);
  if (charging !== category.battery_charging || mobile !== category.battery_mobile) calls.push(["battery", "PUT", { charging, mobile }]);
  if ($("set-network-list").checked !== category.network_list_enabled) calls.push(["network-list", "PUT", { enabled: $("set-network-list").checked }]);
  $("settings-dialog").close();
  for (const [part, method, body] of calls) {
    const ok = await run(category.id, () => apiFetch(`${base}/${part}`, { method, body }));
    if (!ok) break; // the reason is shown under the toolbar; later parts are not sent
  }
}

async function resetNetworks() {
  const category = settingsFor;
  const yes = await confirmDialog({
    title: t("settings.networks.reset.title"),
    message: t("settings.networks.reset.text"),
    confirmLabel: t("settings.networks.reset"),
    danger: true,
  });
  if (!yes) return;
  $("settings-dialog").close();
  await run(category.id, () => apiFetch(`${childPath()}/categories/${encodeURIComponent(category.id)}/networks`, { method: "DELETE" }));
}

export function initCategories(provider) {
  getData = provider;
  $("category-add").addEventListener("click", () => openDialog(null));
  $("category-form").addEventListener("submit", submitCategory);
  $("category-cancel").addEventListener("click", () => $("category-dialog").close());
  $("settings-form").addEventListener("submit", submitSettings);
  $("settings-cancel").addEventListener("click", () => $("settings-dialog").close());
  $("set-network-reset").addEventListener("click", resetNetworks);
  $("limits-form").addEventListener("submit", submitLimits);
  $("limits-cancel").addEventListener("click", () => $("limits-dialog").close());
  $("category-unassigned").addEventListener("change", async (event) => {
    await run("unassigned", () => apiFetch(`${childPath()}/unassigned-category`, { method: "PUT", body: { category_id: event.target.value } }));
  });
}
