// Texts come from /static/i18n/<lang>.json; a missing key falls back to English (TR-311).

let current = {};
let fallback = {};

async function load(lang) {
  const response = await fetch(`/static/i18n/${lang}.json`);
  return response.ok ? response.json() : {};
}

export async function initI18n() {
  fallback = await load("en");
  const lang = (navigator.language || "en").slice(0, 2).toLowerCase();
  current = lang === "en" ? fallback : await load(lang);
  document.documentElement.lang = lang === "nl" ? "nl" : "en";
  applyTranslations();
}

export function t(key) {
  return current[key] ?? fallback[key] ?? key;
}

export function applyTranslations(root = document) {
  for (const element of root.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }
  for (const element of root.querySelectorAll("[data-i18n-aria]")) {
    element.setAttribute("aria-label", t(element.dataset.i18nAria));
  }
}
