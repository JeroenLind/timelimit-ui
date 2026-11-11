import { configureApi } from "./api.js";
import { startConnection } from "./connection.js";
import { initI18n, languageChoice, setLanguage } from "./i18n.js";
import { initNav } from "./nav.js";
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

await initI18n();
const onSettings = Boolean(document.getElementById("settings-page"));
if (onSettings) await initSettings();
else await refreshOverview(); // from the cache: works while the server is down
await refreshNotices();
await startConnection(timings, {
  onBack: async () => {
    if (!onSettings) await refreshOverview();
    await refreshNotices();
  },
});
