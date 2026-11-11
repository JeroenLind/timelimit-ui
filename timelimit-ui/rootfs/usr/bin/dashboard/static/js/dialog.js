// The one confirmation dialog (UI-006). Built on <dialog>.showModal(): the rest of the page is
// inert while it is open (focus stays inside) and Escape cancels.

import { t } from "./i18n.js";

export function confirmDialog({ title, message, confirmLabel, cancelLabel, danger = false }) {
  const dialog = document.getElementById("confirm-dialog");
  const ok = dialog.querySelector("[data-dialog-ok]");
  const cancel = dialog.querySelector("[data-dialog-cancel]");
  dialog.querySelector("[data-dialog-title]").textContent = title ?? "";
  dialog.querySelector("[data-dialog-message]").textContent = message ?? "";
  ok.textContent = confirmLabel ?? t("dialog.confirm");
  cancel.textContent = cancelLabel ?? t("dialog.cancel");
  ok.dataset.danger = String(danger);
  const opener = document.activeElement;

  return new Promise((resolve) => {
    function finish() {
      dialog.removeEventListener("close", finish);
      dialog.removeEventListener("keydown", trap);
      ok.removeEventListener("click", onOk);
      cancel.removeEventListener("click", onCancel);
      if (opener instanceof HTMLElement) opener.focus();
      resolve(dialog.returnValue === "ok");
    }
    function trap(event) {
      if (event.key !== "Tab") return;
      const [first, last] = [cancel, ok];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    const onOk = () => dialog.close("ok");
    const onCancel = () => dialog.close("cancel");
    dialog.returnValue = "cancel";
    dialog.addEventListener("close", finish);
    dialog.addEventListener("keydown", trap);
    ok.addEventListener("click", onOk);
    cancel.addEventListener("click", onCancel);
    dialog.showModal();
    cancel.focus();
  });
}
