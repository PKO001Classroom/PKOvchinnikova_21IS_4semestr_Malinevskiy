"""
Диалог выбора сервера для подключения.
Показывает список доступных серверов в сети и позволяет выбрать или создать новый.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QProgressBar, QSplitter,
    QFrame, QGroupBox, QFormLayout, QLineEdit, QTextEdit,
    QCheckBox, QInputDialog, QTabWidget, QWidget, QGridLayout,
    QApplication, QStackedWidget, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPixmap
import socket
import time
import ipaddress
import subprocess
import re
import platform
from typing import Optional, List, Dict, Any, Tuple

# Импорт модулей из новой структуры - добавляем client.
try:
    from client.config import APP_NAME, APP_VERSION
    from client.network.server_discovery import get_discovery_instance, quick_discover_servers
    from client.server_manager import get_server_manager
    from client.models.server_info import ServerInfo  # Импортируем ServerInfo
    from client.auth_manager import get_auth_manager
except ImportError as e:
    print(f"Ошибка импорта в server_browser_dialog.py: {e}")


class DiscoveryWorker(QThread):
    """
    Рабочий поток для поиска серверов в сети.
    Выполняет поиск в фоне чтобы не блокировать UI.
    """
    servers_found = pyqtSignal(list)
    discovery_progress = pyqtSignal(int, int, str)  # current, total, message
    discovery_finished = pyqtSignal()
    discovery_error = pyqtSignal(str)
    ip_scanned = pyqtSignal(str, bool)  # ip, found
    
    def __init__(self, quick_mode: bool = False):
        super().__init__()
        self.quick_mode = quick_mode
        self.discovery = get_discovery_instance()
        self.is_running = True
        self.networks = None  # Список сетей для сканирования
        self.scanned_ips = []
        self.found_servers = []
        
    def run(self):
        """Основной метод потока"""
        try:
            self.discovery_progress.emit(0, 1, "Подготовка...")
            
            if self.networks:
                # Поиск с выбором сетей
                total_networks = len(self.networks)
                
                def progress_callback(current, total, message):
                    if self.is_running:
                        self.discovery_progress.emit(current, total, message)
                        # Извлекаем IP из сообщения если есть
                        if ":" in message:
                            ip_part = message.split(":")[-1].strip()
                            if ip_part and ip_part not in self.scanned_ips:
                                self.scanned_ips.append(ip_part)
                                self.ip_scanned.emit(ip_part, False)
                
                # Устанавливаем callback для broadcast клиента
                if hasattr(self.discovery, 'broadcast_client'):
                    self.discovery.broadcast_client.progress_callback = progress_callback
                
                if self.quick_mode:
                    servers = self.discovery.quick_discover_servers(self.networks)
                else:
                    servers = self.discovery.discover_servers(self.networks)
            else:
                # Стандартный поиск
                self.discovery_progress.emit(0, 1, "Поиск серверов...")
                
                if self.quick_mode:
                    servers = self.discovery.quick_discover_servers()
                else:
                    servers = self.discovery.discover_servers()
                
                self.discovery_progress.emit(1, 1, f"Найдено {len(servers)} серверов")
            
            if self.is_running:
                self.found_servers = servers
                self.servers_found.emit(servers)
                
        except Exception as e:
            if self.is_running:
                self.discovery_error.emit(str(e))
        finally:
            self.discovery_finished.emit()
            
    def stop(self):
        """Остановка потока"""
        self.is_running = False
        if hasattr(self.discovery, 'broadcast_client'):
            self.discovery.broadcast_client.stop_discovery()
        self.wait()


class NetworkScanner:
    """Класс для сканирования сетей и получения информации о них без использования netifaces"""
    
    @staticmethod
    def get_network_interfaces_windows() -> List[Dict[str, Any]]:
        """Получение сетевых интерфейсов в Windows через ipconfig"""
        interfaces = []
        
        try:
            # Запускаем ipconfig
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='cp866')
            output = result.stdout
            
            # Парсим вывод ipconfig
            lines = output.split('\n')
            current_iface = {}
            
            for line in lines:
                line = line.strip()
                
                # Начало нового интерфейса
                if 'адаптер' in line.lower() or 'adapter' in line.lower():
                    if current_iface and 'ip' in current_iface:
                        interfaces.append(current_iface)
                    current_iface = {'name': line.strip()}
                
                # IPv4 адрес
                elif 'IPv4' in line or 'ipv4' in line.lower():
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        current_iface['ip'] = match.group(1)
                
                # Маска подсети
                elif 'маска' in line.lower() or 'mask' in line.lower():
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        current_iface['netmask'] = match.group(1)
            
            # Добавляем последний интерфейс
            if current_iface and 'ip' in current_iface:
                interfaces.append(current_iface)
                
        except Exception as e:
            print(f"Ошибка получения сетевых интерфейсов Windows: {e}")
            
        return interfaces
    
    @staticmethod
    def get_network_interfaces_linux() -> List[Dict[str, Any]]:
        """Получение сетевых интерфейсов в Linux через ifconfig или ip addr"""
        interfaces = []
        
        try:
            # Пробуем ip addr
            result = subprocess.run(['ip', 'addr'], capture_output=True, text=True)
            output = result.output
            
            lines = output.split('\n')
            current_iface = {}
            
            for line in lines:
                line = line.strip()
                
                # Начало интерфейса
                if ': <' in line or ':' in line and not line.startswith(' '):
                    if current_iface and 'ip' in current_iface:
                        interfaces.append(current_iface)
                    iface_name = line.split(':')[1].strip()
                    current_iface = {'name': iface_name}
                
                # IPv4 адрес
                elif 'inet ' in line and not 'inet6' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip_net = parts[1].split('/')
                        current_iface['ip'] = ip_net[0]
                        if len(ip_net) > 1:
                            # Конвертируем CIDR в маску
                            cidr = int(ip_net[1])
                            mask = (0xffffffff >> (32 - cidr)) << (32 - cidr)
                            current_iface['netmask'] = '.'.join([str((mask >> (8*i)) & 0xff) for i in range(3, -1, -1)])
            
            # Добавляем последний интерфейс
            if current_iface and 'ip' in current_iface:
                interfaces.append(current_iface)
                
        except Exception as e:
            print(f"Ошибка получения сетевых интерфейсов Linux: {e}")
            
        return interfaces
    
    @staticmethod
    def get_network_interfaces_mac() -> List[Dict[str, Any]]:
        """Получение сетевых интерфейсов в macOS через ifconfig"""
        interfaces = []
        
        try:
            result = subprocess.run(['ifconfig'], capture_output=True, text=True)
            output = result.output
            
            lines = output.split('\n')
            current_iface = {}
            
            for line in lines:
                line = line.strip()
                
                # Начало интерфейса
                if ': flags=' in line:
                    if current_iface and 'ip' in current_iface:
                        interfaces.append(current_iface)
                    iface_name = line.split(':')[0]
                    current_iface = {'name': iface_name}
                
                # inet addr
                elif 'inet ' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        current_iface['ip'] = parts[1]
                    if 'netmask' in line:
                        for i, part in enumerate(parts):
                            if part == 'netmask' and i + 1 < len(parts):
                                netmask_hex = parts[i+1]
                                # Конвертируем hex в десятичный формат
                                if netmask_hex.startswith('0x'):
                                    mask_int = int(netmask_hex, 16)
                                    current_iface['netmask'] = '.'.join([
                                        str((mask_int >> 24) & 0xff),
                                        str((mask_int >> 16) & 0xff),
                                        str((mask_int >> 8) & 0xff),
                                        str(mask_int & 0xff)
                                    ])
            
            # Добавляем последний интерфейс
            if current_iface and 'ip' in current_iface:
                interfaces.append(current_iface)
                
        except Exception as e:
            print(f"Ошибка получения сетевых интерфейсов macOS: {e}")
            
        return interfaces
    
    @staticmethod
    def get_network_interfaces() -> List[Dict[str, Any]]:
        """Получение списка сетевых интерфейсов в зависимости от ОС"""
        system = platform.system()
        
        if system == 'Windows':
            interfaces = NetworkScanner.get_network_interfaces_windows()
        elif system == 'Linux':
            interfaces = NetworkScanner.get_network_interfaces_linux()
        elif system == 'Darwin':  # macOS
            interfaces = NetworkScanner.get_network_interfaces_mac()
        else:
            interfaces = []
        
        # Фильтруем интерфейсы и добавляем CIDR
        result = []
        for iface in interfaces:
            ip = iface.get('ip', '')
            netmask = iface.get('netmask', '')
            
            # Пропускаем loopback
            if ip.startswith('127.'):
                continue
                
            # Если нет маски, пробуем определить по классу IP
            if not netmask and ip:
                # Определяем маску по классу IP
                first_octet = int(ip.split('.')[0])
                if first_octet < 128:
                    netmask = '255.0.0.0'
                elif first_octet < 192:
                    netmask = '255.255.0.0'
                else:
                    netmask = '255.255.255.0'
            
            # Вычисляем сеть
            if ip and netmask:
                try:
                    # Конвертируем IP и маску в числа
                    ip_int = NetworkScanner.ip_to_int(ip)
                    mask_int = NetworkScanner.ip_to_int(netmask)
                    network_int = ip_int & mask_int
                    network = NetworkScanner.int_to_ip(network_int)
                    
                    # Определяем CIDR
                    cidr = bin(mask_int).count('1')
                    
                    result.append({
                        'name': iface.get('name', 'Неизвестный интерфейс'),
                        'ip': ip,
                        'netmask': netmask,
                        'network': f"{network}/{cidr}",
                        'cidr': f"{network}/{cidr}"
                    })
                except Exception as e:
                    print(f"Ошибка вычисления сети для {ip}: {e}")
        
        return result
    
    @staticmethod
    def ip_to_int(ip: str) -> int:
        """Конвертация IP адреса в число"""
        parts = ip.split('.')
        return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])
    
    @staticmethod
    def int_to_ip(ip_int: int) -> str:
        """Конвертация числа в IP адрес"""
        return f"{(ip_int >> 24) & 0xff}.{(ip_int >> 16) & 0xff}.{(ip_int >> 8) & 0xff}.{ip_int & 0xff}"
    
    @staticmethod
    def get_all_networks() -> List[Dict[str, Any]]:
        """Получение всех доступных сетей"""
        return NetworkScanner.get_network_interfaces()


class NetworkSelectionDialog(QDialog):
    """Диалог выбора сети для сканирования"""
    
    networks_selected = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 Выбор сети для сканирования")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("Выберите сети для сканирования")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Информация
        info = QLabel("Можно выбрать несколько сетей. Сканирование всех сетей может занять время.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Список сетей
        self.network_list = QListWidget()
        self.network_list.setSelectionMode(QListWidget.MultiSelection)
        self.network_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        
        # Загружаем сети
        self.networks = NetworkScanner.get_all_networks()
        
        if not self.networks:
            # Если не удалось определить сети, добавляем стандартные
            item = QListWidgetItem("⚠️ Не удалось определить сети автоматически")
            item.setFlags(Qt.NoItemFlags)
            self.network_list.addItem(item)
            
            # Добавляем стандартные варианты
            default_networks = [
                {"name": "Локальная сеть 192.168.1.x", "cidr": "192.168.1.0/24", "ip": "192.168.1.1", "netmask": "255.255.255.0"},
                {"name": "Локальная сеть 192.168.0.x", "cidr": "192.168.0.0/24", "ip": "192.168.0.1", "netmask": "255.255.255.0"},
                {"name": "Локальная сеть 10.0.0.x", "cidr": "10.0.0.0/24", "ip": "10.0.0.1", "netmask": "255.255.255.0"},
                {"name": "Локальная сеть 172.16.x.x", "cidr": "172.16.0.0/16", "ip": "172.16.0.1", "netmask": "255.255.0.0"},
            ]
            
            for net in default_networks:
                item = QListWidgetItem(f"🌐 {net['name']}")
                item.setData(Qt.UserRole, net)
                item.setSelected(True)
                self.network_list.addItem(item)
        else:
            for net in self.networks:
                item = QListWidgetItem(f"🌐 {net['name']} - {net['cidr']}")
                item.setData(Qt.UserRole, net)
                item.setSelected(True)  # По умолчанию все выбраны
                self.network_list.addItem(item)
                
        layout.addWidget(self.network_list)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("✅ Выбрать все")
        select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("❌ Очистить все")
        clear_all_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(clear_all_btn)
        
        layout.addLayout(btn_layout)
        
        # Кнопки OK/Cancel
        button_box = QHBoxLayout()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        button_box.addWidget(cancel_btn)
        
        button_box.addStretch()
        
        ok_btn = QPushButton("Сканировать")
        ok_btn.clicked.connect(self.accept_selection)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        button_box.addWidget(ok_btn)
        
        layout.addLayout(button_box)
        
        self.setLayout(layout)
        
    def select_all(self):
        """Выбрать все сети"""
        for i in range(self.network_list.count()):
            item = self.network_list.item(i)
            if item.flags() & Qt.ItemIsSelectable:
                item.setSelected(True)
                
    def clear_all(self):
        """Очистить выбор"""
        self.network_list.clearSelection()
        
    def accept_selection(self):
        """Подтверждение выбора"""
        selected = []
        for item in self.network_list.selectedItems():
            net_data = item.data(Qt.UserRole)
            if net_data:
                selected.append(net_data)
                
        if not selected:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы одну сеть")
            return
            
        self.networks_selected.emit(selected)
        self.accept()


class ServerBrowserDialog(QDialog):
    """
    Диалог выбора сервера.
    
    Показывает:
    1. Список найденных серверов в сети
    2. Детальную информацию о выбранном сервере
    3. Возможность обновить список
    4. Возможность создать новый сервер
    5. Возможность запустить сохраненный сервер
    """
    
    server_selected = pyqtSignal(dict)  # Сигнал с выбранным сервером
    
    def __init__(self, parent=None, show_quick_discover: bool = True):
        super().__init__(parent)
        
        # Инициализация менеджеров
        self.server_discovery = get_discovery_instance()
        self.server_manager = get_server_manager()
        self.auth_manager = get_auth_manager()
        self.discovery_worker = None
        
        # Данные
        self.found_servers: List[ServerInfo] = []
        self.saved_servers: List[dict] = []
        self.selected_server: Optional[ServerInfo] = None
        self.scanned_ips = []
        
        # UI элементы
        self.servers_list: Optional[QListWidget] = None
        self.server_info_label: Optional[QLabel] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.refresh_btn: Optional[QPushButton] = None
        self.connect_btn: Optional[QPushButton] = None
        self.create_btn: Optional[QPushButton] = None
        
        # Таймеры
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_server_status)
        
        self.init_ui()
        self.load_saved_servers()
        
        # Запускаем быстрый поиск если нужно
        if show_quick_discover:
            self.start_quick_discovery()
        else:
            self.start_discovery()
        
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle(f"🌐 Выбор сервера - {APP_NAME}")
        self.setGeometry(300, 200, 1000, 750)
        self.setMinimumSize(900, 650)
        
        # Устанавливаем иконку
        try:
            self.setWindowIcon(QIcon("icon.ico"))
        except:
            pass
        
        # Основной layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Заголовок
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Выбор сервера для подключения")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #1976d2; padding: 5px;")
        header_layout.addWidget(title_label)
        
        subtitle_label = QLabel(f"{APP_NAME} v{APP_VERSION} - Подключитесь к существующему серверу или создайте новый")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #666; font-size: 12px; padding-bottom: 10px;")
        header_layout.addWidget(subtitle_label)
        
        main_layout.addWidget(header_widget)
        
        # Создаем стек виджетов для разных состояний
        self.stacked_widget = QStackedWidget()
        
        # Экран загрузки
        self.loading_screen = self.create_loading_screen()
        self.stacked_widget.addWidget(self.loading_screen)
        
        # Основной экран
        self.main_screen = self.create_main_screen()
        self.stacked_widget.addWidget(self.main_screen)
        
        # Экран ошибки
        self.error_screen = self.create_error_screen()
        self.stacked_widget.addWidget(self.error_screen)
        
        main_layout.addWidget(self.stacked_widget)
        
        # Статусная строка
        self.status_label = QLabel("Готов к работе")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 11px;
                padding: 8px;
                background-color: #f9f9f9;
                border-radius: 4px;
                border: 1px solid #eee;
            }
        """)
        main_layout.addWidget(self.status_label)
        
        # Панель кнопок
        button_panel = self.create_button_panel()
        main_layout.addWidget(button_panel)
        
        self.setLayout(main_layout)
        
        # Начинаем с экрана загрузки
        self.stacked_widget.setCurrentWidget(self.loading_screen)
        
    def show_network_selector(self):
        """Показать диалог выбора сети"""
        dialog = NetworkSelectionDialog(self)
        
        def on_networks_selected(networks):
            self.selected_networks = networks
            network_names = ", ".join([n['cidr'] for n in networks[:3]])
            if len(networks) > 3:
                network_names += f" и еще {len(networks)-3}"
            self.status_label.setText(f"Выбрано сетей: {len(networks)} ({network_names})")
            # Запускаем сканирование с выбранными сетями
            self.start_discovery_with_networks(networks)
        
        dialog.networks_selected.connect(on_networks_selected)
        dialog.exec_()

    def start_discovery_with_networks(self, networks: List[Dict]):
        """Запуск поиска с выбранными сетями"""
        self.stacked_widget.setCurrentWidget(self.loading_screen)
        self.loading_progress.setValue(0)
        self.loading_progress.setFormat("Подготовка... 0%")
        
        self.status_label.setText(f"Сканирование {len(networks)} сетей...")
        
        # Обновляем информацию о сетях
        network_info = "\n".join([f"  • {n['cidr']} ({n['ip']})" for n in networks[:5]])
        if len(networks) > 5:
            network_info += f"\n  • и еще {len(networks) - 5} сетей"
        
        self.scan_info_label.setText(f"Сканируемые сети:\n{network_info}")
        
        # Очищаем список найденных IP
        self.scanned_ips = []
        self.ip_list_label.setText("Найденные IP: ожидание...")
        
        # Отключаем кнопки
        self.refresh_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        
        # Запускаем поток поиска с выбранными сетями
        self.discovery_worker = DiscoveryWorker(quick_mode=False)
        self.discovery_worker.networks = networks
        self.discovery_worker.servers_found.connect(self.on_servers_found)
        self.discovery_worker.discovery_progress.connect(self.update_discovery_progress)
        self.discovery_worker.discovery_error.connect(self.on_discovery_error)
        self.discovery_worker.finished.connect(self.on_discovery_finished)
        self.discovery_worker.start()

    def update_discovery_progress(self, current: int, total: int, message: str):
        """Обновление прогресса сканирования"""
        if total > 0:
            progress = int((current / total) * 100)
            self.loading_progress.setValue(progress)
            self.loading_progress.setFormat(f"{message} {progress}%")
            
            # Обновляем информацию о найденных серверах
            if hasattr(self, 'found_servers'):
                self.status_label.setText(f"Найдено серверов: {len(self.found_servers)} | Сканировано: {current}/{total}")
                
            # Добавляем информацию о сканируемом IP
            if ":" in message:
                ip_part = message.split(":")[-1].strip()
                if ip_part and ip_part not in self.scanned_ips:
                    self.scanned_ips.append(ip_part)
                    if len(self.scanned_ips) > 20:
                        display_ips = self.scanned_ips[:20] + ["..."]
                    else:
                        display_ips = self.scanned_ips
                    self.ip_list_label.setText(f"Сканировано IP: {', '.join(display_ips)}")
        
    def create_loading_screen(self) -> QWidget:
        """Создание экрана загрузки"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        # Анимация загрузки
        loading_label = QLabel("🔍 Поиск серверов в сети...")
        loading_font = QFont()
        loading_font.setPointSize(14)
        loading_label.setFont(loading_font)
        loading_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(loading_label)
        
        # Прогресс бар
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setTextVisible(True)
        self.loading_progress.setFormat("Поиск... %p%")
        self.loading_progress.setMinimumWidth(400)
        self.loading_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.loading_progress, 0, Qt.AlignCenter)
        
        # Информация о сканировании
        self.scan_info_label = QLabel("")
        self.scan_info_label.setAlignment(Qt.AlignCenter)
        self.scan_info_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 10px;")
        self.scan_info_label.setWordWrap(True)
        layout.addWidget(self.scan_info_label)
        
        # Список найденных IP
        ip_group = QGroupBox("📡 Сканируемые IP")
        ip_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                margin-top: 10px;
            }
        """)
        ip_layout = QVBoxLayout()
        self.ip_list_label = QLabel("Ожидание сканирования...")
        self.ip_list_label.setWordWrap(True)
        self.ip_list_label.setStyleSheet("color: #2196F3; font-size: 11px;")
        ip_layout.addWidget(self.ip_list_label)
        ip_group.setLayout(ip_layout)
        layout.addWidget(ip_group)
        
        # Кнопка остановки
        self.stop_scan_btn = QPushButton("⏹️ Остановить сканирование")
        self.stop_scan_btn.clicked.connect(self.stop_discovery)
        self.stop_scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        layout.addWidget(self.stop_scan_btn, 0, Qt.AlignCenter)
        
        # Подсказка
        hint_label = QLabel("Это может занять несколько секунд в зависимости от количества сетей")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("color: #888; font-style: italic; margin-top: 20px;")
        layout.addWidget(hint_label)
        
        widget.setLayout(layout)
        return widget
    
    def stop_discovery(self):
        """Остановка поиска серверов"""
        if self.discovery_worker and self.discovery_worker.isRunning():
            self.discovery_worker.stop()
            self.status_label.setText("⏹️ Поиск остановлен пользователем")
            self.stacked_widget.setCurrentWidget(self.main_screen)
        
    def create_main_screen(self) -> QWidget:
        """Создание основного экрана"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Создаем разделитель
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Левая панель - список серверов
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - информация о сервере
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Устанавливаем пропорции
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
        widget.setLayout(layout)
        return widget
        
    def create_left_panel(self) -> QWidget:
        """Создание левой панели со списком серверов"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Панель управления
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # Вкладки: Найденные и Сохраненные серверы
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
                background-color: #f5f5f5;
                border: 1px solid #ccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #1976d2;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #e8e8e8;
            }
        """)
        
        # Вкладка найденных серверов
        found_tab = QWidget()
        found_layout = QVBoxLayout(found_tab)
        found_layout.setContentsMargins(5, 5, 5, 5)
        
        found_label = QLabel("Серверы в сети:")
        found_label.setStyleSheet("font-weight: bold; color: #1976d2; font-size: 13px; padding: 5px;")
        found_layout.addWidget(found_label)
        
        self.servers_list = QListWidget()
        self.servers_list.itemClicked.connect(self.on_server_selected)
        self.servers_list.itemDoubleClicked.connect(self.on_server_double_clicked)
        self.servers_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: white;
                font-size: 12px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px 10px;
                border-bottom: 1px solid #f0f0f0;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
                border: 1px solid #bbdefb;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            QListWidget::item:last {
                border-bottom: none;
            }
        """)
        found_layout.addWidget(self.servers_list)
        
        # Счетчик найденных серверов
        self.found_count_label = QLabel("Найдено: 0")
        self.found_count_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        found_layout.addWidget(self.found_count_label)
        
        self.tab_widget.addTab(found_tab, "🌐 В сети")
        
        # Вкладка сохраненных серверов
        saved_tab = QWidget()
        saved_layout = QVBoxLayout(saved_tab)
        saved_layout.setContentsMargins(5, 5, 5, 5)
        
        saved_label = QLabel("Сохраненные серверы:")
        saved_label.setStyleSheet("font-weight: bold; color: #9C27B0; font-size: 13px; padding: 5px;")
        saved_layout.addWidget(saved_label)
        
        self.saved_servers_list = QListWidget()
        self.saved_servers_list.itemClicked.connect(self.on_saved_server_selected)
        self.saved_servers_list.itemDoubleClicked.connect(self.on_saved_server_double_clicked)
        self.saved_servers_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: white;
                font-size: 12px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px 10px;
                border-bottom: 1px solid #f0f0f0;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #f3e5f5;
                color: #7b1fa2;
                border: 1px solid #e1bee7;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        saved_layout.addWidget(self.saved_servers_list)
        
        # Счетчик сохраненных серверов
        self.saved_count_label = QLabel("Сохранено: 0")
        self.saved_count_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        saved_layout.addWidget(self.saved_count_label)
        
        self.tab_widget.addTab(saved_tab, "💾 Сохраненные")
        
        layout.addWidget(self.tab_widget)
        
        # Кнопки обновления и выбора сети
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Обновить список")
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.clicked.connect(self.start_discovery)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        btn_layout.addWidget(self.refresh_btn)
        
        self.network_select_btn = QPushButton("🌐 Выбрать сети")
        self.network_select_btn.setObjectName("networkBtn")
        self.network_select_btn.clicked.connect(self.show_network_selector)
        self.network_select_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        btn_layout.addWidget(self.network_select_btn)
        
        # Кнопка запуска сохраненного сервера
        self.start_saved_btn = QPushButton("▶️ Запустить выбранный")
        self.start_saved_btn.setObjectName("startSavedBtn")
        self.start_saved_btn.clicked.connect(self.on_start_server_clicked)
        self.start_saved_btn.setEnabled(False)
        self.start_saved_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        btn_layout.addWidget(self.start_saved_btn)
        
        layout.addLayout(btn_layout)
        
        # Информация о текущем сканировании
        self.scan_info_panel = QLabel("")
        self.scan_info_panel.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f5f5f5; border-radius: 4px;")
        self.scan_info_panel.setWordWrap(True)
        layout.addWidget(self.scan_info_panel)
        
        panel.setLayout(layout)
        return panel
        
    def create_right_panel(self) -> QWidget:
        """Создание правой панели с информацией о сервере"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(15)
        
        # Группа информации о сервере
        info_group = QGroupBox("📋 Информация о сервере")
        info_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #1976d2;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #f9f9f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
            }
        """)
        info_layout = QVBoxLayout()
        
        self.server_info_text = QTextEdit()
        self.server_info_text.setReadOnly(True)
        self.server_info_text.setMaximumHeight(250)
        self.server_info_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 15px;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        self.server_info_text.setHtml("""
            <div style='text-align: center; padding: 40px 20px;'>
                <h3 style='color: #666; margin-bottom: 15px;'>Выберите сервер из списка</h3>
                <p style='color: #999; margin-bottom: 10px;'>Серверы будут отображены после завершения поиска</p>
                <div style='background-color: #f5f5f5; padding: 15px; border-radius: 8px; margin-top: 20px;'>
                    <p style='color: #666; font-size: 11px; margin: 5px 0;'>🟢 - сервер онлайн и доступен</p>
                    <p style='color: #666; font-size: 11px; margin: 5px 0;'>⚫ - сервер оффлайн или недоступен</p>
                    <p style='color: #666; font-size: 11px; margin: 5px 0;'>🔒 - требуется пароль для запуска</p>
                    <p style='color: #666; font-size: 11px; margin: 5px 0;'>👥 - количество пользователей онлайн</p>
                </div>
            </div>
        """)
        info_layout.addWidget(self.server_info_text)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Группа действий
        actions_group = QGroupBox("🚀 Действия с сервером")
        actions_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #1976d2;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #f9f9f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
            }
        """)
        actions_layout = QGridLayout()
        actions_layout.setSpacing(15)
        actions_layout.setContentsMargins(10, 15, 10, 15)
        
        row = 0
        
        # Кнопка подключения
        self.connect_btn = QPushButton("🔗 Подключиться к серверу")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.connect_btn.setEnabled(False)
        self.connect_btn.setMinimumHeight(50)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 14px;
                padding: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
                cursor: not-allowed;
            }
        """)
        actions_layout.addWidget(self.connect_btn, row, 0, 1, 2)
        
        row += 1
        
        # Кнопка создания сервера
        self.create_btn = QPushButton("➕ Создать новый сервер")
        self.create_btn.setObjectName("createBtn")
        self.create_btn.clicked.connect(self.create_server)
        self.create_btn.setMinimumHeight(45)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        actions_layout.addWidget(self.create_btn, row, 0)
        
        # Кнопка запуска сервера
        self.start_server_btn = QPushButton("⚡ Запустить сервер")
        self.start_server_btn.setObjectName("startBtn")
        self.start_server_btn.clicked.connect(self.on_start_server_clicked)
        self.start_server_btn.setEnabled(False)
        self.start_server_btn.setMinimumHeight(45)
        self.start_server_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        actions_layout.addWidget(self.start_server_btn, row, 1)
        
        row += 1
        
        # Кнопки редактирования
        edit_layout = QHBoxLayout()
        edit_layout.setSpacing(10)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.on_edit_clicked)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        edit_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        edit_layout.addWidget(self.delete_btn)
        
        actions_layout.addLayout(edit_layout, row, 0, 1, 2)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # Группа статистики
        stats_group = QGroupBox("📊 Статистика сети")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #1976d2;
                border: 1px solid #bbdefb;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #f9f9f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
            }
        """)
        stats_layout = QFormLayout()
        stats_layout.setSpacing(12)
        stats_layout.setContentsMargins(15, 15, 15, 15)
        
        self.stats_found_label = QLabel("0")
        self.stats_found_label.setStyleSheet("font-weight: bold; color: #2196F3; font-size: 13px;")
        stats_layout.addRow("🌐 Найдено серверов:", self.stats_found_label)
        
        self.stats_online_label = QLabel("0")
        self.stats_online_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 13px;")
        stats_layout.addRow("🟢 Онлайн серверов:", self.stats_online_label)
        
        self.stats_saved_label = QLabel("0")
        self.stats_saved_label.setStyleSheet("font-weight: bold; color: #9C27B0; font-size: 13px;")
        stats_layout.addRow("💾 Сохранено серверов:", self.stats_saved_label)
        
        self.stats_protected_label = QLabel("0")
        self.stats_protected_label.setStyleSheet("font-weight: bold; color: #FF9800; font-size: 13px;")
        stats_layout.addRow("🔒 С защитой паролем:", self.stats_protected_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Растягивающийся спейсер
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
        
    def create_error_screen(self) -> QWidget:
        """Создание экрана ошибки"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        error_label = QLabel("⚠️ Не удалось найти серверы")
        error_font = QFont()
        error_font.setPointSize(14)
        error_label.setFont(error_font)
        error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(error_label)
        
        error_details = QLabel("Проверьте подключение к сети и попробуйте снова")
        error_details.setAlignment(Qt.AlignCenter)
        error_details.setStyleSheet("color: #888; margin: 20px 0;")
        layout.addWidget(error_details)
        
        # Кнопка выбора сети
        network_btn = QPushButton("🌐 Выбрать сеть для сканирования")
        network_btn.clicked.connect(self.show_network_selector)
        network_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        layout.addWidget(network_btn, 0, Qt.AlignCenter)
        
        # Кнопка запуска сохраненного сервера
        saved_btn = QPushButton("💾 Запустить сохраненный сервер")
        saved_btn.clicked.connect(lambda: self.tab_widget.setCurrentIndex(1))
        saved_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(saved_btn, 0, Qt.AlignCenter)
        
        # Кнопка создания сервера
        create_btn = QPushButton("➕ Создать новый сервер")
        create_btn.clicked.connect(self.create_server)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        layout.addWidget(create_btn, 0, Qt.AlignCenter)
        
        # Кнопка повтора
        retry_btn = QPushButton("🔄 Попробовать снова")
        retry_btn.clicked.connect(self.start_discovery)
        retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        layout.addWidget(retry_btn, 0, Qt.AlignCenter)
        
        widget.setLayout(layout)
        return widget
        
    def create_button_panel(self) -> QFrame:
        """Создание панели кнопок"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setStyleSheet("""
            QFrame {
                background-color: #f9f9f9;
                border-top: 1px solid #ddd;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout()
        
        # Кнопка выхода
        self.exit_btn = QPushButton("🚪 Выйти")
        self.exit_btn.clicked.connect(self.reject)
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        layout.addWidget(self.exit_btn)
        
        # Растягивающийся спейсер
        layout.addStretch()
        
        # Кнопка быстрого создания
        self.quick_create_btn = QPushButton("⚡ Быстрый сервер")
        self.quick_create_btn.clicked.connect(self.create_quick_server)
        self.quick_create_btn.setToolTip("Создать сервер на текущем IP с настройками по умолчанию")
        self.quick_create_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        layout.addWidget(self.quick_create_btn)
        
        # Кнопка справки
        help_btn = QPushButton("❓ Справка")
        help_btn.clicked.connect(self.show_help)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #757575;
            }
        """)
        layout.addWidget(help_btn)
        
        panel.setLayout(layout)
        return panel
        
    def start_discovery(self):
        """Начало полного поиска серверов в сети"""
        # Получаем все сети
        networks = NetworkScanner.get_all_networks()
        if networks:
            self.start_discovery_with_networks(networks)
        else:
            self.start_discovery_worker(quick_mode=False)
        
    def start_quick_discovery(self):
        """Начало быстрого поиска серверов в сети"""
        # Получаем все сети
        networks = NetworkScanner.get_all_networks()
        if networks:
            self.start_discovery_with_networks(networks)
        else:
            self.start_discovery_worker(quick_mode=True)
        
    def start_discovery_worker(self, quick_mode: bool = False):
        """Запуск рабочего потока поиска"""
        # Переключаемся на экран загрузки
        self.stacked_widget.setCurrentWidget(self.loading_screen)
        self.loading_progress.setValue(0)
        self.scanned_ips = []
        self.ip_list_label.setText("Сканирование...")
        
        # Обновляем статус
        self.status_label.setText("Быстрый поиск серверов..." if quick_mode else "Подробный поиск серверов...")
        
        # Отключаем кнопки во время поиска
        self.refresh_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.network_select_btn.setEnabled(False)
        
        # Запускаем поток поиска
        self.discovery_worker = DiscoveryWorker(quick_mode=quick_mode)
        self.discovery_worker.servers_found.connect(self.on_servers_found)
        self.discovery_worker.discovery_progress.connect(self.update_discovery_progress)
        self.discovery_worker.discovery_error.connect(self.on_discovery_error)
        self.discovery_worker.finished.connect(self.on_discovery_finished)
        self.discovery_worker.start()
        
    def on_discovery_error(self, error_message: str):
        """Обработка ошибки поиска"""
        self.status_label.setText(f"Ошибка поиска: {error_message}")
        self.scan_info_panel.setText(f"❌ Ошибка: {error_message}")
        
    @pyqtSlot(list)
    def on_servers_found(self, servers: List[ServerInfo]):
        """Обработка найденных серверов"""
        self.found_servers = servers
        
        # Группируем серверы по сетям
        servers_by_network = {}
        for server in servers:
            network = getattr(server, 'discovery_network', 'unknown')
            if network not in servers_by_network:
                servers_by_network[network] = []
            servers_by_network[network].append(server)
        
        # Выводим статистику
        print(f"\n📊 Результаты сканирования:")
        print(f"   Всего найдено серверов: {len(servers)}")
        for network, net_servers in servers_by_network.items():
            online = sum(1 for s in net_servers if s.is_online)
            print(f"   • {network}: {len(net_servers)} серверов ({online} онлайн)")
        
        # Обновляем информацию в панели
        if servers:
            network_info = "\n".join([f"   • {network}: {len(net_servers)} серверов" 
                                     for network, net_servers in servers_by_network.items()])
            self.scan_info_panel.setText(f"✅ Найдено серверов: {len(servers)}\n{network_info}")
        else:
            self.scan_info_panel.setText("❌ Серверы не найдены")
        
        self.update_server_list()
        self.update_stats()
        
    def on_discovery_finished(self):
        """Обработка завершения поиска"""
        # Включаем кнопки
        self.refresh_btn.setEnabled(True)
        self.network_select_btn.setEnabled(True)
        
        # Обновляем статус
        online_count = sum(1 for s in self.found_servers if s.is_online)
        total_count = len(self.found_servers)
        
        if total_count == 0:
            self.status_label.setText("Серверы не найдены. Создайте новый или проверьте сеть.")
            self.stacked_widget.setCurrentWidget(self.error_screen)
        else:
            self.status_label.setText(f"Найдено серверов: {total_count} (онлайн: {online_count})")
            self.stacked_widget.setCurrentWidget(self.main_screen)
        
        # Очищаем worker
        self.discovery_worker = None
        
    def load_saved_servers(self):
        """Загрузка списка сохраненных серверов"""
        try:
            self.saved_servers = self.server_manager.get_server_list()
            self.update_saved_servers_list()
            self.update_stats()
        except Exception as e:
            print(f"Ошибка загрузки сохраненных серверов: {e}")
            
    def update_saved_servers_list(self):
        """Обновление списка сохраненных серверов"""
        self.saved_servers_list.clear()
        
        if not self.saved_servers:
            item = QListWidgetItem("📭 Нет сохраненных серверов")
            item.setForeground(QColor(150, 150, 150))
            self.saved_servers_list.addItem(item)
            self.saved_count_label.setText("Сохранено: 0")
            return
            
        for server in self.saved_servers:
            name = server.get('name', 'Без имени')
            ip = server.get('ip', '')
            port = server.get('port', 0)
            is_running = server.get('is_running', False)
            password_protected = server.get('password_protected', False)
            
            status_icon = "🟢" if is_running else "⚫"
            lock_icon = " 🔒" if password_protected else ""
            
            item_text = f"{status_icon} {name}\n    {ip}:{port}{lock_icon}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, server)
            
            # Устанавливаем цвет в зависимости от статуса
            if not is_running:
                item.setForeground(QColor(150, 150, 150))
                
            self.saved_servers_list.addItem(item)
            
        self.saved_count_label.setText(f"Сохранено: {len(self.saved_servers)}")
        
    def update_server_list(self):
        """Обновление списка найденных серверов"""
        self.servers_list.clear()
        
        if not self.found_servers:
            item = QListWidgetItem("📭 Серверы не найдены")
            item.setForeground(QColor(150, 150, 150))
            self.servers_list.addItem(item)
            self.found_count_label.setText("Найдено: 0")
            self.connect_btn.setEnabled(False)
            return
            
        # Сортируем серверы: сначала онлайн, потом по имени
        sorted_servers = sorted(
            self.found_servers,
            key=lambda x: (not x.is_online, x.name.lower())
        )
        
        for server in sorted_servers:
            status_icon = "🟢" if server.is_online else "⚫"
            users_text = f" 👥{server.users_count}" if server.users_count > 0 else ""
            lock_icon = " 🔒" if server.is_password_protected else ""
            
            item_text = f"{status_icon} {server.name}\n    {server.ip}:{server.port}{users_text}{lock_icon}"
            item = QListWidgetItem(item_text)
            
            # Устанавливаем цвет в зависимости от статуса
            if not server.is_online:
                item.setForeground(QColor(150, 150, 150))
                
            item.setData(Qt.UserRole, server)
            self.servers_list.addItem(item)
            
        self.found_count_label.setText(f"Найдено: {len(self.found_servers)}")
        
    def on_server_selected(self, item):
        """Обработка выбора сервера из списка"""
        server = item.data(Qt.UserRole)
        if isinstance(server, ServerInfo):
            self.selected_server = server
            self.show_server_info(server)
            
            # Разрешаем подключение только к онлайн серверам
            self.connect_btn.setEnabled(server.is_online)
            self.connect_btn.setText("🔗 Подключиться к серверу" if server.is_online else "⚡ Сервер недоступен")
            
            # Показываем кнопку запуска только для сохраненных серверов
            self.check_if_server_is_saved(server)
            
    def on_server_double_clicked(self, item):
        """Двойной клик по серверу - сразу подключаемся"""
        server = item.data(Qt.UserRole)
        if isinstance(server, ServerInfo) and server.is_online:
            self.connect_to_server(server)
            
    def on_saved_server_selected(self, item):
        """Обработка выбора сохраненного сервера"""
        server_data = item.data(Qt.UserRole)
        if isinstance(server_data, dict):
            self.selected_server = None  # Сбрасываем выбранный сервер
            self.show_saved_server_info(server_data)
            
            is_running = server_data.get('is_running', False)
            self.connect_btn.setEnabled(is_running)
            self.connect_btn.setText("🔗 Подключиться к серверу" if is_running else "⚡ Запустить сервер")
            
            self.start_server_btn.setEnabled(True)
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.start_saved_btn.setEnabled(True)
            
    def on_saved_server_double_clicked(self, item):
        """Двойной клик по сохраненному серверу"""
        server_data = item.data(Qt.UserRole)
        if isinstance(server_data, dict) and server_data.get('is_running', False):
            self.connect_to_saved_server(server_data)
            
    def check_if_server_is_saved(self, server: ServerInfo):
        """Проверка, сохранен ли сервер"""
        is_saved = False
        for saved_server in self.saved_servers:
            if (saved_server.get('ip') == server.ip and 
                saved_server.get('port') == server.port):
                is_saved = True
                break
                
        self.start_server_btn.setEnabled(is_saved)
        self.edit_btn.setEnabled(is_saved)
        self.delete_btn.setEnabled(is_saved)
        self.start_saved_btn.setEnabled(is_saved)
        
    def show_server_info(self, server: ServerInfo):
        """Отображение информации о сервере"""
        status_color = "#4CAF50" if server.is_online else "#F44336"
        status_text = "🟢 Онлайн и доступен" if server.is_online else "⚫ Оффлайн или недоступен"
        password_text = "🔒 Требуется пароль для запуска" if server.is_password_protected else "🔓 Без пароля"
        
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 10px;">
            <h2 style="color: #1976d2; margin-top: 0; border-bottom: 2px solid #e3f2fd; padding-bottom: 10px;">{server.name}</h2>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; width: 140px; color: #555; vertical-align: top;">📡 Адрес:</td>
                    <td style="padding: 8px 0;">
                        <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-family: monospace;">{server.ip}:{server.port}</code>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #555;">📊 Статус:</td>
                    <td style="padding: 8px 0;">
                        <span style="color: {status_color}; font-weight: bold; padding: 2px 8px; border-radius: 12px; background-color: {status_color}20;">{status_text}</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #555;">👥 Пользователи:</td>
                    <td style="padding: 8px 0;">
                        <span style="color: #2196F3; font-weight: bold;">{server.users_count}</span> / {server.max_users} онлайн
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #555;">🔐 Защита:</td>
                    <td style="padding: 8px 0;">{password_text}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #555;">📦 Версия:</td>
                    <td style="padding: 8px 0;">{server.version}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; vertical-align: top; color: #555;">📝 Описание:</td>
                    <td style="padding: 8px 0; color: #666; line-height: 1.5;">
                        {server.description or '<i style="color: #999;">Нет описания</i>'}
                    </td>
                </tr>
            </table>
        </div>
        """
        
        self.server_info_text.setHtml(html)
        
    def show_saved_server_info(self, server_data: dict):
        """Отображение информации о сохраненном сервере"""
        name = server_data.get('name', 'Без имени')
        ip = server_data.get('ip', '')
        port = server_data.get('port', 0)
        is_running = server_data.get('is_running', False)
        password_protected = server_data.get('password_protected', False)
        description = server_data.get('description', '')
        created_at = server_data.get('created_at', '')
        
        status_color = "#4CAF50" if is_running else "#FF9800"
        status_text = "🟢 Запущен и доступен" if is_running else "⚫ Остановлен"
        password_text = "🔒 Защищен паролем" if password_protected else "🔓 Без пароля"
        
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 10px;">
            <h2 style="color: {status_color}; margin-top: 0; border-bottom: 2px solid {status_color}30; padding-bottom: 10px;">{name}</h2>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; width: 140px; color: #555; vertical-align: top;">📡 Адрес:</td>
                    <td style="padding: 8px 0;">
                        <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-family: monospace;">{ip}:{port}</code>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #555;">📊 Статус:</td>
                    <td style="padding: 8px 0;">
                        <span style="color: {status_color}; font-weight: bold; padding: 2px 8px; border-radius: 12px; background-color: {status_color}20;">{status_text}</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #555;">🔐 Защита:</td>
                    <td style="padding: 8px 0;">{password_text}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; color: #555;">📅 Создан:</td>
                    <td style="padding: 8px 0; color: #666;">{created_at}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; vertical-align: top; color: #555;">📝 Описание:</td>
                    <td style="padding: 8px 0; color: #666; line-height: 1.5;">
                        {description or '<i style="color: #999;">Нет описания</i>'}
                    </td>
                </tr>
            </table>
        </div>
        """
        
        self.server_info_text.setHtml(html)
        
    def on_connect_clicked(self):
        """Обработка нажатия кнопки подключения"""
        if self.tab_widget.currentIndex() == 0:  # Вкладка "В сети"
            current_item = self.servers_list.currentItem()
            if not current_item:
                QMessageBox.warning(self, "Ошибка", "Выберите сервер из списка")
                return
                
            server = current_item.data(Qt.UserRole)
            if isinstance(server, ServerInfo):
                self.connect_to_server(server)
                
        else:  # Вкладка "Сохраненные"
            current_item = self.saved_servers_list.currentItem()
            if not current_item:
                QMessageBox.warning(self, "Ошибка", "Выберите сервер из списка")
                return
                
            server_data = current_item.data(Qt.UserRole)
            if isinstance(server_data, dict):
                self.connect_to_saved_server(server_data)
                
    def connect_to_server(self, server: ServerInfo):
        """Подключение к выбранному серверу"""
        if not server.is_online:
            reply = QMessageBox.question(
                self, "Сервер недоступен",
                f"Сервер {server.name} в данный момент недоступен.\n\n"
                "Хотите попробовать сохранить его и запустить?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.save_and_start_server(server)
            return
            
        # Проверяем пароль если требуется
        password = None
        if server.is_password_protected:
            password, ok = QInputDialog.getText(
                self, "🔐 Ввод пароля",
                f"Для подключения к серверу '{server.name}' требуется пароль:",
                QLineEdit.Password
            )
            if not ok or not password:
                return
        
        # Формируем данные сервера
        server_data = {
            'name': server.name,
            'ip': server.ip,
            'port': server.port,
            'description': server.description,
            'is_password_protected': server.is_password_protected,
            'password': password  # Сохраняем пароль для подключения
        }
        
        # Сохраняем сервер в список сохраненных если его там нет
        self.save_server_if_new(server)
        
        # Сохраняем в настройках как последний сервер
        self.auth_manager.save_last_server(server_data)
        
        # Отправляем сигнал с выбранным сервером
        self.server_selected.emit(server_data)
        self.accept()
        
    def connect_to_saved_server(self, server_data: dict):
        """Подключение к сохраненному серверу"""
        ip = server_data.get('ip', '')
        port = server_data.get('port', 0)
        
        # Проверяем доступность сервера
        if not self.check_server_connection(ip, port):
            reply = QMessageBox.question(
                self, "Сервер недоступен",
                f"Сервер {server_data.get('name')} не отвечает.\n\n"
                "Хотите попробовать запустить его?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.on_start_server_clicked()
            return
            
        # Проверяем пароль если требуется
        password = None
        if server_data.get('password_protected'):
            password, ok = QInputDialog.getText(
                self, "🔐 Ввод пароля",
                f"Для подключения к серверу '{server_data.get('name')}' требуется пароль:",
                QLineEdit.Password
            )
            if not ok or not password:
                return
                
            # Проверяем пароль через менеджер
            server_name = server_data.get('name', '')
            if not self.server_manager.check_server_password(server_name, password):
                QMessageBox.warning(self, "Ошибка", "❌ Неверный пароль")
                return
        
        # Сохраняем в настройках как последний сервер
        server_data['password'] = password
        self.auth_manager.save_last_server(server_data)
        
        # Отправляем сигнал
        self.server_selected.emit(server_data)
        self.accept()
        
    def save_server_if_new(self, server: ServerInfo):
        """Сохранение сервера если он новый"""
        ip = server.ip
        port = server.port
        
        # Проверяем, есть ли уже такой сервер
        is_new = True
        server_name = None
        for saved_server in self.saved_servers:
            if (saved_server.get('ip') == ip and 
                saved_server.get('port') == port):
                is_new = False
                server_name = saved_server.get('name')
                break
                
        if is_new:
            # Создаем конфигурацию сервера
            success, message = self.server_manager.create_server(
                name=server.name,
                ip=ip,
                port=port,
                description=server.description,
                password=None,  # Пароль не сохраняем при импорте
                auto_start=False
            )
            
            if success:
                # Обновляем список сохраненных серверов
                self.load_saved_servers()
                QMessageBox.information(
                    self, "✅ Сервер сохранен",
                    f"Сервер '{server.name}' добавлен в список сохраненных.\n\n"
                    f"Теперь вы можете запускать его с этого компьютера."
                )
            else:
                QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить сервер: {message}")
        else:
            # Сервер уже сохранен
            print(f"Сервер '{server_name}' уже сохранен")
            
    def save_and_start_server(self, server: ServerInfo):
        """Сохранение и запуск сервера"""
        # Сначала сохраняем
        self.save_server_if_new(server)
        
        # Затем пытаемся запустить
        server_name = server.name
        self.on_start_server_clicked(server_name=server_name)
                
    def create_server(self):
        """Создание нового сервера"""
        try:
            from client.ui.server_create_dialog import ServerCreateDialog
            dialog = ServerCreateDialog(self)
        except ImportError:
            QMessageBox.warning(self, "Ошибка", "Модуль создания сервера не найден")
            return
        
        def on_server_created(server_config):
            # Запускаем создание сервера
            success, message = self.server_manager.create_server(
                name=server_config['name'],
                ip=server_config['ip'],
                port=server_config['port'],
                description=server_config.get('description', ''),
                password=server_config.get('password'),
                broadcast_port=server_config.get('broadcast_port', 37020),
                max_users=server_config.get('max_users', 50),
                auto_start=server_config.get('auto_start', False)
            )
            
            if success:
                # Предлагаем запустить сервер
                reply = QMessageBox.question(
                    self, "✅ Сервер создан",
                    f"{message}\n\nЗапустить сервер сейчас?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # Запускаем сервер
                    server_name = server_config['name']
                    password = server_config.get('password')
                    
                    success, message = self.server_manager.start_server(server_name, password)
                    if success:
                        QMessageBox.information(self, "✅ Успех", message)
                        # Обновляем списки
                        self.load_saved_servers()
                        self.start_quick_discovery()
                        
                        # Автоматически подключаемся
                        server_data = {
                            'name': server_config['name'],
                            'ip': server_config['ip'],
                            'port': server_config['port'],
                            'description': server_config.get('description', ''),
                            'is_password_protected': bool(server_config.get('password')),
                            'password': password
                        }
                        
                        # Сохраняем в настройках
                        self.auth_manager.save_last_server(server_data)
                        
                        # Отправляем сигнал
                        self.server_selected.emit(server_data)
                        self.accept()
                    else:
                        QMessageBox.warning(self, "⚠️ Ошибка", message)
                else:
                    QMessageBox.information(self, "✅ Сервер создан", message)
                    # Обновляем список
                    self.load_saved_servers()
                    
            else:
                QMessageBox.critical(self, "❌ Ошибка", message)
        
        dialog.server_created.connect(on_server_created)
        dialog.exec_()
                
    def create_quick_server(self):
        """Создание быстрого сервера с настройками по умолчанию"""
        try:
            # Получаем текущий IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Ищем свободный порт начиная с 8000
            port = 8000
            while port < 8100:
                if self.check_port_available(local_ip, port):
                    break
                port += 1
            
            if port >= 8100:
                QMessageBox.warning(self, "❌ Ошибка", "Не удалось найти свободный порт (8000-8099)")
                return
            
            # Запрашиваем имя сервера
            name, ok = QInputDialog.getText(
                self, "⚡ Быстрый сервер",
                "Введите имя сервера:",
                text=f"Мой сервер ({local_ip})"
            )
            
            if not ok or not name:
                return
            
            # Запрашиваем пароль
            password, ok = QInputDialog.getText(
                self, "🔐 Защита паролем",
                "Пароль для запуска сервера (оставьте пустым для отсутствия защиты):",
                QLineEdit.Password
            )
            
            if not ok:
                return
            
            # Создаем сервер
            success, message = self.server_manager.create_server(
                name=name,
                ip=local_ip,
                port=port,
                description="Быстро созданный сервер",
                password=password if password else None,
                auto_start=False
            )
            
            if success:
                # Запускаем сервер
                success, message = self.server_manager.start_server(name, password)
                if success:
                    QMessageBox.information(self, "✅ Успех", f"Сервер запущен!\n\n{message}")
                    
                    # Обновляем списки
                    self.load_saved_servers()
                    self.start_quick_discovery()
                    
                    # Автоматически подключаемся
                    server_data = {
                        'name': name,
                        'ip': local_ip,
                        'port': port,
                        'description': "Быстро созданный сервер",
                        'is_password_protected': bool(password),
                        'password': password
                    }
                    
                    # Сохраняем в настройках
                    self.auth_manager.save_last_server(server_data)
                    
                    # Отправляем сигнал
                    self.server_selected.emit(server_data)
                    self.accept()
                else:
                    QMessageBox.warning(self, "⚠️ Ошибка", f"Сервер создан, но не запущен:\n\n{message}")
            else:
                QMessageBox.critical(self, "❌ Ошибка", message)
                
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Не удалось создать быстрый сервер:\n\n{str(e)}")
            
    def on_start_server_clicked(self, server_name: str = None):
        """Запуск выбранного сервера"""
        if not server_name:
            current_item = self.saved_servers_list.currentItem()
            if not current_item:
                QMessageBox.warning(self, "Ошибка", "Выберите сервер из списка сохраненных")
                return
                
            server_data = current_item.data(Qt.UserRole)
            if not isinstance(server_data, dict):
                return
                
            server_name = server_data.get('name', '')
        
        # Проверяем, запущен ли уже сервер
        if self.server_manager.check_server_connection(server_name):
            QMessageBox.information(self, "✅ Сервер уже запущен", 
                                  f"Сервер '{server_name}' уже запущен и доступен.")
            return
        
        # Запрашиваем пароль если требуется
        password = None
        server_info = self.server_manager.get_server_status(server_name)
        if server_info.get('password_protected'):
            password, ok = QInputDialog.getText(
                self, "🔐 Ввод пароля",
                f"Для запуска сервера '{server_name}' требуется пароль:",
                QLineEdit.Password
            )
            if not ok:
                return
        
        # Запускаем сервер
        success, message = self.server_manager.start_server(server_name, password)
        
        if success:
            QMessageBox.information(self, "✅ Успех", message)
            # Обновляем списки
            self.load_saved_servers()
            self.start_quick_discovery()
        else:
            QMessageBox.warning(self, "⚠️ Ошибка", message)
            
    def on_edit_clicked(self):
        """Редактирование выбранного сервера"""
        current_item = self.saved_servers_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Ошибка", "Выберите сервер для редактирования")
            return
            
        server_data = current_item.data(Qt.UserRole)
        if not isinstance(server_data, dict):
            return
            
        QMessageBox.information(self, "✏️ Редактирование", 
                              "Функция редактирования в разработке.\n\n"
                              f"Сервер: {server_data.get('name')}\n"
                              f"Для изменения настроек удалите и создайте сервер заново.")
        
    def on_delete_clicked(self):
        """Удаление выбранного сервера"""
        current_item = self.saved_servers_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Ошибка", "Выберите сервер для удаления")
            return
            
        server_data = current_item.data(Qt.UserRole)
        if not isinstance(server_data, dict):
            return
            
        server_name = server_data.get('name', '')
        
        reply = QMessageBox.question(
            self, "🗑️ Подтверждение удаления",
            f"Вы уверены, что хотите удалить сервер '{server_name}'?\n\n"
            "Файл конфигурации также будет удален.\n"
            "Это действие нельзя отменить.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = self.server_manager.delete_server(
                server_name, 
                delete_files=True
            )
            
            if success:
                QMessageBox.information(self, "✅ Успех", message)
                # Обновляем списки
                self.load_saved_servers()
                self.start_quick_discovery()
            else:
                QMessageBox.warning(self, "⚠️ Ошибка", message)
                
    def check_server_connection(self, ip: str, port: int) -> bool:
        """Проверка подключения к серверу"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
            
    def check_port_available(self, ip: str, port: int) -> bool:
        """Проверка доступности порта"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result != 0  # 0 = порт занят
        except:
            return False
            
    def update_stats(self):
        """Обновление статистики"""
        online_count = sum(1 for s in self.found_servers if s.is_online)
        protected_count = sum(1 for s in self.found_servers if s.is_password_protected)
        
        self.stats_found_label.setText(str(len(self.found_servers)))
        self.stats_online_label.setText(str(online_count))
        self.stats_saved_label.setText(str(len(self.saved_servers)))
        self.stats_protected_label.setText(str(protected_count))
        
    def update_server_status(self):
        """Обновление статуса серверов"""
        pass  # Можно добавить периодическое обновление
        
    def show_help(self):
        """Показ справки"""
        help_text = """
        <h2>📚 Справка по выбору сервера</h2>
        
        <h3>🌐 Вкладка "В сети":</h3>
        <ul>
            <li><b>🟢</b> - сервер онлайн и доступен для подключения</li>
            <li><b>⚫</b> - сервер оффлайн или недоступен</li>
            <li><b>👥</b> - количество пользователей на сервере</li>
            <li><b>🔒</b> - для запуска сервера требуется пароль</li>
        </ul>
        
        <h3>💾 Вкладка "Сохраненные":</h3>
        <ul>
            <li>Серверы, которые вы ранее сохранили</li>
            <li>Можно запускать и останавливать</li>
            <li>Можно удалить из списка</li>
        </ul>
        
        <h3>🚀 Действия с сервером:</h3>
        <ul>
            <li><b>Подключиться</b> - подключиться к выбранному серверу</li>
            <li><b>Создать новый сервер</b> - создать и настроить новый сервер</li>
            <li><b>Быстрый сервер</b> - быстро создать сервер с настройками по умолчанию</li>
            <li><b>Запустить сервер</b> - запустить сохраненный сервер</li>
            <li><b>Удалить сервер</b> - удалить сервер из списка сохраненных</li>
        </ul>
        
        <h3>🌐 Выбор сети:</h3>
        <ul>
            <li>Можно выбрать конкретные сети для сканирования</li>
            <li>Отображаются все доступные сетевые интерфейсы</li>
            <li>Показывается прогресс сканирования и найденные IP</li>
        </ul>
        
        <h3>💡 Важная информация:</h3>
        <ul>
            <li>Для запуска защищенных серверов потребуется пароль</li>
            <li>Любой пользователь может запустить сервер, зная правильный пароль</li>
            <li>Серверы обнаруживаются в локальной сети автоматически</li>
            <li>Для работы в разных сетях может потребоваться настройка брандмауэра</li>
        </ul>
        """
        
        QMessageBox.information(self, "📚 Справка", help_text)
        
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Останавливаем поиск если запущен
        if self.discovery_worker and self.discovery_worker.isRunning():
            self.discovery_worker.stop()
            
        # Останавливаем таймеры
        self.update_timer.stop()
        
        super().closeEvent(event)


# Тестирование диалога
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль
    app.setStyle("Fusion")
    
    # Создаем и показываем диалог
    dialog = ServerBrowserDialog()
    
    # Обработчик выбора сервера
    def on_server_selected(server_data):
        print(f"\n✅ Выбран сервер:")
        print(f"   Имя: {server_data.get('name')}")
        print(f"   Адрес: {server_data.get('ip')}:{server_data.get('port')}")
        print(f"   Защита паролем: {server_data.get('is_password_protected')}")
        dialog.close()
    
    dialog.server_selected.connect(on_server_selected)
    
    # Запускаем диалог
    if dialog.exec_() == QDialog.Accepted:
        print("\n✅ Диалог закрыт с выбором сервера")
    else:
        print("\n🚪 Диалог закрыт без выбора сервера")
    
    sys.exit(0)