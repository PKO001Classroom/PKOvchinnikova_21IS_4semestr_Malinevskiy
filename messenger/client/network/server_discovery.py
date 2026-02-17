"""
Модуль для обнаружения доступных серверов в локальной сети через UDP broadcast.
Интегрирован с BroadcastClient.
"""

import threading
import time
import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass

from client.models.server_info import ServerInfo
from client.network.broadcast_client import BroadcastClient, get_broadcast_client

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    """Конфигурация для обнаружения серверов"""
    timeout: float = 3.0  # секунды
    discovery_interval: int = 30  # секунды между автоматическими поисками
    max_cache_age: int = 300  # секунд жизни кэша серверов


class ServerDiscovery:
    """
    Класс для обнаружения серверов мессенджера в локальной сети.
    Использует BroadcastClient для поиска серверов.
    """
    
    def __init__(self, config: Optional[DiscoveryConfig] = None):
        """
        Инициализация модуля обнаружения серверов.
        
        Args:
            config: Конфигурация обнаружения (используется дефолтная если None)
        """
        self.config = config or DiscoveryConfig()
        self.broadcast_client = get_broadcast_client()
        
        self.found_servers: Dict[str, ServerInfo] = {}  # ip:port -> ServerInfo
        self.discovery_thread: Optional[threading.Thread] = None
        self.is_discovering = False
        self.last_discovery_time = 0
        self.callbacks = []
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        
        logger.info("ServerDiscovery инициализирован с интеграцией BroadcastClient")
    
    def discover(self, networks: List[Dict] = None) -> List[ServerInfo]:
        """
        Активный поиск серверов в сети.
        
        Args:
            networks: Список сетей для сканирования
            
        Returns:
            Список обнаруженных серверов
        """
        logger.info("Начинаю поиск серверов в сети...")
        servers = []
        
        try:
            # Используем BroadcastClient для поиска
            if networks:
                self.broadcast_client.progress_callback = self._on_progress
                found_servers = self.broadcast_client.discover_servers(networks)
            else:
                found_servers = self.broadcast_client.discover_servers()
            
            # Обновляем кэш найденных серверов
            for server in found_servers:
                server_key = f"{server.ip}:{server.port}"
                
                # Обновляем или добавляем сервер
                if server_key in self.found_servers:
                    self.found_servers[server_key].last_seen = time.time()
                    self.found_servers[server_key].is_online = True
                    # Обновляем информацию о сети
                    if hasattr(server, 'discovery_network'):
                        self.found_servers[server_key].discovery_network = server.discovery_network
                else:
                    server.last_seen = time.time()
                    self.found_servers[server_key] = server
                
                servers.append(server)
                logger.info(f"Найден сервер: {server.name} ({server.ip}:{server.port})")
            
            # Помечаем старые серверы как оффлайн
            self._mark_offline_servers()
            
            # Выводим статистику
            stats = self.broadcast_client.get_discovery_stats()
            logger.info(f"Поиск завершен. Найдено серверов: {len(servers)}")
            
            if networks:
                # Группируем по сетям для отчета
                servers_by_network = {}
                for server in servers:
                    network = getattr(server, 'discovery_network', 'unknown')
                    if network not in servers_by_network:
                        servers_by_network[network] = []
                    servers_by_network[network].append(server)
                
                for network, net_servers in servers_by_network.items():
                    online = sum(1 for s in net_servers if s.is_online)
                    logger.info(f"  • {network}: {len(net_servers)} серверов ({online} онлайн)")
            
        except Exception as e:
            logger.error(f"Ошибка при поиске серверов: {e}")
        
        self.last_discovery_time = time.time()
        return list(self.found_servers.values())
    
    def _on_progress(self, current: int, total: int, message: str):
        """Обработка прогресса поиска"""
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def discover_with_progress(self, networks: List[Dict] = None, 
                              callback: Optional[Callable[[int, int, str], None]] = None) -> List[ServerInfo]:
        """
        Поиск серверов с отслеживанием прогресса.
        
        Args:
            networks: Список сетей для сканирования
            callback: Функция обратного вызова для прогресса
            
        Returns:
            Список найденных серверов
        """
        self.progress_callback = callback
        return self.discover(networks)
    
    def quick_discover(self, networks: List[Dict] = None) -> List[ServerInfo]:
        """
        Быстрый поиск серверов с меньшим таймаутом.
        
        Args:
            networks: Список сетей для сканирования
            
        Returns:
            Список найденных серверов
        """
        logger.info("Быстрый поиск серверов...")
        
        try:
            # Используем быстрый поиск BroadcastClient
            original_timeout = self.broadcast_client.timeout
            self.broadcast_client.timeout = 1.5
            
            servers = self.discover(networks)
            
            # Восстанавливаем таймаут
            self.broadcast_client.timeout = original_timeout
            
            return servers
            
        except Exception as e:
            logger.error(f"Ошибка быстрого поиска серверов: {e}")
            return []
    
    def _mark_offline_servers(self):
        """Помечает серверы как оффлайн если они не отвечали долгое время"""
        current_time = time.time()
        offline_timeout = self.config.max_cache_age
        
        for server_key, server in list(self.found_servers.items()):
            if server.last_seen and (current_time - server.last_seen) > offline_timeout:
                server.is_online = False
                logger.debug(f"Сервер {server.name} помечен как оффлайн")
    
    def start_continuous_discovery(self, networks: List[Dict] = None):
        """
        Запуск непрерывного фонового поиска серверов.
        
        Args:
            networks: Список сетей для сканирования
        """
        if self.is_discovering:
            logger.warning("Поиск уже запущен")
            return
        
        self.is_discovering = True
        self.discovery_thread = threading.Thread(
            target=self._discovery_loop,
            args=(networks,),
            daemon=True,
            name="ServerDiscoveryThread"
        )
        self.discovery_thread.start()
        logger.info("Запущен фоновый поиск серверов")
    
    def _discovery_loop(self, networks: List[Dict] = None):
        """Фоновый цикл поиска серверов"""
        while self.is_discovering:
            try:
                servers = self.discover(networks)
                
                # Вызываем колбэки если есть новые серверы
                if servers and self.callbacks:
                    for callback in self.callbacks:
                        try:
                            callback(servers)
                        except Exception as e:
                            logger.error(f"Ошибка в колбэке: {e}")
                
                # Ждем перед следующим поиском
                time.sleep(self.config.discovery_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле поиска: {e}")
                time.sleep(5)  # Краткая пауза при ошибке
    
    def stop_continuous_discovery(self):
        """Остановка фонового поиска"""
        self.is_discovering = False
        if self.discovery_thread:
            self.discovery_thread.join(timeout=2)
        logger.info("Фоновый поиск серверов остановлен")
    
    def stop_discovery(self):
        """Остановка текущего поиска"""
        self.broadcast_client.stop_discovery()
    
    def add_callback(self, callback):
        """
        Добавление callback функции, которая вызывается при обнаружении новых серверов.
        
        Args:
            callback: Функция, принимающая список ServerInfo
        """
        if callable(callback):
            self.callbacks.append(callback)
    
    def remove_callback(self, callback):
        """Удаление callback функции"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def get_online_servers(self) -> List[ServerInfo]:
        """
        Получение списка только онлайн серверов.
        
        Returns:
            Список онлайн серверов
        """
        return [server for server in self.found_servers.values() if server.is_online]
    
    def get_server_by_address(self, ip: str, port: int) -> Optional[ServerInfo]:
        """
        Поиск сервера по адресу.
        
        Args:
            ip: IP адрес сервера
            port: Порт сервера
            
        Returns:
            ServerInfo или None если не найден
        """
        server_key = f"{ip}:{port}"
        return self.found_servers.get(server_key)
    
    def get_servers_by_network(self) -> Dict[str, List[ServerInfo]]:
        """
        Получение серверов, сгруппированных по сетям.
        
        Returns:
            Словарь {сеть: [серверы]}
        """
        result = {}
        for server in self.found_servers.values():
            network = getattr(server, 'discovery_network', 'unknown')
            if network not in result:
                result[network] = []
            result[network].append(server)
        return result
    
    def clear_cache(self):
        """Очистка кэша найденных серверов"""
        self.found_servers.clear()
        logger.info("Кэш серверов очищен")
    
    def check_server_availability(self, ip: str, port: int, timeout: float = 2.0) -> bool:
        """
        Проверка доступности конкретного сервера.
        
        Args:
            ip: IP адрес сервера
            port: Порт сервера
            timeout: Таймаут проверки
            
        Returns:
            True если сервер доступен
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False


# Синглтон для глобального доступа
_discovery_instance: Optional[ServerDiscovery] = None

def get_discovery_instance() -> ServerDiscovery:
    """Получение глобального экземпляра ServerDiscovery"""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = ServerDiscovery()
    return _discovery_instance


def discover_servers_once(networks: List[Dict] = None) -> List[ServerInfo]:
    """
    Упрощенная функция для одноразового поиска серверов.
    
    Args:
        networks: Список сетей для сканирования
        
    Returns:
        Список найденных серверов
    """
    return get_discovery_instance().discover(networks)


def quick_discover_servers(networks: List[Dict] = None) -> List[ServerInfo]:
    """
    Быстрый одноразовый поиск серверов.
    
    Args:
        networks: Список сетей для сканирования
        
    Returns:
        Список найденных серверов
    """
    return get_discovery_instance().quick_discover(networks)