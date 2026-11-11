// Texts come from /static/i18n/<lang>.json; a missing key falls back to English (TR-311).
// Language: the stored choice, else the browser language if it is nl or en, else English (Q8).

import { LANGUAGES, readPref, writePref } from "./prefs.js";

let current = {};
let fallback = {};
let language = "en";

async function load(lang) {
  try {
    const response = await fetch(`/static/i18n/${lang}.json`);
    return response.ok ? await response.json() : {};
  } catch {
    return {};
  }
}

export function resolveLanguage(choice) {
  if (choice === "nl" || choice === "en") return choice;
  const browser = (navigator.language || "en").slice(0, 2).toLowerCase();
  return browser === "nl" ? "nl" : "en";
}

export const languageChoice = () => readPref("language", LANGUAGES);

export async function initI18n() {
  fallback = await load("en");
  await setLanguage(languageChoice(), false);
}

export async function setLanguage(choice, remember = true) {
  if (remember) writePref("language", choice);
  language = resolveLanguage(choice);
  current = language === "en" ? fallback : await load(language);
  document.documentElement.lang = language;
  applyTranslations();
}

export const currentLanguage = () => language;

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
  document.dispatchEvent(new CustomEvent("dashboard:language"));
}
