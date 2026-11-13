// Time limit rules (plan E3): one table per category, one dialog for add and edit.
// The form is checked here as well; an invalid form never reaches the backend.

import { apiFetch } from "./api.js";
import { confirmDialog } from "./dialog.js";
import { formatDuration } from "./format.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let getData = () => null;
let editing = null; // { categoryId, rule | null }

export function formatDays(days) {
  const sorted = [...days].sort((a, b) => a - b);
  if (sorted.length === 7) return t("rules.every_day");
  const name = (d) => t(`day.${d}`);
  const parts = [];
  for (let i = 0; i < sorted.length; ) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j += 1;
    parts.push(j - i >= 2 ? `${name(sorted[i])}–${name(sorted[j])}` : sorted.slice(i, j + 1).map(name).join(", "));
    i = j + 1;
  }
  return parts.join(", ");
}

const clock = (minute) => `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;

export function ruleSummary(rule) {
  return `${formatDays(rule.days)} · ${formatDuration(rule.minutes * 60000)}`;
}

function cell(content) {
  const td = document.createElement("td");
  if (content instanceof Node) td.append(content);
  else td.textContent = content;
  return td;
}

function button(label, onClick, className) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  b.dataset.changeControl = "";
  if (className) b.className = className;
  b.addEventListener("click", onClick);
  return b;
}

function details(rule) {
  const bits = [];
  if (rule.start !== null) bits.push(t("rules.window").replace("{start}", clock(rule.start)).replace("{end}", clock(rule.end)));
  if (rule.session_minutes) bits.push(t("rules.session_text").replace("{session}", rule.session_minutes).replace("{pause}", rule.pause_minutes ?? 0));
  if (rule.per_day) bits.push(t("rules.per_day"));
  if (rule.expires_at) bits.push(t("rules.expires").replace("{date}", new Date(rule.expires_at).toLocaleDateString()));
  if (rule.off_today) bits.push(t("rules.off_until").replace("{time}", new Date(rule.off_today.restore_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })));
  if (!rule.on_server) bits.push(t("child.not_on_server"));
  return bits.join(" · ");
}

export function renderRules(data) {
  const list = $("rules-list");
  const categories = data.categories.filter((c) => c.on_server);
  $("rules-empty").hidden = categories.length > 0;
  list.replaceChildren(
    ...categories.map((category) => {
      const section = document.createElement("section");
      section.className = "rule-section";
      section.dataset.categoryId = category.id;
      const heading = document.createElement("h3");
      heading.append(category.title, button(t("rules.add"), () => openDialog(category.id, null), "secondary add-rule"));
      section.append(heading);
      if (category.rules.length === 0) {
        const none = document.createElement("p");
        none.className = "muted";
        none.textContent = t("rules.none");
        section.append(none);
        return section;
      }
      const table = document.createElement("table");
      const body = document.createElement("tbody");
      for (const rule of category.rules) {
        const row = document.createElement("tr");
        row.dataset.ruleId = rule.id;
        const actions = document.createElement("td");
        actions.className = "rule-actions";
        if (rule.on_server) {
          const off = Boolean(rule.off_today);
          const today = button(t(off ? "rules.on_again" : "rules.off_today"), () => toggleToday(rule), "secondary off-today");
          if (!off && !rule.applies_today) {
            today.disabled = true;
            today.dataset.keepDisabled = "";
            today.title = t("rules.not_today");
          }
          actions.append(
            today,
            button(t("rules.edit"), () => openDialog(category.id, rule), "secondary edit-rule"),
            button(t("rules.delete"), () => removeRule(rule), "secondary delete-rule"),
          );
        }
        row.append(cell(ruleSummary(rule)), cell(details(rule)), actions);
        body.append(row);
      }
      table.append(body);
      const wrap = document.createElement("div");
      wrap.className = "table-wrap";
      wrap.append(table);
      section.append(wrap);
      return section;
    }),
  );
}

// -- dialog -------------------------------------------------------------------------------------------------------------
function setError(field, message) {
  const span = document.querySelector(`[data-error-for="${field}"]`);
  if (!span) return;
  span.textContent = message ?? "";
  span.hidden = !message;
}

function clearErrors() {
  for (const span of document.querySelectorAll("#rule-form .field-error")) {
    span.textContent = "";
    span.hidden = true;
  }
  $("rule-error").hidden = true;
}

function openDialog(categoryId, rule) {
  editing = { categoryId, rule };
  clearErrors();
  $("rule-title").textContent = t(rule ? "rules.title_edit" : "rules.title_add");
  for (const box of document.querySelectorAll('#rule-form input[name="day"]')) {
    box.checked = rule ? rule.days.includes(Number(box.value)) : Number(box.value) < 5;
  }
  $("rule-minutes").value = rule ? String(rule.minutes) : "60";
  $("rule-start").value = rule && rule.start !== null ? clock(rule.start) : "";
  $("rule-end").value = rule && rule.end !== null ? clock(rule.end) : "";
  $("rule-session").value = rule && rule.session_minutes ? String(rule.session_minutes) : "";
  $("rule-pause").value = rule && rule.pause_minutes ? String(rule.pause_minutes) : "";
  $("rule-per-day").checked = Boolean(rule && rule.per_day);
  $("rule-extra").checked = Boolean(rule && rule.extra_time);
  $("rule-dialog").showModal();
  $("rule-minutes").focus();
}

const whole = (text) => (/^\d+$/.test(text.trim()) ? Number(text) : null);

/** Reads and checks the form. Returns { body } or { errors: {field: key} }. */
export function readForm() {
  const errors = {};
  const days = [...document.querySelectorAll('#rule-form input[name="day"]:checked')].map((b) => Number(b.value));
  if (days.length === 0) errors.days = "rules.err.days";
  const minutes = whole($("rule-minutes").value);
  if (minutes === null || minutes > 1440) errors.minutes = "rules.err.number";
  const start = $("rule-start").value;
  const end = $("rule-end").value;
  if (Boolean(start) !== Boolean(end)) errors[start ? "end" : "start"] = "rules.err.both_times";
  else if (start && end && start > end) errors.end = "rules.err.end_before_start";
  const sessionText = $("rule-session").value.trim();
  const pauseText = $("rule-pause").value.trim();
  const session = sessionText === "" ? null : whole(sessionText);
  const pause = pauseText === "" ? null : whole(pauseText);
  if (sessionText !== "" && (session === null || session > 1440)) errors.session_minutes = "rules.err.number";
  if (pauseText !== "" && (pause === null || pause > 1440)) errors.pause_minutes = "rules.err.number";
  if (!errors.session_minutes && !errors.pause_minutes && (session === null) !== (pause === null)) {
    errors[session === null ? "session_minutes" : "pause_minutes"] = "rules.err.both_session";
  }
  if (Object.keys(errors).length) return { errors };
  return {
    body: {
      days,
      minutes,
      start: start || null,
      end: end || null,
      session_minutes: session,
      pause_minutes: pause,
      per_day: $("rule-per-day").checked,
      extra_time: $("rule-extra").checked,
    },
  };
}

async function submit(event) {
  event.preventDefault();
  clearErrors();
  const { body, errors } = readForm();
  if (errors) {
    for (const [field, key] of Object.entries(errors)) setError(field, t(key));
    return;
  }
  const save = $("rule-save");
  save.disabled = true;
  try {
    const { categoryId, rule } = editing;
    const childId = $("child-page").dataset.childId;
    if (rule) await apiFetch(`/api/children/${encodeURIComponent(childId)}/rules/${encodeURIComponent(rule.id)}`, { method: "PUT", body });
    else await apiFetch(`/api/children/${encodeURIComponent(childId)}/categories/${encodeURIComponent(categoryId)}/rules`, { method: "POST", body });
    $("rule-dialog").close();
  } catch (error) {
    if (error.field && document.querySelector(`[data-error-for="${error.field}"]`)) setError(error.field, error.message);
    else {
      $("rule-error").textContent = t(`error.${error.code}`);
      $("rule-error").hidden = false;
    }
  } finally {
    save.disabled = false;
    document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
  }
}

async function removeRule(rule) {
  const yes = await confirmDialog({ title: t("rules.delete.title"), message: `${ruleSummary(rule)}. ${t("rules.delete.text")}`, confirmLabel: t("rules.delete"), danger: true });
  if (!yes) return;
  $("rules-error").hidden = true;
  try {
    await apiFetch(`/api/children/${encodeURIComponent($("child-page").dataset.childId)}/rules/${encodeURIComponent(rule.id)}`, { method: "DELETE" });
  } catch (error) {
    $("rules-error").textContent = t(`error.${error.code}`);
    $("rules-error").hidden = false;
  }
  document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
}

async function toggleToday(rule) {
  $("rules-error").hidden = true;
  const url = `/api/children/${encodeURIComponent($("child-page").dataset.childId)}/rules/${encodeURIComponent(rule.id)}/off-today`;
  try {
    await apiFetch(url, { method: rule.off_today ? "DELETE" : "PUT" });
  } catch (error) {
    $("rules-error").textContent = error.field === "rule" ? error.message : t(`error.${error.code}`);
    $("rules-error").hidden = false;
  }
  document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
}

export function initRules(provider) {
  getData = provider;
  $("rule-form").addEventListener("submit", submit);
  $("rule-cancel").addEventListener("click", () => $("rule-dialog").close());
}
