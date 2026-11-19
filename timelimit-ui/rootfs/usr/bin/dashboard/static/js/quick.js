// Quick actions on the overview: extra time or a temporary block for one category (plan G2, FR-700).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let child = null;

const path = (suffix) =>
  `/api/children/${encodeURIComponent(child.id)}/categories/${encodeURIComponent($("quick-category").value)}/${suffix}`;

async function send(suffix, method, body) {
  $("quick-error").hidden = true;
  $("quick-done").hidden = true;
  try {
    await track(() => apiFetch(path(suffix), { method, body }));
    $("quick-done").hidden = false;
  } catch (error) {
    $("quick-error").textContent = error.field ? error.message : t(`error.${error.code}`);
    $("quick-error").hidden = false;
  } finally {
    document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
  }
}

export function openQuick(summary) {
  child = summary;
  $("quick-title").textContent = t("overview.quick.title").replace("{name}", summary.name);
  $("quick-category").replaceChildren(
    ...summary.categories_brief.map((c) => {
      const option = document.createElement("option");
      option.value = c.id;
      option.textContent = c.title;
      return option;
    }),
  );
  $("quick-error").hidden = true;
  $("quick-done").hidden = true;
  $("quick-dialog").showModal();
}

export function initQuick() {
  if (!$("quick-dialog")) return; // not the overview page
  $("quick-close").addEventListener("click", () => $("quick-dialog").close());
  for (const button of $("quick-dialog").querySelectorAll("[data-quick-extra]")) {
    button.addEventListener("click", () => send("extra-time", "PUT", { mode: "add", minutes: Number(button.dataset.quickExtra) }));
  }
  for (const button of $("quick-dialog").querySelectorAll("[data-quick-block]")) {
    button.addEventListener("click", () => send("temp-block", "PUT", { minutes: Number(button.dataset.quickBlock) }));
  }
  $("quick-unblock").addEventListener("click", () => send("temp-block", "DELETE"));
}
