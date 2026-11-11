// Sidebar on wide screens, hamburger menu on small ones (UI-004).
// Closed by: the button again, the close button, the overlay, Escape. Focus returns to the button.

const NARROW = window.matchMedia("(max-width: 720px)");

export function initNav() {
  const toggle = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("nav-overlay");
  const close = document.getElementById("nav-close");

  function sync(open) {
    const narrow = NARROW.matches;
    const visible = !narrow || open;
    sidebar.dataset.open = String(narrow && open);
    sidebar.setAttribute("aria-hidden", String(!visible));
    sidebar.inert = !visible;
    overlay.hidden = !(narrow && open);
    toggle.setAttribute("aria-expanded", String(narrow && open));
  }

  function setOpen(open, { returnFocus = false } = {}) {
    sync(open);
    if (open) close.focus();
    else if (returnFocus) toggle.focus();
  }

  const isOpen = () => sidebar.dataset.open === "true";
  toggle.addEventListener("click", () => setOpen(!isOpen(), { returnFocus: isOpen() }));
  close.addEventListener("click", () => setOpen(false, { returnFocus: true }));
  overlay.addEventListener("click", () => setOpen(false, { returnFocus: true }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) setOpen(false, { returnFocus: true });
  });
  sidebar.addEventListener("click", (event) => {
    if (event.target.closest("a") && isOpen()) setOpen(false);
  });
  NARROW.addEventListener("change", () => sync(false));
  sync(false);
}
