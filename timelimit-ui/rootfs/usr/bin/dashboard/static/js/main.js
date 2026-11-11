import { configureApi } from "./api.js";
import { startConnection } from "./connection.js";
import { initI18n, languageChoice, setLanguage } from "./i18n.js";
import { initNav } from "./nav.js";
import { refreshOverview } from "./overview.js";
import { applyTheme, readPref, THEMES, writePref } from "./prefs.js";

const timings = JSON.parse(document.getElementById("timings").textContent);
configureApi(timings);

initNav();

const themeSelect = document.getElementById("theme-select");
themeSelect.value = readPref("theme", THEMES);
applyTheme(themeSelect.value);
themeSelect.addEventListener("change", () => {
  writePref("theme", themeSelect.value);
  applyTheme(themeSelect.value);
});

const languageSelect = document.getElementById("language-select");
languageSelect.value = languageChoice();
languageSelect.addEventListener("change", () => setLanguage(languageSelect.value));

document.getElementById("refresh-overview").addEventListener("click", refreshOverview);

await initI18n();
await refreshOverview(); // from the cache: works while the server is down
await startConnection(timings, { onBack: refreshOverview });
