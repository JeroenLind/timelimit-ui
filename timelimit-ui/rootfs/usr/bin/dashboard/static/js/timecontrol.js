// Extra time for today and temporary blocking per category (plan E8, FR-500..504).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { formatDuration } from "./format.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let categoryId = null;
let lookup = () => null;

const base = () => `/api/children/${encodeURIComponent($("child-page").dataset.childId)}/categories/${encodeURIComponent(categoryId)}`;

function clock(ms) {
  return new Date(ms).toLocaleTimeString(document.documentElement.lang || undefined, { hour: "2-digit", minute: "2-digit" });
}

function summary() {
  const category = lookup(categoryId);
  if (!category) return;
  const extra = category.extra_time_ms ? formatDuration(category.extra_time_ms) : t("time.none");
  const parts = [t("time.summary_extra").replace("{time}", extra)];
  if (category.temp_blocked) {
    parts.push(category.temp_blocked_until ? t("time.summary_blocked_until").replace("{time}", clock(category.temp_blocked_until)) : t("time.summary_blocked"));
  }
  $("time-summary").textContent = parts.join(" \u2022 ");
  $("block-end").disabled = !category.temp_blocked;
  if (!category.temp_blocked) $("block-end").dataset.keepDisabled = "";
  else delete $("block-end").dataset.keepDisabled;
}

async function send(path, method, body) {
  $("time-error").hidden = true;
  try {
    await track(() => apiFetch(`${base()}/${path}`, { method, body }));
  } catch (error) {
    $("time-error").textContent = error.field ? error.message : t(`error.${error.code}`);
    $("time-error").hidden = false;
  } finally {
    document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
  }
}

const minutes = (id) => Number($(id).value);
const extra = (mode, value) => send("extra-time", "PUT", { mode, minutes: value });
const block = (value) => send("temp-block", "PUT", { minutes: value });

/** Called after every redraw of the child page, so an open dialog follows the data. */
export function refreshTime() {
  if ($("time-dialog").open) summary();
}

export function openTime(category, find) {
  categoryId = category.id;
  lookup = find;
  $("time-title").textContent = t("time.title").replace("{name}", category.title);
  $("time-error").hidden = true;
  summary();
  $("time-dialog").showModal();
}

export function initTimeControl() {
  $("time-close").addEventListener("click", () => $("time-dialog").close());
  for (const button of $("time-dialog").querySelectorAll("[data-extra-add]")) {
    button.addEventListener("click", () => extra("add", Number(button.dataset.extraAdd)));
  }
  for (const button of $("time-dialog").querySelectorAll("[data-block]")) {
    button.addEventListener("click", () => block(Number(button.dataset.block)));
  }
  $("time-add").addEventListener("click", () => extra("add", minutes("time-minutes")));
  $("time-subtract").addEventListener("click", () => extra("subtract", minutes("time-minutes")));
  $("time-reset").addEventListener("click", () => extra("set", 0));
  $("block-custom").addEventListener("click", () => block(minutes("block-minutes")));
  $("block-end").addEventListener("click", () => send("temp-block", "DELETE"));
}
