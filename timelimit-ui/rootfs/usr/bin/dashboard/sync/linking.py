"""Linking this dashboard to a family (plan E1, FR-100, FR-101, decisions Q6, Q6b, Q6c, Q6d).

Existing family: the parent logs in with the mail code, the dashboard registers itself as a new device of
that parent (``sign-in-into-family``), then creates the parent "Dashboard" with the same password
(``ADD_USER`` with the DH password container), signs the device in as "Dashboard" (``SET_DEVICE_USER``) and
keeps it signed in (``SET_KEEP_SIGNED_IN``, the only step that needs the password integrity). From then on
every action uses the device method as "Dashboard". The password is used in memory only.

Fresh test server: ``create-family`` makes "Dashboard" the first parent (a family exists only then).

The server gives no family id; the own device id stands in for it (a new registration is a new cache).
Every step looks at the cache first, so a step that failed half way can be finished by running it again.
"""

from __future__ import annotations

from typing import Any

from dashboard.client.server import TimeLimitClient
from dashboard.domain import actions, passwords
from dashboard.domain.clock import Clock
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.domain.integrity import encrypt_parent_password
from dashboard.domain.secret import Secret
from dashboard.logs import fields, get_logger
from dashboard.repository.cache import CacheRepository, Scope
from dashboard.repository.db import Database
from dashboard.repository.links import Link, LinkRepository
from dashboard.sync.pull import Puller, apply_server_status
from dashboard.sync.push import Pusher

log = get_logger("link")

DASHBOARD_NAME = "Dashboard"
DEVICE_NAME = "Dashboard"
DEVICE_MODEL = "TimeLimit Dashboard"


