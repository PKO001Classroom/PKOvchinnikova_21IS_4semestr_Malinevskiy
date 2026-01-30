import websockets
import json
import asyncio
from threading import Thread
from PyQt5.QtCore import QObject, pyqtSignal
import requests
from config import SERVER_HOST, SERVER_PORT

class MessengerWebSocket(QObject):
    message_received = pyqtSignal(dict)  # Сигнал для передачи сообщений в UI
    status_updated = pyqtSignal(dict)    # Сигнал для обновления статусов
    
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.ws = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.is_connected = False
        self.running = True
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
                print(f"⚠️ WebSocket thread error: {e}")
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
                print(f"🔌 Connecting to WebSocket: {ws_uri}")

                async with websockets.connect(
                    ws_uri, 
                    ping_interval=20, 
                    ping_timeout=20,
                    close_timeout=5
                ) as websocket:
                    self.ws = websocket
                    self.is_connected = True
                    self.reconnect_attempts = 0
                    print("✅ WebSocket connected successfully")
                    
                    while self.running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=25)
                            await self._handle_message(message)
                        except asyncio.TimeoutError:
                            # Отправляем ping для поддержания соединения
                            try:
                                await websocket.send('ping')
                            except:
                                print("⚠️ Failed to send ping")
                                break
                        except websockets.exceptions.ConnectionClosed as e:
                            print(f"⚠️ WebSocket connection closed: {e}")
                            break
                        except Exception as e:
                            print(f"⚠️ WebSocket receive error: {e}")
                            break
                            
            except ConnectionRefusedError:
                print(f"❌ Connection refused to {self.server_host}:{self.server_port}")
                await self._handle_disconnection()
            except Exception as e:
                print(f"⚠️ WebSocket connection error: {e}")
                await self._handle_disconnection()
        
        # После завершения цикла устанавливаем статус оффлайн
        if self.running:
            print("📴 WebSocket listener stopped")
            self._mark_user_offline()
    
    async def _handle_disconnection(self):
        """Обработка разрыва соединения"""
        self.is_connected = False
        self.reconnect_attempts += 1
        if self.reconnect_attempts < self.max_reconnect_attempts:
            delay = min(2 * self.reconnect_attempts, 10)
            print(f"⏳ Reconnecting in {delay} seconds... (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
            await asyncio.sleep(delay)
        else:
            print("❌ Max reconnection attempts reached")
    
    def _mark_user_offline(self):
        """Отметить пользователя как оффлайн"""
        try:
            response = requests.post(
                f"http://{self.server_host}:{self.server_port}/auth/status",
                json={"user_id": self.user_id, "is_online": False},
                timeout=3
            )
            if response.status_code == 200:
                print(f"📴 Marked user {self.user_id} as offline")
            else:
                print(f"⚠️ Failed to mark user offline: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Failed to mark user {self.user_id} as offline: {e}")
            
    async def _handle_message(self, message):
        """Обработка входящих сообщений"""
        try:
            if message == 'pong':
                return
                
            data = json.loads(message)
            print(f"📨 WebSocket received: {data.get('type', 'unknown')}")
            
            # Обработка обновления статуса пользователя
            if data.get("type") == "user_status_update":
                self.status_updated.emit(data)
            else:
                # Отправляем данные в UI через сигнал
                self.message_received.emit(data)
                
        except json.JSONDecodeError:
            print(f"⚠️ Non-JSON message: {message}")
        except Exception as e:
            print(f"⚠️ Error handling message: {e}")

    def send_message(self, data):
        """Отправка сообщения через WebSocket"""
        if self.is_connected and self.ws:
            try:
                # Запускаем асинхронную отправку
                asyncio.run_coroutine_threadsafe(self._send_async(data), self.loop)
            except Exception as e:
                print(f"⚠️ Error in send_message: {e}")
        else:
            print("⚠️ WebSocket not connected, cannot send message")

    async def _send_async(self, data):
        """Асинхронная отправка сообщения"""
        try:
            await self.ws.send(json.dumps(data))
            print(f"📤 WebSocket sent: {data.get('type', 'unknown')}")
        except Exception as e:
            print(f"⚠️ Error sending message: {e}")
            self.is_connected = False

    def disconnect(self):
        """Отключение WebSocket"""
        print("🔌 Disconnecting WebSocket...")
        self.running = False
        self.is_connected = False
        if self.ws:
            try:
                # Создаем новую задачу для закрытия соединения
                asyncio.run_coroutine_threadsafe(self._close_async(), self.loop)
            except:
                pass
    
    async def _close_async(self):
        """Асинхронное закрытие соединения"""
        try:
            await self.ws.close()
            print("✅ WebSocket closed properly")
        except:
            pass