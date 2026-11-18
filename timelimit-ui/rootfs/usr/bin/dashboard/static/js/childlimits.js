// All limits of a child off until a chosen time (plan E13, FR-505).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
const childPath = () => `/api/children/${encodeURIComponent($("child-page").dataset.childId)}`;
let busy = false;
let until = null;

function showState() {
  const on = until !== null;
  $("child-limits-state").textContent = busy
    ? t("rules.waiting")
    : on
      ? t("childlimits.until").replace("{time}", new Date(until).toLocaleString())
      : t("childlimits.none");
  $("child-limits-off").hidden = on;
  $("child-limits-on").hidden = !on;
  for (const b of [$("child-limits-off"), $("child-limits-on")]) {
    if (busy) {
      b.disabled = true;
      b.dataset.keepDisabled = "";
    } else {
      delete b.dataset.keepDisabled;
      b.disabled = false;
    }
  }
}

export function renderChildLimits(child) {
  until = child.limits_disabled_until ?? null;
  showState();
}

function fieldError(message) {
  const span = document.querySelector('#child-limits-form [data-error-for="child_limit_minutes"]');
  span.textContent = message ?? "";
  span.hidden = !message;
}

async function send(minutes) {
  $("child-limits-error").hidden = true;
  busy = true;
  showState();
  try {
    await track(() => apiFetch(`${childPath()}/disable-limits`, { method: "PUT", body: { minutes } }));
  } catch (error) {
    $("child-limits-error").textContent = error.field ? error.message : t(`error.${error.code}`);
    $("child-limits-error").hidden = false;
  } finally {
    busy = false;
    document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
    showState();
  }
}

export function initChildLimits() {
  $("child-limits-off").addEventListener("click", () => {
    fieldError("");
    $("child-limits-dialog").showModal();
    $("child-limits-minutes").focus();
  });
  $("child-limits-on").addEventListener("click", () => send(0));
  $("child-limits-cancel").addEventListener("click", () => $("child-limits-dialog").close());
  for (const b of document.querySelectorAll("[data-child-limit-minutes]")) {
    b.addEventListener("click", () => {
      $("child-limits-minutes").value = b.dataset.childLimitMinutes;
    });
  }
  $("child-limits-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const minutes = Number($("child-limits-minutes").value);
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 10080) {
      fieldError(t("categories.limits.invalid"));
      return;
    }
    $("child-limits-dialog").close();
    await send(minutes);
  });
}
