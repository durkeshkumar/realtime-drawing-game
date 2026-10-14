
import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Room code -> player ID -> active WebSocket connections
        self.active_connections: dict[
            str, dict[int, set[WebSocket]]
        ] = defaultdict(lambda: defaultdict(set))

        self._lock = asyncio.Lock()

    async def connect(
        self,
        room_code: str,
        player_id: int,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()

        async with self._lock:
            self.active_connections[room_code][player_id].add(websocket)

    async def disconnect(
        self,
        room_code: str,
        player_id: int,
        websocket: WebSocket | None = None,
    ) -> None:
        async with self._lock:
            room_connections = self.active_connections.get(room_code)

            if not room_connections:
                return

            player_connections = room_connections.get(player_id)

            if not player_connections:
                return

            if websocket is None:
                player_connections.clear()
            else:
                player_connections.discard(websocket)

            if not player_connections:
                room_connections.pop(player_id, None)

            if not room_connections:
                self.active_connections.pop(room_code, None)

    async def send_personal_message(
        self,
        message: dict,
        room_code: str,
        player_id: int,
    ) -> None:
        async with self._lock:
            connections = list(
                self.active_connections.get(room_code, {}).get(
                    player_id, set()
                )
            )

        failed_connections = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                failed_connections.append(websocket)

        for websocket in failed_connections:
            await self.disconnect(room_code, player_id, websocket)

    async def broadcast(
        self,
        room_code: str,
        message: dict,
        exclude_player_id: int | None = None,
    ) -> None:
        async with self._lock:
            room_connections = self.active_connections.get(room_code, {})
            targets = [
                (player_id, websocket)
                for player_id, connections in room_connections.items()
                if player_id != exclude_player_id
                for websocket in list(connections)
            ]

        failed_connections = []

        for player_id, websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception:
                failed_connections.append((player_id, websocket))

        for player_id, websocket in failed_connections:
            await self.disconnect(room_code, player_id, websocket)

    async def get_connected_player_ids(self, room_code: str) -> list[int]:
        async with self._lock:
            room_connections = self.active_connections.get(room_code, {})
            return [
                player_id
                for player_id, connections in room_connections.items()
                if connections
            ]

    async def is_player_connected(
        self,
        room_code: str,
        player_id: int,
    ) -> bool:
        async with self._lock:
            return bool(
                self.active_connections.get(room_code, {}).get(player_id)
            )


manager = ConnectionManager()
