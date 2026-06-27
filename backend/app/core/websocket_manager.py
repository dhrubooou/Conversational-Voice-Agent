from typing import Dict, List
from fastapi import WebSocket


class WebSocketManager:
    """
    Manages active WebSocket connections per LiveKit room.
    Provides sub-millisecond real-time event broadcasting to subscription channels.
    """

    def __init__(self):
        # Key: room_name, Value: List of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_name: str, websocket: WebSocket) -> None:
        """
        Accepts a WebSocket connection and registers it to a room's broadcast list.
        """
        await websocket.accept()
        if room_name not in self.active_connections:
            self.active_connections[room_name] = []
        self.active_connections[room_name].append(websocket)
        print(
            f"🔌 WebSocket subscriber registered for room: {room_name} (Total: {len(self.active_connections[room_name])})"
        )

    def disconnect(self, room_name: str, websocket: WebSocket) -> None:
        """
        Deregisters a WebSocket connection from a room.
        """
        if room_name in self.active_connections:
            if websocket in self.active_connections[room_name]:
                self.active_connections[room_name].remove(websocket)
                print(
                    f"🔌 WebSocket subscriber left room: {room_name} (Remaining: {len(self.active_connections[room_name])})"
                )
            if not self.active_connections[room_name]:
                del self.active_connections[room_name]

    async def broadcast(self, room_name: str, message: dict) -> None:
        """
        Broadcasts a JSON message to all active WebSocket connections subscribed to a room.
        """
        if room_name in self.active_connections:
            disconnected_websockets = []
            for websocket in self.active_connections[room_name]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    print(
                        f"⚠️ Failed to send WebSocket message, queueing for cleanup: {e}"
                    )
                    disconnected_websockets.append(websocket)

            # Clean up broken connections
            for ws in disconnected_websockets:
                self.disconnect(room_name, ws)


# Global instance of WebSocketManager
ws_manager = WebSocketManager()
