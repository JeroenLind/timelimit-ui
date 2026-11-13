// Every change shows its state: pending, confirmed, failed (UI-007, FR-209).

import { t } from "./i18n.js";

let clearTimer = null;

function show(state, text) {
  const box = document.getElementById("action-status");
  if (!box) return;
  clearTimeout(clearTimer);
  box.dataset.state = state;
  box.textContent = text;
  box.hidden = false;
  if (state === "confirmed") clearTimer = setTimeout(() => { box.hidden = true; }, 3000);
}

/** Runs `work` (a promise-returning function) and shows waiting, then done or the reason it failed. */
export async function track(work) {
  show("pending", t("action.pending"));
  try {
    const result = await work();
    show("confirmed", t("action.done"));
    return result;
  } catch (error) {
    if (error && error.code === "CONFLICT") {
      document.getElementById("action-status")?.setAttribute("hidden", "");
    } else {
      show("failed", `${t("action.failed")} ${error && error.message ? error.message : ""}`.trim());
    }
    throw error;
  }
}
