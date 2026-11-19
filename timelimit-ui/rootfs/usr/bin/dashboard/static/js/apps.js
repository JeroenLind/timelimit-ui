// Apps of a category: assign and remove (plan E7, FR-403..405).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { confirmDialog } from "./dialog.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let category = null;
let overview = { known: false, apps: [] };

const childPath = () => `/api/children/${encodeURIComponent($("child-page").dataset.childId)}`;

function row(app, checked = false) {
  const label = document.createElement("label");
  label.className = "check app-row";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.value = app.package;
  input.checked = checked;
  const text = document.createElement("span");
  text.textContent = app.title === app.package ? app.package : `${app.title} (${app.package})`;
  label.append(input, text);
  if (app.category_id && app.category_id !== category.id) {
    const note = document.createElement("span");
    note.className = "muted";
    note.textContent = ` \u2013 ${t("apps.moves").replace("{category}", app.category_title ?? "")}`;
    label.append(note);
  }
  return label;
}

function render() {
  const mine = overview.apps.filter((a) => a.category_id === category.id);
  const others = overview.apps.filter((a) => a.category_id !== category.id);
  $("apps-unknown").hidden = overview.known;
  $("apps-assigned").replaceChildren(...mine.map((a) => row(a)));
  $("apps-assigned").dataset.empty = mine.length === 0 ? t("apps.none") : "";
  $("apps-remove").disabled = mine.length === 0;
  if (mine.length === 0) $("apps-remove").dataset.keepDisabled = "";
  else delete $("apps-remove").dataset.keepDisabled;
  const query = $("apps-search").value.trim().toLowerCase();
  const shown = others.filter((a) => !query || a.title.toLowerCase().includes(query) || a.package.toLowerCase().includes(query));
  const keep = new Set([...$("apps-available").querySelectorAll("input:checked")].map((i) => i.value));
  $("apps-available").replaceChildren(...shown.map((a) => row(a, keep.has(a.package))));
}

async function load() {
  overview = await apiFetch(`${childPath()}/apps`);
  render();
}

async function send(part, packages) {
  $("apps-error").hidden = true;
  try {
    await track(() => apiFetch(`${childPath()}/categories/${encodeURIComponent(category.id)}/apps${part}`, { method: "POST", body: { packages } }));
  } catch (error) {
    $("apps-error").textContent = error.field ? error.message : t(`error.${error.code}`);
    $("apps-error").hidden = false;
    return;
  } finally {
    document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
  }
  $("apps-manual").value = "";
  await load();
}

const checked = (id) => [...$(id).querySelectorAll("input:checked")].map((i) => i.value);

export async function openApps(selected) {
  category = selected;
  $("apps-title").textContent = t("apps.title").replace("{name}", selected.title);
  $("apps-error").hidden = true;
  $("apps-search").value = "";
  $("apps-manual").value = "";
  overview = { known: false, apps: [] };
  render();
  $("apps-dialog").showModal();
  try {
    await load();
  } catch (error) {
    $("apps-error").textContent = t(`error.${error.code}`);
    $("apps-error").hidden = false;
  }
}

export function initApps() {
  $("apps-close").addEventListener("click", () => $("apps-dialog").close());
  $("apps-search").addEventListener("input", render);
  $("apps-remove").addEventListener("click", async () => {
    const packages = checked("apps-assigned");
    if (!packages.length) return;
    // UI-006: taking apps out of a category asks first
    const yes = await confirmDialog({
      title: t("apps.remove.title"),
      message: t("apps.remove.text").replace("{count}", String(packages.length)).replace("{category}", category.title),
      confirmLabel: t("apps.remove"),
      danger: true,
    });
    if (yes) send("/remove", packages);
  });
  $("apps-add").addEventListener("click", () => {
    const manual = $("apps-manual").value.split(/\s+/).filter(Boolean);
    const packages = [...new Set([...checked("apps-available"), ...manual])];
    if (!packages.length) {
      $("apps-error").textContent = t("apps.choose");
      $("apps-error").hidden = false;
      return;
    }
    send("", packages);
  });
}