class Linker:
    def __init__(
        self,
        *,
        client: TimeLimitClient,
        links: LinkRepository,
        cache: CacheRepository,
        db: Database,
        profile_key: str,
        clock: Clock | None = None,
    ) -> None:
        self._client = client
        self._links = links
        self._cache = cache
        self._db = db
        self._key = profile_key
        self._clock = clock
        self._puller = Puller(client, cache, db, clock)
        self._pusher = Pusher(client, links, self._puller)

    def _now_ms(self) -> int:
        return int(self._clock.now().timestamp() * 1000) if self._clock else 0

    # -- the mail login ---------------------------------------------------------------------------------------------
    def send_code(self, mail: str, locale: str) -> Secret:
        return self._client.send_login_code(mail, locale)

    def confirm_code(
        self, login_token: Secret, code: str
    ) -> tuple[Secret, dict[str, Any]]:
        auth = self._client.sign_in_by_code(login_token, code)
        return auth, self._client.status_by_mail(auth)

    # -- the two ways to get a link -------------------------------------------------------------------------------
    def join_family(self, mail_auth: Secret, mail: str, time_zone: str) -> Link:
        """Register this dashboard as a new device of the parent that owns ``mail`` (no password yet)."""
        del time_zone  # the parent's own zone is used later for "Dashboard"
        answer = self._client.sign_in_into_family(
            mail_auth_token=mail_auth,
            device_name=DEVICE_NAME,
            device_model=DEVICE_MODEL,
        )
        return self._store(answer, mail)

    def create_family(
        self, mail_auth: Secret, mail: str, password: str, time_zone: str
    ) -> Link:
        """Fresh test server: the first parent of a new family is "Dashboard"."""
        hashes = passwords.new_password(password)
        answer = self._client.create_family(
            mail_auth_token=mail_auth,
            parent_name=DASHBOARD_NAME,
            device_name=DEVICE_NAME,
            device_model=DEVICE_MODEL,
            time_zone=time_zone,
            password={
                "hash": hashes.hash,
                "secondHash": hashes.second_hash,
                "secondSalt": hashes.second_salt,
            },
        )
        return self._store(answer, mail)

    def _store(self, answer: dict[str, Any], mail: str) -> Link:
        token = Secret(answer["deviceAuthToken"])
        own_id = str(answer["ownDeviceId"])
        link = self._links.set(
            self._key,
            device_token=token,
            own_device_id=own_id,
            family_id=own_id,
            now_ms=self._now_ms(),
            mail=mail,
        )
        scope = self._cache.activate(self._key, link.family_id)
        with self._db.transaction():
            apply_server_status(self._cache, scope, answer["data"])
        log.info("device registered", extra=fields(device_id=own_id))
        return link

    # -- "Dashboard" as the signed-in parent ------------------------------------------------------------------------
    def dashboard_ready(self) -> bool:
        link = self._links.get(self._key)
        if link is None:
            return False
        scope = Scope(self._key, link.family_id)
        device = self._own_device(scope, link)
        user = self._dashboard_user(scope)
        return bool(
            device
            and user
            and device.data.get("currentUserId") == user.data["id"]
            and device.data.get("isUserKeptSignedIn")
        )

    def finish(self, password: str) -> str:
        """Make "Dashboard" the signed-in parent of this device. Returns the id of "Dashboard".

        Safe to run again after a failure: each step is skipped when the cache shows it is done.
        """
        link = self._links.get(self._key)
        if link is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked yet."
            )
        scope = Scope(self._key, link.family_id)
        if not self._cache.users(scope):
            self._puller.pull(self._key, link.device_token, link.family_id)
        device = self._own_device(scope, link)
        if device is None:
            raise DashboardError(
                ErrorCode.SESSION_INVALID, "This device is not known to the server."
            )
        user = self._dashboard_user(scope)
        starter = str(device.data.get("currentUserId", ""))

        if user is None:
            starter_user = self._user(scope, starter)
            if starter_user is None:
                raise DashboardError(
                    ErrorCode.INTERNAL_ERROR,
                    "The signed-in parent is not in the family data.",
                )
            if not passwords.password_matches(
                password, str(starter_user.data["password"])
            ):
                raise DashboardError(
                    ErrorCode.INVALID_PASSWORD,
                    "That password does not belong to this parent.",
                )
            dashboard_id = self._add_dashboard_parent(
                scope, link, starter_user.data, password, starter
            )
        else:
            dashboard_id = str(user.data["id"])
            if not passwords.password_matches(password, str(user.data["password"])):
                raise DashboardError(
                    ErrorCode.INVALID_PASSWORD,
                    "That password does not belong to the Dashboard parent.",
                )
        second_hash = passwords.second_hash_for(
            password, self._second_salt(scope, dashboard_id)
        )

        device = self._own_device(scope, link)
        if device is not None and device.data.get("currentUserId") != dashboard_id:
            self._pusher.push(
                self._key,
                str(device.data.get("currentUserId") or starter),
                [actions.set_device_user(link.own_device_id, dashboard_id)],
            )
        device = self._own_device(scope, link)
        if device is not None and not device.data.get("isUserKeptSignedIn"):
            self._pusher.push(
                self._key,
                dashboard_id,
                [actions.set_keep_signed_in(link.own_device_id, True)],
                second_hash=second_hash,
            )
        if not self.dashboard_ready():
            raise DashboardError(
                ErrorCode.ACTION_NOT_CONFIRMED,
                "The server did not sign this dashboard in as the Dashboard parent.",
            )
        log.info("dashboard parent ready", extra=fields(user_id=dashboard_id))
        return dashboard_id

    def dashboard_parent_id(self) -> str | None:
        link = self._links.get(self._key)
        if link is None:
            return None
        user = self._dashboard_user(Scope(self._key, link.family_id))
        return str(user.data["id"]) if user else None

    def _add_dashboard_parent(
        self,
        scope: Scope,
        link: Link,
        starter: dict[str, Any],
        password: str,
        starter_id: str,
    ) -> str:
        key = self._cache.dh_key(scope)
        if key is None:
            self._puller.pull(self._key, link.device_token, link.family_id)
            key = self._cache.dh_key(scope)
        if key is None:
            raise DashboardError(
                ErrorCode.INTERNAL_ERROR,
                "The server sent no key for the new parent (client level too low for this server).",
            )
        hashes = passwords.new_password(password)
        user_id = actions.new_id()
        container = encrypt_parent_password(
            server_public_key=key[0],
            key_id=key[1],
            password_hash=hashes.hash,
            second_salt=hashes.second_salt,
            second_hash=hashes.second_hash,
        )
        self._pusher.push(
            self._key,
            starter_id,
            [
                actions.add_parent_user(
                    user_id,
                    DASHBOARD_NAME,
                    str(starter.get("timeZone") or "UTC"),
                    hashes.hash,
                    hashes.second_salt,
                    container,
                )
            ],
        )
        if self._dashboard_user(scope) is None:
            raise DashboardError(
                ErrorCode.ACTION_NOT_CONFIRMED,
                "The server did not create the Dashboard parent.",
            )
        return user_id

    # -- cache lookups ------------------------------------------------------------------------------------------------
    def _own_device(self, scope: Scope, link: Link) -> Any:
        return next(
            (
                d
                for d in self._cache.devices(scope)
                if d.data.get("deviceId") == link.own_device_id
            ),
            None,
        )

    def _user(self, scope: Scope, user_id: str) -> Any:
        return next(
            (u for u in self._cache.users(scope) if u.data.get("id") == user_id), None
        )

    def _dashboard_user(self, scope: Scope) -> Any:
        return next(
            (
                u
                for u in self._cache.users(scope)
                if u.data.get("name") == DASHBOARD_NAME
                and u.data.get("type") == "parent"
            ),
            None,
        )

    def _second_salt(self, scope: Scope, user_id: str) -> str:
        user = self._user(scope, user_id)
        assert user is not None
        return str(user.data["secondPasswordSalt"])
