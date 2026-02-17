"""
Broadcast клиент для поиска серверов в локальной сети.
"""

import socket
import json
import time
import logging
import threading
from typing import List, Optional, Dict, Callable, Any
from client.models.server_info import ServerInfo

logger = logging.getLogger(__name__)


class BroadcastClient:
    """
    UDP клиент для поиска серверов мессенджера через broadcast.
    Поддерживает сканирование нескольких сетей.
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
        self.buffer_size = 1024
        self.discovery_in_progress = False
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        self.found_servers_count = 0
        self.scanned_networks = 0
        self.total_networks = 0
        
    def discover_servers(self, networks: List[Dict] = None) -> List[ServerInfo]:
        """
        Поиск серверов в сети.
        
        Args:
            networks: Список сетей для сканирования (если None, используется broadcast на все интерфейсы)
            
        Returns:
            Список найденных серверов
        """
        all_servers = []
        self.discovery_in_progress = True
        self.found_servers_count = 0
        
        try:
            if networks and len(networks) > 0:
                # Сканируем каждую сеть отдельно
                self.total_networks = len(networks)
                self.scanned_networks = 0
                
                for i, network in enumerate(networks):
                    if not self.discovery_in_progress:
                        break
                    
                    self.scanned_networks = i
                    
                    if self.progress_callback:
                        self.progress_callback(i, self.total_networks, 
                                             f"Сканирование {network.get('cidr', network.get('name', 'сети'))}")
                    
                    network_servers = self._discover_on_network(network)
                    
                    # Добавляем информацию о сети к каждому серверу
                    for server in network_servers:
                        server.discovery_network = network.get('cidr', network.get('name', 'unknown'))
                        server.discovery_interface = network.get('ip', '0.0.0.0')
                    
                    all_servers.extend(network_servers)
                    self.found_servers_count = len(all_servers)
                    
                    if self.progress_callback:
                        self.progress_callback(i + 1, self.total_networks, 
                                             f"Найдено {len(network_servers)} серверов в {network.get('cidr', 'сети')}")
            else:
                # Используем стандартный broadcast
                self.total_networks = 1
                self.scanned_networks = 0
                
                if self.progress_callback:
                    self.progress_callback(0, 1, "Сканирование сети...")
                
                all_servers = self._discover_broadcast()
                self.found_servers_count = len(all_servers)
                
                if self.progress_callback:
                    self.progress_callback(1, 1, f"Сканирование завершено. Найдено {len(all_servers)} серверов")
            
        except Exception as e:
            logger.error(f"Ошибка при поиске серверов: {e}")
        finally:
            self.discovery_in_progress = False
        
        # Выводим итоговую статистику
        if all_servers:
            logger.info(f"Всего найдено серверов: {len(all_servers)}")
            # Группируем по сетям
            servers_by_network = {}
            for server in all_servers:
                network = getattr(server, 'discovery_network', 'unknown')
                if network not in servers_by_network:
                    servers_by_network[network] = []
                servers_by_network[network].append(server)
            
            for network, servers in servers_by_network.items():
                online = sum(1 for s in servers if s.is_online)
                logger.info(f"  • {network}: {len(servers)} серверов ({online} онлайн)")
        
        return all_servers
    
    def _discover_on_network(self, network: Dict) -> List[ServerInfo]:
        """
        Поиск серверов в конкретной сети.
        
        Args:
            network: Информация о сети
            
        Returns:
            Список найденных серверов
        """
        servers = []
        
        try:
            # Создаем UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(min(self.timeout, 2.0))  # Уменьшаем таймаут для отдельных сетей
            
            # Пытаемся привязаться к конкретному интерфейсу
            bind_ip = network.get('ip', '0.0.0.0')
            if bind_ip != '0.0.0.0':
                try:
                    sock.bind((bind_ip, 0))
                    logger.debug(f"Привязан к интерфейсу {bind_ip}")
                except Exception as e:
                    logger.warning(f"Не удалось привязаться к {bind_ip}: {e}")
            
            # Формируем discovery запрос
            discovery_request = {
                "type": "discovery",
                "client_version": "1.0",
                "client_ip": bind_ip,
                "timestamp": time.time()
            }
            
            request_data = json.dumps(discovery_request).encode('utf-8')
            
            # Отправляем broadcast запрос
            broadcast_addr = network.get('broadcast', '255.255.255.255')
            sock.sendto(request_data, (broadcast_addr, self.broadcast_port))
            logger.debug(f"Отправлен broadcast запрос на {broadcast_addr}:{self.broadcast_port}")
            
            # Слушаем ответы от серверов
            start_time = time.time()
            network_servers = []
            
            while time.time() - start_time < self.timeout and self.discovery_in_progress:
                try:
                    data, addr = sock.recvfrom(self.buffer_size)
                    server_info = self._parse_server_response(data, addr)
                    
                    if server_info:
                        network_servers.append(server_info)
                        logger.info(f"Найден сервер: {server_info.name} ({server_info.ip}:{server_info.port})")
                        
                except socket.timeout:
                    break
                except json.JSONDecodeError as e:
                    logger.warning(f"Некорректный JSON от {addr}: {e}")
                except Exception as e:
                    logger.warning(f"Ошибка при обработке ответа от {addr}: {e}")
            
            sock.close()
            servers.extend(network_servers)
            
        except Exception as e:
            logger.error(f"Ошибка при поиске в сети {network.get('cidr', 'unknown')}: {e}")
        
        return servers
    
    def _discover_broadcast(self) -> List[ServerInfo]:
        """
        Стандартный broadcast поиск.
        
        Returns:
            Список найденных серверов
        """
        servers = []
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(self.timeout)
            
            # Получаем локальный IP
            local_ip = self._get_local_ip()
            
            discovery_request = {
                "type": "discovery",
                "client_version": "1.0",
                "client_ip": local_ip,
                "timestamp": time.time()
            }
            
            request_data = json.dumps(discovery_request).encode('utf-8')
            
            # Отправляем broadcast запрос
            sock.sendto(request_data, ('<broadcast>', self.broadcast_port))
            logger.debug(f"Отправлен broadcast запрос на порт {self.broadcast_port}")
            
            start_time = time.time()
            
            while time.time() - start_time < self.timeout and self.discovery_in_progress:
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
            logger.error(f"Ошибка при broadcast поиске: {e}")
        
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
            response = json.loads(data.decode('utf-8', errors='ignore'))
            
            if response.get("type") != "server_response":
                return None
            
            # Проверяем обязательные поля
            required_fields = ["name", "port"]
            for field in required_fields:
                if field not in response:
                    logger.warning(f"В ответе от {addr} отсутствует поле {field}")
                    return None
            
            server = ServerInfo(
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
            
            # Добавляем дополнительные атрибуты
            server.response_data = response
            server.discovery_network = "unknown"
            server.discovery_interface = "0.0.0.0"
            
            return server
            
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
    
    def discover_with_progress(self, networks: List[Dict] = None, callback: Callable = None) -> List[ServerInfo]:
        """
        Поиск с отслеживанием прогресса.
        
        Args:
            networks: Список сетей для сканирования
            callback: Функция обратного вызова для прогресса
            
        Returns:
            Список найденных серверов
        """
        self.progress_callback = callback
        return self.discover_servers(networks)
    
    def stop_discovery(self):
        """Остановка поиска"""
        self.discovery_in_progress = False
        logger.info("Поиск серверов остановлен")
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """Получение статистики поиска"""
        return {
            "in_progress": self.discovery_in_progress,
            "scanned_networks": self.scanned_networks,
            "total_networks": self.total_networks,
            "found_servers": self.found_servers_count
        }
    
    def quick_discover(self, networks: List[Dict] = None) -> List[ServerInfo]:
        """
        Быстрый поиск серверов с меньшим таймаутом.
        
        Args:
            networks: Список сетей для сканирования
            
        Returns:
            Список найденных серверов
        """
        original_timeout = self.timeout
        self.timeout = 1.5  # Уменьшаем таймаут для быстрого поиска
        servers = self.discover_servers(networks)
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