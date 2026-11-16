// Used time: today per category against the limit, and the history per day as bars and a list (plan E9, FR-600, FR-601).

import { apiFetch } from "./api.js";
import { formatDuration } from "./format.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";
let data = null;

const visible = () => !$("panel-usage").hidden;

function svg(name, attrs = {}) {
  const el = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}

function shortDate(iso) {
  const [, month, day] = iso.split("-");
  return `${Number(day)}-${Number(month)}`;
}

function renderToday() {
  const body = $("usage-today");
  body.replaceChildren(
    ...data.categories.map((category) => {
      const row = document.createElement("tr");
      row.dataset.categoryId = category.id;
      const name = document.createElement("td");
      name.textContent = category.title;
      const used = document.createElement("td");
      used.textContent = formatDuration(category.used_today_ms);
      const limit = document.createElement("td");
      const allowed = category.limit_today_ms === null ? null : category.limit_today_ms + category.extra_time_ms;
      limit.textContent = allowed === null ? t("usage.no_limit") : formatDuration(allowed);
      const bar = document.createElement("td");
      if (allowed) {
        const meter = document.createElement("progress");
        meter.max = allowed;
        meter.value = Math.min(category.used_today_ms, allowed);
        meter.className = category.used_today_ms > allowed ? "over" : "";
        meter.setAttribute("aria-label", `${category.title}: ${formatDuration(category.used_today_ms)} / ${formatDuration(allowed)}`);
        bar.append(meter);
      }
      row.append(name, used, limit, bar);
      return row;
    }),
  );
  $("usage-empty").hidden = data.categories.length > 0;
  $("usage-content").hidden = data.categories.length === 0;
}

function renderHistory() {
  const category = data.categories.find((c) => c.id === $("usage-category").value);
  if (!category) return;
  const days = Number($("usage-range").value);
  const rows = category.history.slice(-days);
  const peak = Math.max(1, ...rows.map((r) => r.used_ms));
  const width = 40;
  const height = 160;
  const chart = svg("svg", { viewBox: `0 0 ${rows.length * width} ${height + 24}`, role: "img", class: "usage-chart" });
  chart.setAttribute("aria-label", t("usage.chart").replace("{name}", category.title));
  rows.forEach((row, i) => {
    const h = Math.round((row.used_ms / peak) * height);
    const bar = svg("rect", { x: i * width + 6, y: height - h, width: width - 12, height: h, class: "usage-bar" });
    const tip = svg("title");
    tip.textContent = `${row.date}: ${formatDuration(row.used_ms)}`;
    bar.append(tip);
    chart.append(bar);
    if (rows.length <= 7 || i % 5 === 0 || i === rows.length - 1) {
      const label = svg("text", { x: i * width + width / 2, y: height + 16, "text-anchor": "middle", class: "usage-label" });
      label.textContent = shortDate(row.date);
      chart.append(label);
    }
  });
  $("usage-chart").replaceChildren(chart);
  $("usage-history").replaceChildren(
    ...[...rows].reverse().map((row) => {
      const tr = document.createElement("tr");
      const date = document.createElement("td");
      date.textContent = row.date;
      const used = document.createElement("td");
      used.textContent = formatDuration(row.used_ms);
      tr.append(date, used);
      return tr;
    }),
  );
}

function render() {
  const select = $("usage-category");
  const previous = select.value;
  select.replaceChildren(...data.categories.map((c) => new Option(c.title, c.id)));
  if (data.categories.some((c) => c.id === previous)) select.value = previous;
  renderToday();
  renderHistory();
}

async function load() {
  try {
    data = await apiFetch(`/api/children/${encodeURIComponent($("child-page").dataset.childId)}/usage`);
    $("usage-error").hidden = true;
    render();
  } catch (error) {
    $("usage-error").textContent = t(`error.${error.code}`);
    $("usage-error").hidden = false;
  }
}

export function initUsage() {
  $("tab-usage").addEventListener("click", load);
  $("usage-category").addEventListener("change", () => data && renderHistory());
  $("usage-range").addEventListener("change", () => data && renderHistory());
  document.addEventListener("dashboard:changed", () => visible() && load());
  document.addEventListener("dashboard:language", () => data && visible() && render());
}
