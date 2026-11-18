// Parents section of the settings page: Dashboard parent state and "change password" (plan E10, FR-901, FR-902).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let changing = null;

function fieldError(field, message) {
  for (const el of $("password-dialog").querySelectorAll("[data-error-for]")) {
    const match = el.dataset.errorFor === field;
    el.hidden = !match || !message;
    el.textContent = match ? message : "";
  }
}

function open(parent) {
  changing = parent;
  for (const id of ["pw-current", "pw-new", "pw-repeat"]) $(id).value = "";
  fieldError(null, "");
  $("pw-error").hidden = true;
  $("pw-title").textContent = t("parents.change.title").replace("{name}", parent.name);
  $("password-dialog").showModal();
  $("pw-current").focus();
}

async function submit(event) {
  event.preventDefault();
  fieldError(null, "");
  $("pw-error").hidden = true;
  if ($("pw-new").value !== $("pw-repeat").value) {
    fieldError("repeat_password", t("parents.change.mismatch"));
    return;
  }
  const body = { current_password: $("pw-current").value, new_password: $("pw-new").value };
  const target = changing;
  try {
    await track(() => apiFetch(`/api/parents/${encodeURIComponent(target.id)}/password`, { method: "POST", body }));
    $("password-dialog").close();
    $("parents-note").textContent = t("parents.changed").replace("{name}", target.name);
  } catch (error) {
    if (error.field) fieldError(error.field, error.message);
    else {
      $("pw-error").textContent = error.message || t(`error.${error.code}`);
      $("pw-error").hidden = false;
    }
  } finally {
    for (const id of ["pw-current", "pw-new", "pw-repeat"]) $(id).value = "";
  }
}

function render(data) {
  const state = data.dashboard.signed_in && data.dashboard.keep_signed_in ? "ok" : "out";
  $("parents-dashboard").dataset.state = state;
  $("parents-dashboard").textContent = t(state === "ok" ? "parents.dashboard.ok" : "parents.dashboard.out");
  $("parents-list").replaceChildren(
    ...data.parents.map((parent) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "card-title";
      name.textContent = parent.name;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.dataset.changeControl = "";
      button.textContent = t("parents.change");
      button.setAttribute("aria-label", `${t("parents.change")} ${parent.name}`);
      button.addEventListener("click", () => open(parent));
      li.append(name, button);
      return li;
    }),
  );
}

/** Shows the section only while the dashboard is linked (state "ready" or "registered"). */
export async function refreshParents(linkState) {
  const show = linkState === "ready" || linkState === "registered";
  $("parents-section").hidden = !show;
  if (!show) return;
  try {
    render(await apiFetch("/api/parents"));
  } catch {
    $("parents-section").hidden = true;
  }
}

export function initParents() {
  $("password-form-change").addEventListener("submit", submit);
  $("pw-cancel").addEventListener("click", () => $("password-dialog").close());
}
