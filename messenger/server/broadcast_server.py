"""
Broadcast сервер для анонсирования сервера мессенджера в сети.
"""

import socket
import json
import threading
import time
import logging
from typing import Optional
from database.user_model import UserModel

logger = logging.getLogger(__name__)


class BroadcastServer:
    """
    UDP сервер для ответа на broadcast запросы от клиентов.
    Отправляет информацию о сервере в локальную сеть.
    """
    
    def __init__(
        self,
        server_name: str = "Local Messenger Server",
        server_port: int = 8000,
        broadcast_port: int = 37020,
        description: str = "",
        max_users: int = 50,
        password_required: bool = False
    ):
        """
        Инициализация broadcast сервера.
        
        Args:
            server_name: Имя сервера
            server_port: Порт основного сервера
            broadcast_port: Порт для broadcast
            description: Описание сервера
            max_users: Максимальное количество пользователей
            password_required: Требуется ли пароль для запуска
        """
        self.server_name = server_name
        self.server_port = server_port
        self.broadcast_port = broadcast_port
        self.description = description
        self.max_users = max_users
        self.password_required = password_required
        
        self.is_running = False
        self.socket: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.last_activity = 0
        
        logger.info(f"Broadcast сервер инициализирован: {server_name}:{server_port}")
    
    def start(self):
        """Запуск broadcast сервера"""
        if self.is_running:
            logger.warning("Broadcast сервер уже запущен")
            return False
        
        try:
            # Создаем UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.bind(('', self.broadcast_port))
            self.socket.settimeout(1.0)  # Таймаут для возможности остановки
            
            self.is_running = True
            self.thread = threading.Thread(
                target=self._listen_loop,
                daemon=True,
                name="BroadcastServerThread"
            )
            self.thread.start()
            
            logger.info(f"Broadcast сервер запущен на порту {self.broadcast_port}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска broadcast сервера: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Остановка broadcast сервера"""
        self.is_running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        
        logger.info("Broadcast сервер остановлен")
    
    def _listen_loop(self):
        """Основной цикл прослушивания broadcast запросов"""
        logger.debug("Начало цикла прослушивания broadcast запросов")
        
        while self.is_running and self.socket:
            try:
                # Ждем входящие запросы
                data, addr = self.socket.recvfrom(1024)
                self.last_activity = time.time()
                
                # Обрабатываем запрос в отдельном потоке
                threading.Thread(
                    target=self._handle_request,
                    args=(data, addr),
                    daemon=True
                ).start()
                
            except socket.timeout:
                # Таймаут - нормальная ситуация, проверяем флаг is_running
                continue
            except OSError as e:
                if self.is_running:
                    logger.error(f"Ошибка socket в цикле прослушивания: {e}")
                break
            except Exception as e:
                logger.error(f"Неожиданная ошибка в цикле прослушивания: {e}")
                time.sleep(1)
        
        logger.debug("Цикл прослушивания broadcast завершен")
    
    def _handle_request(self, data: bytes, addr: tuple):
        """
        Обработка входящего запроса.
        
        Args:
            data: Данные запроса
            addr: Адрес отправителя (ip, port)
        """
        try:
            request = json.loads(data.decode('utf-8'))
            
            if request.get("type") == "discovery":
                self._send_server_info(addr)
                logger.debug(f"Отправлен ответ на discovery запрос от {addr[0]}")
                
        except json.JSONDecodeError:
            logger.warning(f"Некорректный JSON от {addr}")
        except Exception as e:
            logger.error(f"Ошибка обработки запроса от {addr}: {e}")
    
    def _send_server_info(self, addr: tuple):
        """
        Отправка информации о сервере.
        
        Args:
            addr: Адрес получателя
        """
        try:
            # Получаем текущее количество пользователей
            users_count = 0
            try:
                users = UserModel.get_all_users()
                users_count = len([u for u in users if u.get("is_online", False)])
            except:
                users_count = 0
            
            # Формируем ответ
            response = {
                "type": "server_response",
                "name": self.server_name,
                "port": self.server_port,
                "users_count": users_count,
                "password_required": self.password_required,
                "description": self.description,
                "version": "1.0",
                "max_users": self.max_users,
                "timestamp": time.time()
            }
            
            # Отправляем ответ
            if self.socket:
                response_data = json.dumps(response).encode('utf-8')
                self.socket.sendto(response_data, addr)
                
        except Exception as e:
            logger.error(f"Ошибка отправки информации о сервере: {e}")
    
    def update_config(
        self,
        server_name: Optional[str] = None,
        description: Optional[str] = None,
        password_required: Optional[bool] = None
    ):
        """
        Обновление конфигурации сервера.
        
        Args:
            server_name: Новое имя сервера
            description: Новое описание
            password_required: Новое значение требования пароля
        """
        if server_name is not None:
            self.server_name = server_name
        if description is not None:
            self.description = description
        if password_required is not None:
            self.password_required = password_required
        
        logger.info(f"Конфигурация broadcast сервера обновлена: {self.server_name}")
    
    def get_status(self) -> dict:
        """
        Получение статуса broadcast сервера.
        
        Returns:
            Словарь со статусом
        """
        return {
            "is_running": self.is_running,
            "server_name": self.server_name,
            "server_port": self.server_port,
            "broadcast_port": self.broadcast_port,
            "description": self.description,
            "password_required": self.password_required,
            "last_activity": self.last_activity
        }


# Глобальный экземпляр для доступа из основного сервера
_broadcast_server_instance: Optional[BroadcastServer] = None

def get_broadcast_server() -> BroadcastServer:
    """Получение глобального экземпляра BroadcastServer"""
    global _broadcast_server_instance
    return _broadcast_server_instance

def init_broadcast_server(
    server_name: str = "Local Messenger Server",
    server_port: int = 8000,
    **kwargs
) -> BroadcastServer:
    """
    Инициализация глобального broadcast сервера.
    
    Args:
        server_name: Имя сервера
        server_port: Порт сервера
        **kwargs: Дополнительные параметры
        
    Returns:
        Экземпляр BroadcastServer
    """
    global _broadcast_server_instance
    _broadcast_server_instance = BroadcastServer(
        server_name=server_name,
        server_port=server_port,
        **kwargs
    )
    return _broadcast_server_instance


# Тестирование
if __name__ == "__main__":
    print("Тестирование broadcast сервера...")
    
    # Создаем тестовый сервер
    server = BroadcastServer(
        server_name="Test Messenger Server",
        server_port=8000,
        description="Тестовый сервер для разработки",
        password_required=False
    )
    
    try:
        # Запускаем сервер
        if server.start():
            print("Broadcast сервер запущен. Ожидание запросов...")
            print("Нажмите Ctrl+C для остановки")
            
            # Демонстрация работы в течение 30 секунд
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\nОстановка по запросу пользователя...")
    finally:
        server.stop()
        print("Тест завершен.")
