"""
WebSocket клиент для реального обмена сообщениями и уведомлениями.
"""

import websockets
import json
import asyncio
from threading import Thread
from PyQt5.QtCore import QObject, pyqtSignal
import requests
import logging
from typing import Optional

# Импорт модулей из новой структуры
try:
    from client.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_URL, CONNECTION_TIMEOUT
    from client.auth_manager import get_auth_manager
except ImportError as e:
    print(f"Ошибка импорта в websocket_client.py: {e}")


logger = logging.getLogger(__name__)


class MessengerWebSocket(QObject):
    message_received = pyqtSignal(dict)  # Сигнал для передачи сообщений в UI
    status_updated = pyqtSignal(dict)    # Сигнал для обновления статусов
    connection_changed = pyqtSignal(bool)  # Сигнал изменения состояния соединения
    
    def __init__(self, user_id: int, server_url: Optional[str] = None):
        super().__init__()
        self.user_id = user_id
        self.ws = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.is_connected = False
        self.running = True
        self.auth_manager = get_auth_manager()
        
        # Определяем URL сервера
        if server_url:
            # Извлекаем host и port из URL
            if server_url.startswith("http://"):
                server_url = server_url[7:]
            elif server_url.startswith("https://"):
                server_url = server_url[8:]
            
            parts = server_url.split(":")
            if len(parts) == 2:
                self.server_host = parts[0]
                self.server_port = int(parts[1])
            else:
                self.server_host = SERVER_HOST
                self.server_port = SERVER_PORT
        else:
            self.server_host = SERVER_HOST
            self.server_port = SERVER_PORT
            
        self.loop = None

    def connect(self):
        """Запускает WebSocket в отдельном потоке"""
        def websocket_thread():
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(self._websocket_listener())
            except Exception as e:
                logger.error(f"WebSocket thread error: {e}")
            finally:
                if self.loop and not self.loop.is_closed():
                    self.loop.close()
        
        thread = Thread(target=websocket_thread, daemon=True)
        thread.start()

    async def _websocket_listener(self):
        """Основной цикл WebSocket"""
        while self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                ws_uri = f"ws://{self.server_host}:{self.server_port}/ws/{self.user_id}"
                logger.info(f"🔌 Connecting to WebSocket: {ws_uri}")

                async with websockets.connect(
                    ws_uri, 
                    ping_interval=20, 
                    ping_timeout=20,
                    close_timeout=5
                ) as websocket:
                    self.ws = websocket
                    self.is_connected = True
                    self.reconnect_attempts = 0
                    self.connection_changed.emit(True)
                    logger.info("✅ WebSocket connected successfully")
                    
                    # Отправляем начальное сообщение с токеном
                    try:
                        auth_token = self.auth_manager.get_auth_token()
                        if auth_token:
                            auth_message = {
                                "type": "auth",
                                "token": auth_token,
                                "user_id": self.user_id
                            }
                            await websocket.send(json.dumps(auth_message))
                    except Exception as e:
                        logger.warning(f"Failed to send auth message: {e}")
                    
                    while self.running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=25)
                            await self._handle_message(message)
                        except asyncio.TimeoutError:
                            # Отправляем ping для поддержания соединения
                            try:
                                await websocket.send('ping')
                            except:
                                logger.warning("⚠️ Failed to send ping")
                                break
                        except websockets.exceptions.ConnectionClosed as e:
                            logger.warning(f"⚠️ WebSocket connection closed: {e}")
                            break
                        except Exception as e:
                            logger.error(f"⚠️ WebSocket receive error: {e}")
                            break
                            
            except ConnectionRefusedError:
                logger.error(f"❌ Connection refused to {self.server_host}:{self.server_port}")
                await self._handle_disconnection()
            except Exception as e:
                logger.error(f"⚠️ WebSocket connection error: {e}")
                await self._handle_disconnection()
        
        # После завершения цикла устанавливаем статус оффлайн
        if self.running:
            logger.info("📴 WebSocket listener stopped")
            self._mark_user_offline()
    
    async def _handle_disconnection(self):
        """Обработка разрыва соединения"""
        self.is_connected = False
        self.connection_changed.emit(False)
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts < self.max_reconnect_attempts:
            delay = min(2 * self.reconnect_attempts, 10)
            logger.info(f"⏳ Reconnecting in {delay} seconds... (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
            await asyncio.sleep(delay)
        else:
            logger.error("❌ Max reconnection attempts reached")
    
    def _mark_user_offline(self):
        """Отметить пользователя как оффлайн"""
        try:
            response = requests.post(
                f"http://{self.server_host}:{self.server_port}/auth/status",
                json={"user_id": self.user_id, "is_online": False},
                timeout=3
            )
            if response.status_code == 200:
                logger.info(f"📴 Marked user {self.user_id} as offline")
            else:
                logger.warning(f"⚠️ Failed to mark user offline: {response.status_code}")
        except Exception as e:
            logger.error(f"⚠️ Failed to mark user {self.user_id} as offline: {e}")
            
    async def _handle_message(self, message):
        """Обработка входящих сообщений"""
        try:
            if message == 'pong':
                return
                
            data = json.loads(message)
            message_type = data.get('type', 'unknown')
            logger.debug(f"📨 WebSocket received: {message_type}")
            
            # Обработка обновления статуса пользователя
            if message_type == "user_status_update":
                self.status_updated.emit(data)
            elif message_type == "auth_response":
                # Ответ на аутентификацию
                if data.get("status") == "success":
                    logger.info("✅ WebSocket authentication successful")
                else:
                    logger.warning(f"⚠️ WebSocket authentication failed: {data.get('message')}")
            elif message_type == "ping":
                # Ответ на ping
                await self.ws.send('pong')
            else:
                # Отправляем данные в UI через сигнал
                self.message_received.emit(data)
                
        except json.JSONDecodeError:
            logger.warning(f"⚠️ Non-JSON message: {message}")
        except Exception as e:
            logger.error(f"⚠️ Error handling message: {e}")

    def send_message(self, data):
        """Отправка сообщения через WebSocket"""
        if self.is_connected and self.ws:
            try:
                # Запускаем асинхронную отправку
                asyncio.run_coroutine_threadsafe(self._send_async(data), self.loop)
            except Exception as e:
                logger.error(f"⚠️ Error in send_message: {e}")
        else:
            logger.warning("⚠️ WebSocket not connected, cannot send message")

    async def _send_async(self, data):
        """Асинхронная отправка сообщения"""
        try:
            await self.ws.send(json.dumps(data))
            logger.debug(f"📤 WebSocket sent: {data.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"⚠️ Error sending message: {e}")
            self.is_connected = False
            self.connection_changed.emit(False)

    def disconnect(self):
        """Отключение WebSocket"""
        logger.info("🔌 Disconnecting WebSocket...")
        self.running = False
        self.is_connected = False
        self.connection_changed.emit(False)
        
        if self.ws and self.loop:
            try:
                # Создаем новую задачу для закрытия соединения
                asyncio.run_coroutine_threadsafe(self._close_async(), self.loop)
            except:
                pass
    
    async def _close_async(self):
        """Асинхронное закрытие соединения"""
        try:
            await self.ws.close()
            logger.info("✅ WebSocket closed properly")
        except:
            logger.warning("⚠️ Error closing WebSocket")
    
    def get_connection_status(self) -> dict:
        """Получение статуса соединения"""
        return {
            "is_connected": self.is_connected,
            "reconnect_attempts": self.reconnect_attempts,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "server": f"{self.server_host}:{self.server_port}",
            "user_id": self.user_id
        }


# Глобальный экземпляр для удобного доступа
_websocket_instances = {}

def get_websocket_instance(user_id: int, server_url: Optional[str] = None) -> MessengerWebSocket:
    """Получение экземпляра WebSocket для пользователя"""
    global _websocket_instances
    
    if user_id not in _websocket_instances:
        _websocket_instances[user_id] = MessengerWebSocket(user_id, server_url)
    
    return _websocket_instances[user_id]


def remove_websocket_instance(user_id: int):
    """Удаление экземпляра WebSocket"""
    global _websocket_instances
    
    if user_id in _websocket_instances:
        instance = _websocket_instances[user_id]
        instance.disconnect()
        del _websocket_instances[user_id]


if __name__ == "__main__":
    # Тестирование WebSocket клиента
    import time
    
    print("Тестирование WebSocket клиента...")
    
    # Тестовые данные
    test_user_id = 1
    
    # Создаем экземпляр WebSocket
    websocket = MessengerWebSocket(test_user_id, "http://127.0.0.1:8000")
    
    # Обработчики сигналов
    def on_message_received(data):
        print(f"📨 Получено сообщение: {data}")
    
    def on_status_updated(data):
        print(f"🔄 Обновлен статус: {data}")
    
    def on_connection_changed(is_connected):
        status = "подключено" if is_connected else "отключено"
        print(f"🔌 Соединение {status}")
    
    websocket.message_received.connect(on_message_received)
    websocket.status_updated.connect(on_status_updated)
    websocket.connection_changed.connect(on_connection_changed)
    
    # Подключаемся
    websocket.connect()
    
    print("WebSocket подключен. Ожидание сообщений...")
    print("Нажмите Ctrl+C для остановки")
    
    try:
        # Ждем некоторое время
        time.sleep(30)
        
        # Проверяем статус
        status = websocket.get_connection_status()
        print(f"\nСтатус соединения: {status}")
        
        # Отправляем тестовое сообщение
        test_message = {
            "type": "test",
            "message": "Тестовое сообщение",
            "timestamp": time.time()
        }
        websocket.send_message(test_message)
        
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\nОстановка по запросу пользователя...")
    finally:
        # Отключаемся
        websocket.disconnect()
        print("Тестирование завершено!")