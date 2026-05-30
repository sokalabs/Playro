"""Thread-safe SSE event bus for build stage transitions.

The generation pipeline emits stage events (idea -> plan -> luau -> handoff)
into per-build queues.  The /generate/{id}/events SSE endpoint drains these
queues and streams them to the desktop frontend in real time, replacing the
old hardcoded addStep+sleep delays in renderer.js.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import asdict, dataclass
from typing import Optional


# Map backend stage names to SSE event types.  The desktop frontend uses
# addEventListener('stage', ...) for progress updates and
# addEventListener('complete', ...) / addEventListener('error', ...)
# for terminal events.  Kept as a module-level constant because dataclass
# fields cannot have mutable defaults.
_STAGE_TO_EVENT: dict[str, str] = {
    "idea": "stage",
    "plan": "stage",
    "luau": "stage",
    "handoff": "stage",
    "complete": "complete",
    "error": "error",
}


@dataclass
class BuildEvent:
    """A single build stage transition event."""

    build_id: str
    stage: str # idea | plan | luau | handoff | complete | error
    title: str # human-readable stage label
    detail: str # one-line description of what happened
    timestamp: float # unix epoch seconds
    data: Optional[dict] = None # optional payload (e.g. generated file list)

    def to_sse(self) -> str:
        """Format as an SSE frame with named event type + JSON payload.

        Each frame now includes an ``event:`` line so that EventSource
        dispatches to the correct named listener (``stage``, ``complete``,
        or ``error``). The JSON payload also carries ``stage`` so a
        generic ``onmessage`` fallback can route by content.
        """
        payload = {
            "build_id": self.build_id,
            "stage": self.stage,
            "title": self.title,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }
        if self.data:
            payload["data"] = self.data
        event_type = _STAGE_TO_EVENT.get(self.stage, "stage")
        return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


class BuildEventBus:
    """Global, thread-safe pub/sub bus for build stage events.

    Each build gets its own ``queue.Queue`` the first time
    ``emit()`` is called for that build_id.  Subscribers call
    ``subscribe(build_id)`` to get a queue they can drain.

    Queues are TTL-garbage-collected: after ``ttl_seconds`` with no
    events or active subscribers, the queue is pruned.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._queues: dict[str, list[queue.Queue[BuildEvent]]] = {}
        self._last_activity: dict[str, float] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    # -- public API --------------------------------------------------------

    def emit(self, event: BuildEvent) -> None:
        """Broadcast an event to all subscribers for the build."""
        with self._lock:
            subscribers = self._queues.setdefault(event.build_id, [])
            self._last_activity[event.build_id] = time.time()
            # Put into every subscriber queue (non-blocking; drop if full)
            for q in subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass
            self._gc()

    def subscribe(self, build_id: str, maxsize: int = 256) -> queue.Queue[BuildEvent]:
        """Return a new subscriber queue for the given build.

        The caller drains the queue at its own pace (e.g. from an SSE
        handler in the HTTP server thread).
        """
        q: queue.Queue[BuildEvent] = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._queues.setdefault(build_id, []).append(q)
            self._last_activity[build_id] = time.time()
        return q

    def unsubscribe(self, build_id: str, q: queue.Queue[BuildEvent]) -> None:
        """Remove a subscriber queue (call when the SSE connection closes)."""
        with self._lock:
            subscribers = self._queues.get(build_id)
            if subscribers is not None:
                try:
                    subscribers.remove(q)
                except ValueError:
                    pass

    # -- garbage collection -------------------------------------------------

    def _gc(self) -> None:
        """Prune queues for builds with no activity beyond TTL."""
        now = time.time()
        stale = [
            bid
            for bid, ts in self._last_activity.items()
            if now - ts > self._ttl and not self._queues.get(bid)
        ]
        for bid in stale:
            self._queues.pop(bid, None)
            self._last_activity.pop(bid, None)


# Module-level singleton — imported by both the pipeline and the SSE handler.
bus = BuildEventBus()
