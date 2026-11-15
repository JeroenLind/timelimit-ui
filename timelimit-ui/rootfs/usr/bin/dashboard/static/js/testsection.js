// The test section: add family members, look into the database (plan E11, FR-800, FR-801).

import { track } from "./actions.js";
import { apiFetch } from "./api.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);
let known = [];
const pending = [];

function show(list) {
  const items = [...list, ...pending];
  $("test-users").replaceChildren(
    ...items.map((user) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "card-title";
      name.textContent = user.name;
      const kind = document.createElement("span");
      kind.className = "badge";
      kind.textContent = user.type === "parent" ? t("test.parent") : t("test.child");
      li.append(name, kind);
      if (user.pending) {
        li.dataset.pending = "";
        const wait = document.createElement("span");
        wait.className = "muted";
        wait.textContent = ` ${t("rules.waiting")}`;
        li.append(wait);
      }
      return li;
    }),
  );
}

async function load() {
  known = (await apiFetch("/api/test/users")).users;
  show(known);
}

function setError(field, message) {
  for (const el of document.querySelectorAll("#test-form [data-error-for]")) {
    const match = el.dataset.errorFor === field;
    el.hidden = !match;
    el.textContent = match ? message : "";
  }
}

function initPage() {
  const type = $("test-type");
  type.addEventListener("change", () => {
    $("test-password-field").hidden = type.value !== "parent";
  });
  $("test-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    setError(null, "");
    $("test-error").hidden = true;
    const body = { type: type.value, name: $("test-name").value, time_zone: $("test-zone").value };
    if (type.value === "parent") body.password = $("test-password").value;
    const entry = { name: body.name.trim() || "?", type: body.type, pending: true };
    pending.push(entry);
    show(known);
    try {
      await track(() => apiFetch("/api/test/users", { method: "POST", body }));
      $("test-name").value = "";
      $("test-password").value = "";
    } catch (error) {
      if (error.field) setError(error.field, error.message);
      else {
        $("test-error").textContent = error.message || t(`error.${error.code}`);
        $("test-error").hidden = false;
      }
    } finally {
      pending.splice(pending.indexOf(entry), 1);
      try {
        await load();
      } catch {
        show(known);
      }
    }
  });
  document.addEventListener("dashboard:changed", () => load().catch(() => {}));
  load().catch(() => {});
}

async function initDatabase() {
  try {
    const data = await apiFetch("/api/test/database");
    $("database-tables").replaceChildren(
      ...data.tables.map((table) => {
        const box = document.createElement("details");
        box.dataset.table = table.name;
        const head = document.createElement("summary");
        head.textContent = `${table.name} (${table.total})`;
        const grid = document.createElement("table");
        const top = document.createElement("tr");
        for (const column of table.columns) {
          const th = document.createElement("th");
          th.textContent = column;
          top.append(th);
        }
        grid.append(top);
        for (const row of table.rows) {
          const tr = document.createElement("tr");
          for (const value of row) {
            const td = document.createElement("td");
            td.textContent = value === null ? "" : String(value);
            tr.append(td);
          }
          grid.append(tr);
        }
        const scroll = document.createElement("div");
        scroll.className = "table-scroll";
        scroll.append(grid);
        box.append(head, scroll);
        return box;
      }),
    );
  } catch (error) {
    $("database-error").textContent = t(`error.${error.code}`);
    $("database-error").hidden = false;
  }
}

export function initTestSection() {
  if ($("test-page")) initPage();
  if ($("database-page")) initDatabase();
}
