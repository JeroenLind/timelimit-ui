import { configureApi } from "./api.js";
import { startConnection } from "./connection.js";
import { initI18n } from "./i18n.js";
import { refreshOverview } from "./overview.js";

const timings = JSON.parse(document.getElementById("timings").textContent);
configureApi(timings);

const toggle = document.getElementById("menu-toggle");
const sidebar = document.getElementById("sidebar");
toggle.addEventListener("click", () => {
  const open = sidebar.dataset.open !== "true";
  sidebar.dataset.open = String(open);
  toggle.setAttribute("aria-expanded", String(open));
});

document.getElementById("refresh-overview").addEventListener("click", refreshOverview);

await initI18n();
await refreshOverview(); // from the cache: works while the server is down
await startConnection(timings, { onBack: refreshOverview });
