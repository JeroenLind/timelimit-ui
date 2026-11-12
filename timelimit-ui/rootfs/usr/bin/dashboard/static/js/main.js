import { configureApi } from "./api.js";
import { startConnection } from "./connection.js";
import { initI18n, languageChoice, setLanguage } from "./i18n.js";
import { initNav } from "./nav.js";
import { initChild, refreshChild } from "./child.js";
import { startEvents } from "./events.js";
import { refreshNotices } from "./notices.js";
import { refreshOverview } from "./overview.js";
import { initSettings } from "./settings.js";
import { applyTheme, readPref, THEMES, writePref } from "./prefs.js";

const timings = JSON.parse(document.getElementById("timings").textContent);
configureApi(timings);

initNav();

applyTheme(readPref("theme", THEMES));
for (const link of document.querySelectorAll(".nav-link")) {
  if (link.getAttribute("href") === window.location.pathname) link.setAttribute("aria-current", "page");
}

const themeSelect = document.getElementById("theme-select");
if (themeSelect) {
  themeSelect.value = readPref("theme", THEMES);
  themeSelect.addEventListener("change", () => {
    writePref("theme", themeSelect.value);
    applyTheme(themeSelect.value);
  });
}

const languageSelect = document.getElementById("language-select");
if (languageSelect) {
  languageSelect.value = languageChoice();
  languageSelect.addEventListener("change", () => setLanguage(languageSelect.value));
}

const refresh = document.getElementById("refresh-overview");
if (refresh) refresh.addEventListener("click", refreshOverview);

if (document.getElementById("child-page")) initChild();
await initI18n();
const onSettings = Boolean(document.getElementById("settings-page"));
const onChild = Boolean(document.getElementById("child-page"));
// Every page reads from the cache, so it works while the server is down.
const refreshPage = async () => {
  if (onChild) await refreshChild();
  else if (!onSettings) await refreshOverview();
};
if (onSettings) await initSettings();

await refreshPage();
await refreshNotices();
document.addEventListener("dashboard:changed", () => {
  refreshPage();
  refreshNotices();
});
startEvents();
await startConnection(timings, {
  onBack: async () => {
    await refreshPage();
    await refreshNotices();
  },
});
