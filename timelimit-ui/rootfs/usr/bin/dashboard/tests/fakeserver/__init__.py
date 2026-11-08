"""Fake TimeLimit server: the test double of plan step A5 (TR-501).

``FakeTimeLimitServer`` starts a server that speaks the real protocol (strict schemas, silent action
failures, sequence numbers, Socket.IO) on an ephemeral port, so tests never touch a real family.
"""

from __future__ import annotations

from types import TracebackType

from .app import Faults, ServerThread, create_app
from .state import API_LEVEL_DEFAULT, World

__all__ = ["FakeTimeLimitServer"]


class FakeTimeLimitServer:
    def __init__(
        self,
        *,
        api_level: int = API_LEVEL_DEFAULT,
        premium: bool = True,
        rule_expiry: bool = False,
    ) -> None:
        self.world = World(
            api_level=api_level, premium=premium, rule_expiry=rule_expiry
        )
        self.faults = Faults()
        self.calls: list[tuple[str, str]] = []
        self._app, self._sio = create_app(self.world, self.faults, self.calls)
        self._thread: ServerThread | None = None
        self._port = 0

    @property
    def port(self) -> int:
        return self._port

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def inbox(self) -> list[tuple[str, str]]:
        """(mail address, login code) of every mail the fake 'sent'."""
        return self.world.inbox

    @property
    def unsimulated(self) -> list[str]:
        """Schema-valid actions the fake does not implement; tests assert this stays empty."""
        return self.world.unsimulated

    def start(self) -> None:
        # Restarting keeps the family data and the port, like a server that was down for a while.
        self._thread = ServerThread(self._app, self._sio, "127.0.0.1", self._port)
        self._port = self._thread.port
        self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread = None

    def __enter__(self) -> FakeTimeLimitServer:  # noqa: PYI034
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
