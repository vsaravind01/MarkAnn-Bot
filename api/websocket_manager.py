import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket - Connection Established - Client ID: {client_id}")

    async def disconnect(self, client_id: str):
        await self.active_connections[client_id].close()
        del self.active_connections[client_id]
        logger.info(f"WebSocket - Connection Closed - Client ID: {client_id}")

    def remove_connection(self, client_id: str):
        del self.active_connections[client_id]
        logger.info(f"WebSocket - Connection Removed - Client ID: {client_id}")

    async def close_all_connections(self):
        for connection in self.active_connections.values():
            await connection.close()
        self.active_connections.clear()
        logger.info("WebSocket - All Connections Closed")

    async def broadcast(self, client_id: str, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)
        logger.info(f"WebSocket - Broadcast Message Sent - Client ID: {client_id}")

    @staticmethod
    async def send_personal_message(message: dict, websocket: WebSocket):
        await websocket.send_json(message)
        logger.info(
            f"WebSocket - Personal Message Sent - Client ID: {websocket.client.host}"
        )
