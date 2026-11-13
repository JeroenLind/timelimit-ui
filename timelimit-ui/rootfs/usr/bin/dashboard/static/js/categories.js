// Categories tab: add, rename, move below another category, order, delete, unassigned apps, disable limits (plan E6a).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { confirmDialog } from "./dialog.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let getData = () => null;
let editing = null; // null: new category, otherwise the category being edited
let limitsFor = null;
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
  const span = document.querySelector(`#category-form [data-error-for="${field}"], #limits-form [data-error-for="${field}"]`);
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

export function initCategories(provider) {
  getData = provider;
  $("category-add").addEventListener("click", () => openDialog(null));
  $("category-form").addEventListener("submit", submitCategory);
  $("category-cancel").addEventListener("click", () => $("category-dialog").close());
  $("limits-form").addEventListener("submit", submitLimits);
  $("limits-cancel").addEventListener("click", () => $("limits-dialog").close());
  $("category-unassigned").addEventListener("change", async (event) => {
    await run("unassigned", () => apiFetch(`${childPath()}/unassigned-category`, { method: "PUT", body: { category_id: event.target.value } }));
  });
}
