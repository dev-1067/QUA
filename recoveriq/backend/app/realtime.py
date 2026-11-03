"""In-process WebSocket hub. Each connection carries the viewer's scope, so an agent only
receives events for their own cases and a branch manager only for their branch."""
from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self.clients: dict[WebSocket, dict] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket, scope: dict) -> None:
        await ws.accept()
        self.clients[ws] = scope

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.pop(ws, None)

    @staticmethod
    def _visible(scope: dict, evt: dict) -> bool:
        role = scope["role"]
        if role in ("exec", "admin"):
            return True
        if role == "l1":
            return evt.get("region_id") in (None, scope.get("region_id"))
        if role == "l2":
            return evt.get("branch_id") in (None, scope.get("branch_id"))
        return evt.get("agent_id") == scope["user_id"] or evt.get("broadcast", False)

    async def broadcast(self, evt: dict) -> None:
        msg = json.dumps(evt, default=str)
        dead = []
        for ws, scope in list(self.clients.items()):
            if not self._visible(scope, evt):
                continue
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def publish_threadsafe(self, evt: dict) -> None:
        if self.loop is None or self.loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self.loop.create_task(self.broadcast(evt))
        else:
            asyncio.run_coroutine_threadsafe(self.broadcast(evt), self.loop)


hub = Hub()
