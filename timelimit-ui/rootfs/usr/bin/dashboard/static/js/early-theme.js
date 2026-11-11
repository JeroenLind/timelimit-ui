// Runs before the first paint (classic script in <head>) so a chosen theme does not flash.
try {
  const theme = localStorage.getItem("dashboard.theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
} catch {
  /* no storage: follow the system */
}
