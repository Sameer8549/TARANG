"""
WebSocket Connection Manager — broadcasts events to all dashboard clients.
"""

import json
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("tarang.ws")


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event_type: str, data: dict):
        """Broadcast JSON event to all connected dashboard clients."""
        payload = json.dumps({"type": event_type, "data": data})
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
        if len(self.active) > 0:
            logger.debug(f"📢 Broadcast [{event_type}] → {len(self.active)} clients")

    @property
    def count(self) -> int:
        return len(self.active)
