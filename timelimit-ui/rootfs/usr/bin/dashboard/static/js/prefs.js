// Theme and language choices of this browser. Stored in localStorage when it works (it can throw
// in private windows); the page works without it.

export const THEMES = ["auto", "light", "dark"];
export const LANGUAGES = ["auto", "nl", "en"];

export function readPref(name, allowed, fallback = "auto") {
  try {
    const value = localStorage.getItem(`dashboard.${name}`);
    return allowed.includes(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

export function writePref(name, value) {
  try {
    if (value === "auto") localStorage.removeItem(`dashboard.${name}`);
    else localStorage.setItem(`dashboard.${name}`, value);
  } catch {
    /* no storage: the choice lasts until the page closes */
  }
}

export function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.dataset.theme = theme;
  else delete root.dataset.theme;
}
