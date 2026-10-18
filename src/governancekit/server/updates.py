"""
Live updates for the GovernanceKit frontend.

Admins open a stream at /updates and get an event whenever a trace changes:
it starts, an agent checks, begins or finishes an activity on it, an agent is
added to it, or it ends. The frontend then reloads what it shows, so nobody
has to press refresh.

The events say only that something changed, not what; the client fetches the
monitors and audit logs as before.
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent

from governancekit.server.auth import require_admin
from governancekit.server.state import ServerState, get_state

router = APIRouter(tags=["management"], dependencies=[Depends(require_admin)])

# Seconds a stream stays open. The client then reconnects, so its token is
# checked again, and the server can shut down without waiting long for it.
STREAM_LIFETIME = 60.0
# Seconds between two events on a stream; changes meanwhile are sent as one
MIN_INTERVAL = 0.25


class FrontendTraceUpdates:
    """
    Tells the open update streams that a trace has changed.

    notify is called from the request threads, while the streams wait on the
    event loop, so each listener is woken through its loop.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._listeners: list[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = []

    def notify(self) -> None:
        """Wake every listener. Safe to call from any thread."""
        with self._lock:
            listeners = list(self._listeners)
        for loop, changed in listeners:
            loop.call_soon_threadsafe(changed.set)

    @contextmanager
    def listen(self) -> Iterator[asyncio.Event]:
        """
        Listen for changes while inside the block. Call from the event loop.

        Yields:
            An event that is set on every change; clear it after handling one.
        """
        listener = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            self._listeners.append(listener)
        try:
            yield listener[1]
        finally:
            with self._lock:
                self._listeners.remove(listener)


# ---------- Endpoints ----------


@router.get("/updates", response_class=EventSourceResponse)
async def stream_updates(
    state: Annotated[ServerState, Depends(get_state)],
) -> AsyncIterator[ServerSentEvent]:
    """
    Admin endpoint. Server-sent events: one right away, then one whenever a
    trace changes.

    The stream closes after STREAM_LIFETIME seconds; reconnect to keep
    listening. The first event lets a client that reconnects catch up on what
    it missed.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + STREAM_LIFETIME
    with state.frontend_updates.listen() as changed:
        changed.set()
        while True:
            try:
                await asyncio.wait_for(changed.wait(), timeout=deadline - loop.time())
            except TimeoutError:
                return
            changed.clear()
            yield ServerSentEvent(event="traces", raw_data="changed")
            await asyncio.sleep(MIN_INTERVAL)
