// The one small store of the page: what we know about the TimeLimit server.

const listeners = new Set();
const state = { server: "unknown", code: null };

export function getState() {
  return { ...state };
}

export function setServer(server, code = null) {
  const changed = state.server !== server;
  state.server = server;
  state.code = code;
  for (const listener of listeners) listener(getState(), changed);
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const isOffline = () => state.server === "down";
