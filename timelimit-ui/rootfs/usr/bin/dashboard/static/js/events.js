// One EventSource to the backend (design section 3). A "changed" event means the cache has new data:
// pages listen to the DOM event "dashboard:changed" and read again from the cache.

let source = null;

export function startEvents() {
  if (source || typeof EventSource === "undefined") return;
  source = new EventSource("/api/dashboard/stream");
  for (const type of ["changed", "session_invalid"]) {
    source.addEventListener(type, () => document.dispatchEvent(new CustomEvent("dashboard:changed", { detail: { type } })));
  }
  // EventSource reconnects by itself after a drop; the connection banner handles "backend gone".
}
