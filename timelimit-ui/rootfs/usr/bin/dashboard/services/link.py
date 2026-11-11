"""The link flow as the browser sees it (plan E1, FR-100, FR-101, decisions Q6, Q6b, Q6c, Q6d).

States: ``no_server`` (nothing chosen), ``not_linked``, ``registered`` (the device is registered but
"Dashboard" is not the signed-in parent yet: a password is needed to finish), ``ready`` and
``session_invalid`` (the server ended the session: link again).

The mail login (code sent by the server) is kept in memory while the browser walks through the steps.
Passwords are passed through and never stored; the log shows only masked values.
"""

from __future__ import annotations

import threading
from typing import Any

from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.domain.secret import Secret
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend
from dashboard.sync.live import STATE_SESSION_INVALID

NO_SERVER = "no_server"
NOT_LINKED = "not_linked"
REGISTERED = "registered"
READY = "ready"
SESSION_INVALID = "session_invalid"


class LinkService:
    def __init__(self, backend: Backend, profiles: ServerProfiles) -> None:
        self._backend = backend
        self._profiles = profiles
        self._lock = threading.Lock()
        self._login: dict[str, Any] = {}

    # -- state -----------------------------------------------------------------------------------------------------
    def state(self) -> str:
        url = self._profiles.url()
        if not url:
            return NO_SERVER
        if self._backend.links.get(url) is None:
            return NOT_LINKED
        if self._backend.live_state(url)["state"] == STATE_SESSION_INVALID:
            return SESSION_INVALID
        return READY if self._backend.linker(url).dashboard_ready() else REGISTERED

    def view(self) -> dict[str, Any]:
        url = self._profiles.url()
        link = self._backend.links.get(url) if url else None
        with self._lock:
            step = self._login.get("step", "none")
            status = self._login.get("status")
            mail = self._login.get("mail", "")
        return {
            "state": self.state(),
            "device_id": link.own_device_id if link else None,
            "linked_at": link.linked_at if link else None,
            "login_step": step,
            "login_mail": mail,
            "account_status": status,
            "can_create_family": step == "confirmed"
            and status == "without family"
            and self._profiles.test_server(),
        }

    def reset_login(self) -> None:
        with self._lock:
            self._login = {}

    # -- steps -----------------------------------------------------------------------------------------------------------
    def _url(self) -> str:
        url = self._profiles.url()
        if not url:
            raise DashboardError(ErrorCode.INVALID_INPUT, "Choose a server first.")
        return url

    def send_code(self, mail: str, locale: str) -> None:
        mail = (mail or "").strip()
        if "@" not in mail:
            raise DashboardError(ErrorCode.INVALID_INPUT, "Enter a valid mail address.")
        token = self._backend.linker(self._url()).send_code(mail, locale or "en")
        with self._lock:
            self._login = {"step": "code_sent", "mail": mail, "login_token": token}

    def confirm_code(self, code: str) -> None:
        with self._lock:
            login_token = self._login.get("login_token")
            mail = self._login.get("mail", "")
        if not isinstance(login_token, Secret):
            raise DashboardError(ErrorCode.INVALID_INPUT, "Ask for a code first.")
        auth, status = self._backend.linker(self._url()).confirm_code(
            login_token, (code or "").strip()
        )
        with self._lock:
            self._login = {
                "step": "confirmed",
                "mail": status.get("mail", mail),
                "mail_auth": auth,
                "status": status.get("status"),
            }

    def join(self, password: str, time_zone: str) -> None:
        """Existing family: register (once), then make "Dashboard" the signed-in parent."""
        del time_zone
        url = self._url()
        if not password:
            raise DashboardError(
                ErrorCode.INVALID_INPUT, "Enter the password of this parent."
            )
        linker = self._backend.linker(url)
        if self._backend.links.get(url) is None:
            with self._lock:
                auth = self._login.get("mail_auth")
                mail = self._login.get("mail", "")
                status = self._login.get("status")
            if not isinstance(auth, Secret) or status != "with family":
                raise DashboardError(
                    ErrorCode.INVALID_INPUT,
                    "Log in with the mail code of a parent first.",
                )
            linker.join_family(auth, mail, "UTC")
            self.reset_login()
        self._finish(url, password)

    def finish(self, password: str) -> None:
        """The device is registered but "Dashboard" is not signed in yet: finish with the password."""
        self._finish(self._url(), password)

    def _finish(self, url: str, password: str) -> None:
        self._backend.linker(url).finish(password)
        self._backend.start_live(url)

    def create_family(self, password: str, time_zone: str) -> None:
        """Fresh test server only (Q6c): the first parent of a new family is "Dashboard"."""
        url = self._url()
        if not self._profiles.test_server(url):
            raise DashboardError(
                ErrorCode.INVALID_INPUT,
                "Creating a family is only possible on a test server.",
            )
        with self._lock:
            auth = self._login.get("mail_auth")
            mail = self._login.get("mail", "")
            status = self._login.get("status")
        if not isinstance(auth, Secret) or status != "without family":
            raise DashboardError(
                ErrorCode.INVALID_INPUT,
                "Log in with a mail address that has no family yet.",
            )
        if not password:
            raise DashboardError(
                ErrorCode.INVALID_INPUT, "Choose a password for Dashboard."
            )
        self._backend.linker(url).create_family(
            auth, mail, password, time_zone or "UTC"
        )
        self.reset_login()
        self._backend.start_live(url)

    def unlink(self) -> None:
        url = self._url()
        self._backend.stop_live()
        self._backend.links.clear(url)
        self._backend.cache.clear_profile(url)
        self.reset_login()

    def resume(self) -> None:
        """At start-up: live sync for the active server when it is linked."""
        url = self._profiles.url()
        if url and self._backend.links.get(url) is not None:
            self._backend.start_live(url)

    def dashboard_parent_id(self) -> str | None:
        url = self._profiles.url()
        return self._backend.linker(url).dashboard_parent_id() if url else None
