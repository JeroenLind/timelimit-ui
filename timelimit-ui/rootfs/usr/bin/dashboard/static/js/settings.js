// The settings and link screen (plan E1).

import { ApiError, apiFetch } from "./api.js";
import { confirmDialog } from "./dialog.js";
import { currentLanguage, t } from "./i18n.js";
import { refreshNotices } from "./notices.js";

const $ = (id) => document.getElementById(id);
let current = null;

function showError(error) {
  const box = $("settings-error");
  if (!error) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  const known = t(`error.${error.code}`);
  box.textContent = error.code === "INVALID_INPUT" && error.message ? `${known} ${error.message}` : known;
  box.dataset.code = error.code;
  box.hidden = false;
}

async function run(action) {
  showError(null);
  try {
    const view = await action();
    if (view) render(view);
    await refreshNotices();
  } catch (error) {
    showError(error instanceof ApiError ? error : new ApiError("INTERNAL_ERROR", String(error), 0));
    try {
      render(await apiFetch("/api/settings"));
    } catch {
      /* the banner already tells that the server is not reachable */
    }
  }
}

function formatTime(ms) {
  return ms ? new Date(ms).toLocaleString(currentLanguage()) : t("settings.never");
}

export function render(view) {
  current = view;
  const { server, link } = view;
  $("server-mode").value = server.mode === "alternative" ? "alternative" : "official";
  $("alt-fields").hidden = $("server-mode").value !== "alternative";
  if (server.mode === "alternative") {
    $("server-protocol").value = server.protocol;
    $("server-address").value = server.address;
    $("server-port").value = server.port ?? "";
  }
  $("server-url").textContent = server.url || "";
  $("test-server").checked = Boolean(server.test_server);
  $("test-server").disabled = !server.url;

  const state = $("link-state");
  state.dataset.state = link.state;
  state.textContent = t(`link.state.${link.state}`);

  const needsLogin = link.state === "not_linked";
  $("mail-form").hidden = !needsLogin || link.login_step !== "none";
  $("code-form").hidden = !needsLogin || link.login_step !== "code_sent";
  const confirmed = needsLogin && link.login_step === "confirmed";
  const hasFamily = link.account_status === "with family";
  const passwordForm = $("password-form");
  const submit = $("link-submit");
  const help = $("password-help");
  passwordForm.hidden = !(
    link.state === "registered" ||
    (confirmed && (hasFamily || link.can_create_family))
  );
  if (link.state === "registered") {
    submit.textContent = t("link.finish");
    submit.dataset.action = "finish";
    help.textContent = t("link.help.join");
  } else if (confirmed && hasFamily) {
    submit.textContent = t("link.join");
    submit.dataset.action = "join";
    help.textContent = t("link.help.join");
  } else {
    submit.textContent = t("link.create");
    submit.dataset.action = "create";
    help.textContent = t("link.help.create");
  }
  if (confirmed && !hasFamily && !link.can_create_family) {
    state.textContent = t("link.help.no_family");
  }
  const linked = link.state === "ready" || link.state === "session_invalid" || link.state === "registered";
  $("linked-box").hidden = !linked;
  $("device-id").textContent = link.device_id || "";

  $("info-version").textContent = view.dashboard_version;
  $("info-api").textContent =
    view.api_level == null
      ? "-"
      : `${view.api_level} (${t(view.version_warning ? "settings.api_untested" : "settings.api_tested")})`;
  $("info-sync").textContent = formatTime(view.last_sync);
  const live = view.live;
  $("info-live").textContent = !live || !live.running
    ? t("settings.live.off")
    : t(live.socket ? "settings.live.on" : "settings.live.polling");
  $("info-log").textContent = view.log_level;
  $("info-timings").textContent = Object.entries(view.timings)
    .map(([name, value]) => `${name}=${value}`)
    .join(", ");
}

export async function initSettings() {
  const sendJson = (path, method, body) => () => apiFetch(path, { method, body });
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

  $("server-mode").addEventListener("change", () => {
    $("alt-fields").hidden = $("server-mode").value !== "alternative";
  });
  $("server-save").addEventListener("click", () =>
    run(
      sendJson("/api/settings/server", "PUT", {
        mode: $("server-mode").value,
        protocol: $("server-protocol").value,
        address: $("server-address").value,
        port: $("server-port").value,
      }),
    ),
  );
  $("test-server").addEventListener("change", () =>
    run(sendJson("/api/settings/test-server", "PUT", { enabled: $("test-server").checked })),
  );
  $("mail-form").addEventListener("submit", (event) => {
    event.preventDefault();
    run(sendJson("/api/link/mail-code", "POST", { mail: $("link-mail").value, locale: currentLanguage() }));
  });
  $("code-form").addEventListener("submit", (event) => {
    event.preventDefault();
    run(sendJson("/api/link/confirm-code", "POST", { code: $("link-code").value }));
  });
  $("password-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const action = $("link-submit").dataset.action;
    const password = $("link-password").value;
    const path = { join: "join", finish: "finish", create: "create-family" }[action];
    run(async () => {
      try {
        return await apiFetch(`/api/link/${path}`, {
          method: "POST",
          body: { password, time_zone: zone },
        });
      } finally {
        $("link-password").value = "";
      }
    });
  });
  $("unlink").addEventListener("click", async () => {
    const yes = await confirmDialog({
      title: t("link.unlink.title"),
      message: t("link.unlink.message"),
      confirmLabel: t("link.unlink.confirm"),
      danger: true,
    });
    if (yes) run(sendJson("/api/link/unlink", "POST", {}));
  });
  $("debug-export").addEventListener("click", async () => {
    const yes = await confirmDialog({
      title: t("settings.debug.warning_title"),
      message: t("settings.debug.warning"),
      confirmLabel: t("settings.debug.button"),
    });
    if (yes) window.location.assign("/api/settings/debug-export");
  });
  document.addEventListener("dashboard:language", () => current && render(current));

  await run(() => apiFetch("/api/settings"));
}
