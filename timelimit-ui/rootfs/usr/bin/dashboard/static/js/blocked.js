// Weekly blocked times per category (plan E5, FR-304): a grid of half-hour cells, Monday first.
// Click or press Space toggles a cell, dragging with the mouse paints, arrow keys move.
// Minutes of the week as the server stores them: Monday 00:00 = 0, the end is exclusive.

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { confirmDialog } from "./dialog.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
const STEP = 30;
const PER_DAY = 1440 / STEP; // 48
const CELLS = 7 * PER_DAY;
let getData = () => null;
let selected = "";
let cells = new Set();
let dirty = false;
let version = "";
let painting = null; // true: block, false: clear, null: not painting
let focused = 0;
let handledByPointer = false;
let lastCell = 0;

const clock = (minute) => `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;

/** Cells touched by the intervals; a finer schedule made elsewhere is shown rounded outwards. */
export function cellsFromIntervals(intervals) {
  const result = new Set();
  for (const [start, end] of intervals) {
    for (let i = Math.floor(start / STEP); i < Math.ceil(end / STEP) && i < CELLS; i += 1) result.add(i);
  }
  return result;
}

/** Runs of neighbouring cells as `[start, end]` minutes of the week. */
export function intervalsFromCells(set) {
  const sorted = [...set].sort((a, b) => a - b);
  const result = [];
  for (const i of sorted) {
    const last = result[result.length - 1];
    if (last && last[1] === i * STEP) last[1] = (i + 1) * STEP;
    else result.push([i * STEP, (i + 1) * STEP]);
  }
  return result;
}

function categories() {
  const data = getData();
  return data ? data.categories.filter((c) => c.on_server) : [];
}

function current() {
  return categories().find((c) => c.id === selected) ?? null;
}

function load(category) {
  cells = cellsFromIntervals(category ? category.blocked_times : []);
  version = category ? category.blocked_version : "";
  dirty = false;
}

function markDirty(value) {
  dirty = value;
  for (const id of ["blocked-save", "blocked-reset"]) {
    const button = $(id);
    button.disabled = !dirty;
    // connection.js re-enables change controls when the server is back; this one stays off while clean
    if (dirty) delete button.dataset.keepDisabled;
    else button.dataset.keepDisabled = "";
  }
}

function paint(index, on) {
  if (on) cells.add(index);
  else cells.delete(index);
  const button = $("blocked-grid").querySelector(`[data-cell="${index}"]`);
  if (button) button.setAttribute("aria-pressed", String(on));
  markDirty(true);
}

function buildGrid() {
  const grid = $("blocked-grid");
  grid.replaceChildren();
  const head = document.createElement("div");
  head.className = "blocked-row blocked-head";
  head.append(document.createElement("span"));
  for (let h = 0; h < 24; h += 3) {
    const label = document.createElement("span");
    label.className = "blocked-hour";
    label.textContent = clock(h * 60);
    head.append(label);
  }
  grid.append(head);
  for (let day = 0; day < 7; day += 1) {
    const row = document.createElement("div");
    row.className = "blocked-row";
    row.setAttribute("role", "row");
    const name = document.createElement("span");
    name.className = "blocked-day";
    name.textContent = t(`day.${day}`);
    row.append(name);
    for (let slot = 0; slot < PER_DAY; slot += 1) {
      const index = day * PER_DAY + slot;
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "blocked-cell";
      cell.dataset.cell = String(index);
      cell.dataset.changeControl = "";
      cell.tabIndex = index === focused ? 0 : -1;
      cell.setAttribute("aria-pressed", String(cells.has(index)));
      cell.setAttribute("aria-label", t("blocked.cell_label").replace("{day}", t(`day.${day}`)).replace("{time}", clock(slot * STEP)));
      cell.addEventListener("pointerdown", (event) => {
        if (event.pointerType === "touch" || event.button !== 0) return;
        event.preventDefault();
        cell.focus();
        handledByPointer = true;
        lastCell = index;
        painting = !cells.has(index);
        paint(index, painting);
      });
      cell.addEventListener("click", () => {
        // a mouse press was already handled on pointerdown; touch taps and the keyboard arrive here
        if (handledByPointer) {
          handledByPointer = false;
          return;
        }
        paint(index, !cells.has(index));
      });
      cell.addEventListener("focus", () => {
        focused = index;
      });
      cell.addEventListener("keydown", (event) => moveFocus(event, index));
      row.append(cell);
    }
    const tools = document.createElement("span");
    tools.className = "blocked-tools";
    for (const [key, on] of [["blocked.day_block", true], ["blocked.day_clear", false]]) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "secondary small";
      b.dataset.changeControl = "";
      b.textContent = t(key);
      b.setAttribute("aria-label", `${t(key)} ${t(`day.${day}`)}`);
      b.addEventListener("click", () => {
        for (let slot = 0; slot < PER_DAY; slot += 1) paint(day * PER_DAY + slot, on);
      });
      tools.append(b);
    }
    row.append(tools);
    grid.append(row);
  }
}

function moveFocus(event, index) {
  const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -PER_DAY, ArrowDown: PER_DAY }[event.key];
  if (step === undefined) return;
  const next = index + step;
  if (next < 0 || next >= CELLS) return;
  event.preventDefault();
  const target = $("blocked-grid").querySelector(`[data-cell="${next}"]`);
  const old = $("blocked-grid").querySelector(`[data-cell="${index}"]`);
  old.tabIndex = -1;
  target.tabIndex = 0;
  target.focus();
}

export function renderBlocked(data) {
  const list = categories();
  $("blocked-empty").hidden = list.length > 0;
  $("blocked-editor").hidden = list.length === 0;
  const select = $("blocked-category");
  if (!list.some((c) => c.id === selected)) {
    selected = list[0] ? list[0].id : "";
    dirty = false;
  }
  select.replaceChildren(
    ...list.map((c) => {
      const option = document.createElement("option");
      option.value = c.id;
      option.textContent = c.title;
      return option;
    }),
  );
  select.value = selected;
  if (!dirty) load(current());
  buildGrid();
  markDirty(dirty);
  void data;
}

async function save() {
  const category = current();
  if (!category) return;
  const url = `/api/children/${encodeURIComponent($("child-page").dataset.childId)}/categories/${encodeURIComponent(category.id)}/blocked-times`;
  const intervals = intervalsFromCells(cells);
  $("blocked-error").hidden = true;
  const send = (check) => track(() => apiFetch(url, { method: "PUT", body: check ? { intervals, version } : { intervals } }));
  try {
    await send(true);
  } catch (error) {
    if (error.code === "CONFLICT") {
      const yes = await confirmDialog({ title: t("blocked.conflict.title"), message: t("blocked.conflict.text"), confirmLabel: t("blocked.conflict.confirm"), danger: true });
      if (!yes) return;
      try {
        await send(false);
      } catch (again) {
        fail(again);
        return;
      }
    } else {
      fail(error);
      return;
    }
  }
  dirty = false;
  document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type: "local" } }));
}

function fail(error) {
  $("blocked-error").textContent = error.field === "intervals" ? error.message : t(`error.${error.code}`);
  $("blocked-error").hidden = false;
}

export function initBlocked(provider) {
  getData = provider;
  document.addEventListener("pointermove", (event) => {
    if (painting === null) return;
    const under = document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-cell]");
    if (!under) return;
    // a fast drag skips cells: paint everything between the last cell and this one
    const to = Number(under.dataset.cell);
    const [low, high] = to < lastCell ? [to, lastCell] : [lastCell, to];
    for (let i = low; i <= high; i += 1) if (cells.has(i) !== painting) paint(i, painting);
    lastCell = to;
  });
  document.addEventListener("pointerup", () => {
    painting = null;
    setTimeout(() => {
      handledByPointer = false;
    }, 0);
  });
  $("blocked-category").addEventListener("change", async (event) => {
    if (dirty) {
      const yes = await confirmDialog({ title: t("blocked.discard.title"), message: t("blocked.discard"), confirmLabel: t("blocked.discard.confirm"), danger: true });
      if (!yes) {
        event.target.value = selected;
        return;
      }
    }
    selected = event.target.value;
    dirty = false;
    load(current());
    buildGrid();
    markDirty(false);
  });
  $("blocked-save").addEventListener("click", save);
  $("blocked-reset").addEventListener("click", () => {
    load(current());
    buildGrid();
    markDirty(false);
  });
}
