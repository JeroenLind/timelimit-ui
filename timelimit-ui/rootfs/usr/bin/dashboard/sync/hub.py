"""The SSE hub: tells the browser that the cache changed (plan B6, design section 3).

Everything upward is a notification, not a call: the sync side publishes small JSON events, every open
browser stream gets them. A slow or stuck browser can never block the sync side: each subscriber has a
bounded queue and the oldest event is dropped when it is full (the browser refreshes from the cache
anyway, so a lost "changed" is harmless when a later one follows).
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from typing import Any

Event = dict[str, Any]
QUEUE_SIZE = 100


class Subscription:
    def __init__(self) -> None:
        self.events: queue.Queue[Event] = queue.Queue(maxsize=QUEUE_SIZE)
        self.closed = threading.Event()


class EventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscriptions: set[Subscription] = set()

    def subscribe(self) -> Subscription:
        subscription = Subscription()
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        subscription.closed.set()
        with self._lock:
            self._subscriptions.discard(subscription)

    @property
    def subscribers(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def publish(self, event: Event) -> None:
        with self._lock:
            targets = list(self._subscriptions)
        for subscription in targets:
            while True:
                try:
                    subscription.events.put_nowait(event)
                    break
                except queue.Full:
                    try:
                        subscription.events.get_nowait()  # drop the oldest
                    except queue.Empty:
                        pass

    def stream(
        self, subscription: Subscription, *, keepalive: float = 15.0
    ) -> Iterator[str]:
        """Server-sent-event text for one browser. Ends when the subscription is closed."""
        yield "retry: 3000\n\n"
        while not subscription.closed.is_set():
            try:
                event = subscription.events.get(timeout=keepalive)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event)}\n\n"
