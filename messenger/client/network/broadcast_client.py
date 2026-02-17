"""
Broadcast клиент для поиска серверов в локальной сети.
"""

import socket
import json
import time
import logging
from typing import List, Optional, Dict

# Исправляем импорт - добавляем client.
from client.models.server_info import ServerInfo

logger = logging.getLogger(__name__)


class BroadcastClient:
    """
    UDP клиент для поиска серверов мессенджера через broadcast.
    """
    
    def __init__(self, timeout: float = 3.0, broadcast_port: int = 37020):
        """
        Инициализация broadcast клиента.
        
        Args:
            timeout: Таймаут ожидания ответов (секунды)
            broadcast_port: Порт для broadcast запросов
        """
        self.timeout = timeout
        self.broadcast_port = broadcast_port
        self.broadcast_address = '<broadcast>'
        self.buffer_size = 1024
        
    def discover_servers(self) -> List[ServerInfo]:
        """
        Поиск серверов в сети.
        
        Returns:
            Список найденных серверов
        """
        servers = []
        
        try:
            # Создаем UDP socket для broadcast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(self.timeout)
            
            # Получаем локальный IP
            local_ip = self._get_local_ip()
            
            # Формируем discovery запрос
            discovery_request = {
                "type": "discovery",
                "client_version": "1.0",
                "client_ip": local_ip,
                "timestamp": time.time()
            }
            
            request_data = json.dumps(discovery_request).encode('utf-8')
            
            # Отправляем broadcast запрос
            sock.sendto(request_data, (self.broadcast_address, self.broadcast_port))
            logger.debug(f"Отправлен broadcast запрос на порт {self.broadcast_port}")
            
            # Слушаем ответы от серверов
            start_time = time.time()
            
            while time.time() - start_time < self.timeout:
                try:
                    data, addr = sock.recvfrom(self.buffer_size)
                    server_info = self._parse_server_response(data, addr)
                    
                    if server_info:
                        servers.append(server_info)
                        logger.info(f"Найден сервер: {server_info.name} ({server_info.ip}:{server_info.port})")
                        
                except socket.timeout:
                    break
                except json.JSONDecodeError as e:
                    logger.warning(f"Некорректный JSON от {addr}: {e}")
                except Exception as e:
                    logger.warning(f"Ошибка при обработке ответа от {addr}: {e}")
            
            sock.close()
            
        except Exception as e:
            logger.error(f"Ошибка при поиске серверов: {e}")
        
        return servers
    
    def _parse_server_response(self, data: bytes, addr: tuple) -> Optional[ServerInfo]:
        """
        Парсинг ответа от сервера.
        
        Args:
            data: Данные ответа
            addr: Адрес отправителя (ip, port)
            
        Returns:
            ServerInfo или None если данные некорректны
        """
        try:
            response = json.loads(data.decode('utf-8'))
            
            if response.get("type") != "server_response":
                return None
            
            # Проверяем обязательные поля
            required_fields = ["name", "port"]
            for field in required_fields:
                if field not in response:
                    logger.warning(f"В ответе от {addr} отсутствует поле {field}")
                    return None
            
            return ServerInfo(
                name=response["name"],
                ip=addr[0],  # IP из адреса отправителя
                port=response["port"],
                users_count=response.get("users_count", 0),
                is_password_protected=response.get("password_required", False),
                description=response.get("description", ""),
                version=response.get("version", "1.0"),
                max_users=response.get("max_users", 50),
                is_online=True,
                last_seen=time.time()
            )
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга ответа от {addr}: {e}")
            return None
    
    def _get_local_ip(self) -> str:
        """Получение локального IP адреса"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    def quick_discover(self) -> List[ServerInfo]:
        """
        Быстрый поиск серверов с меньшим таймаутом.
        
        Returns:
            Список найденных серверов
        """
        original_timeout = self.timeout
        self.timeout = 1.5  # Уменьшаем таймаут для быстрого поиска
        servers = self.discover_servers()
        self.timeout = original_timeout
        return servers


# Глобальный экземпляр для удобного доступа
_broadcast_client_instance: Optional[BroadcastClient] = None

def get_broadcast_client() -> BroadcastClient:
    """Получение глобального экземпляра BroadcastClient"""
    global _broadcast_client_instance
    if _broadcast_client_instance is None:
        _broadcast_client_instance = BroadcastClient()
    return _broadcast_client_instance


if __name__ == "__main__":
    # Тестирование
    print("Тестирование broadcast клиента...")
    client = BroadcastClient(timeout=2.0)
    servers = client.discover_servers()
    
    if servers:
        print(f"Найдено серверов: {len(servers)}")
        for i, server in enumerate(servers, 1):
            print(f"\n{i}. {server.name}")
            print(f"   Адрес: {server.ip}:{server.port}")
            print(f"   Пользователей: {server.users_count}")
            print(f"   Требуется пароль: {'Да' if server.is_password_protected else 'Нет'}")
    else:
        print("Серверы не найдены")