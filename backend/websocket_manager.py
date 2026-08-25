"""WebSocket manager — real-time frame update streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for simulation streaming."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info("WebSocket connected (%d total)", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected (%d total)", len(self.active_connections))

    async def broadcast(self, event: dict):
        dead = []
        async with self._lock:
            for ws in self.active_connections:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections.remove(ws)

    async def send_event(self, websocket: WebSocket, event: dict):
        try:
            await websocket.send_json(event)
        except Exception:
            async with self._lock:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)
