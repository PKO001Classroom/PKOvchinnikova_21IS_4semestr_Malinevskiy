from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        try:
            await websocket.accept()
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
            logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections.get(user_id, set()))}")

            # Отправляем уведомление о новом онлайн статусе
            await self.broadcast_status_update(user_id, True)
        except Exception as e:
            logger.error(f"Error connecting user {user_id}: {e}")
            raise
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        try:
            if user_id in self.active_connections and websocket in self.active_connections[user_id]:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    # Отправляем уведомление об оффлайн статусе
                    asyncio.create_task(self.broadcast_status_update(user_id, False))
                logger.info(f"User {user_id} disconnected. Remaining connections: {len(self.active_connections.get(user_id, set()))}")
        except Exception as e:
            logger.error(f"Error disconnecting user {user_id}: {e}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections and self.active_connections[user_id]:
            dead_connections = []
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json(message)
                    logger.debug(f"Message sent to user {user_id}: {message}")
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    dead_connections.append(connection)
            
            # Удаляем мертвые соединения
            for connection in dead_connections:
                self.disconnect(connection, user_id)
        else:
            logger.debug(f"No active connections for user {user_id}")
    
    async def broadcast_to_users(self, message: dict, user_ids: list[int]):
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)
    
    async def broadcast_status_update(self, user_id: int, is_online: bool):
        """Рассылка уведомления об изменении статуса пользователя"""
        try:
            status_message = {
                "type": "user_status_update",
                "user_id": user_id,
                "is_online": is_online,
                "timestamp": datetime.now().isoformat()
            }
            
            # Отправляем всем пользователям, кроме самого пользователя
            for other_user_id in self.active_connections:
                if other_user_id != user_id:
                    await self.send_personal_message(status_message, other_user_id)
            
            logger.info(f"Broadcast status update: user {user_id} is now {'online' if is_online else 'offline'}")
        except Exception as e:
            logger.error(f"Error broadcasting status update for user {user_id}: {e}")

manager = ConnectionManager()