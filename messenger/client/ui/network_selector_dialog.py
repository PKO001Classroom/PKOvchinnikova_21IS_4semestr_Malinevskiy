"""
Диалог выбора сетевого интерфейса для сканирования.
Альтернативная версия без использования netifaces.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QListWidget, QListWidgetItem, QPushButton,
                             QMessageBox, QFrame, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import socket
import ipaddress
import subprocess
import re


class NetworkSelectorDialog(QDialog):
    """
    Диалог выбора сетевого интерфейса для broadcast сканирования.
    """
    
    networks_selected = pyqtSignal(list)  # Сигнал с выбранными сетями
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.interfaces = []
        self.init_ui()
        self.load_network_interfaces()
        
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle("🌐 Выбор сети для сканирования")
        self.setGeometry(400, 300, 650, 550)
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Заголовок
        title_label = QLabel("Выберите сетевые интерфейсы для сканирования")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #1976d2; padding: 10px 0;")
        layout.addWidget(title_label)
        
        # Пояснение
        info_label = QLabel(
            "Будут просканированы все выбранные сети через UDP broadcast.\n"
            "Чем больше сетей выбрано, тем дольше будет сканирование."
        )
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #ddd; margin: 10px 0;")
        layout.addWidget(separator)
        
        # Список интерфейсов
        self.interface_list = QListWidget()
        self.interface_list.setSelectionMode(QListWidget.MultiSelection)
        self.interface_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: white;
                font-size: 13px;
                padding: 5px;
                min-height: 250px;
            }
            QListWidget::item {
                padding: 12px 10px;
                border-bottom: 1px solid #f0f0f0;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        layout.addWidget(self.interface_list)
        
        # Кнопки выбора
        select_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("✅ Выбрать все")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        select_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("❌ Очистить все")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #757575;
            }
        """)
        select_layout.addWidget(self.deselect_all_btn)
        
        layout.addLayout(select_layout)
        
        # Статистика
        self.stats_label = QLabel("Найдено интерфейсов: 0")
        self.stats_label.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        layout.addWidget(self.stats_label)
        
        # Разделитель
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setStyleSheet("color: #ddd; margin: 10px 0;")
        layout.addWidget(separator2)
        
        # Кнопки действий
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("❌ Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("""
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
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.scan_btn = QPushButton("🔍 Начать сканирование")
        self.scan_btn.clicked.connect(self.accept)
        self.scan_btn.setEnabled(False)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 30px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.scan_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def load_network_interfaces(self):
        """Загрузка доступных сетевых интерфейсов без netifaces"""
        try:
            # Получаем имя хоста и все IP адреса
            hostname = socket.gethostname()
            all_ips = socket.gethostbyname_ex(hostname)[2]
            
            # Добавляем локальный IP если он не в списке
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                if local_ip not in all_ips:
                    all_ips.append(local_ip)
            except:
                pass
            
            # Для каждого IP определяем сеть
            for ip in all_ips:
                if ip.startswith('127.'):  # Пропускаем loopback
                    continue
                
                # Определяем broadcast адрес (предполагаем /24 сеть)
                parts = ip.split('.')
                network = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                cidr = f"{ip}/24"
                
                interface_info = {
                    'name': f"Сеть {parts[0]}.{parts[1]}.{parts[2]}.0/24",
                    'ip': ip,
                    'netmask': '255.255.255.0',
                    'network': network,
                    'broadcast': broadcast,
                    'cidr': cidr
                }
                self.interfaces.append(interface_info)
            
            # Пробуем получить больше информации через ipconfig (Windows)
            if not self.interfaces:
                self._load_from_ipconfig()
            
            # Если все еще нет интерфейсов, добавляем broadcast на все интерфейсы
            if not self.interfaces:
                interface_info = {
                    'name': 'Все сети (широковещательный)',
                    'ip': '0.0.0.0',
                    'netmask': '255.255.255.0',
                    'network': '0.0.0.0',
                    'broadcast': '255.255.255.255',
                    'cidr': '0.0.0.0/0'
                }
                self.interfaces.append(interface_info)
            
            # Заполняем список
            for iface in self.interfaces:
                item_text = (f"{iface['name']}\n"
                           f"    IP: {iface['ip']}, Broadcast: {iface['broadcast']}")
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, iface)
                self.interface_list.addItem(item)
            
            # По умолчанию выбираем все
            for i in range(self.interface_list.count()):
                self.interface_list.item(i).setSelected(True)
            
            self.stats_label.setText(f"Найдено интерфейсов: {len(self.interfaces)}")
            self.scan_btn.setEnabled(len(self.interfaces) > 0)
            
        except Exception as e:
            print(f"Ошибка загрузки интерфейсов: {e}")
            # Добавляем заглушку
            interface_info = {
                'name': 'Локальная сеть',
                'ip': '192.168.1.100',
                'netmask': '255.255.255.0',
                'network': '192.168.1.0',
                'broadcast': '192.168.1.255',
                'cidr': '192.168.1.0/24'
            }
            self.interfaces.append(interface_info)
            
            item_text = (f"{interface_info['name']}\n"
                       f"    IP: {interface_info['ip']}, Broadcast: {interface_info['broadcast']}")
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, interface_info)
            self.interface_list.addItem(item)
            item.setSelected(True)
            
            self.stats_label.setText(f"Найдено интерфейсов: 1")
            self.scan_btn.setEnabled(True)
    
    def _load_from_ipconfig(self):
        """Загрузка интерфейсов через ipconfig (Windows)"""
        try:
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='cp866')
            lines = result.stdout.split('\n')
            
            current_iface = None
            ip_pattern = re.compile(r'IPv4-адрес.*:\s*(\d+\.\d+\.\d+\.\d+)')
            mask_pattern = re.compile(r'Маска подсети.*:\s*(\d+\.\d+\.\d+\.\d+)')
            
            for line in lines:
                if 'адаптер' in line.lower():
                    current_iface = line.strip()
                elif current_iface:
                    ip_match = ip_pattern.search(line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if not ip.startswith('127.'):
                            parts = ip.split('.')
                            interface_info = {
                                'name': current_iface,
                                'ip': ip,
                                'netmask': '255.255.255.0',
                                'network': f"{parts[0]}.{parts[1]}.{parts[2]}.0",
                                'broadcast': f"{parts[0]}.{parts[1]}.{parts[2]}.255",
                                'cidr': f"{ip}/24"
                            }
                            self.interfaces.append(interface_info)
        except Exception as e:
            print(f"Ошибка при выполнении ipconfig: {e}")
    
    def select_all(self):
        """Выбрать все интерфейсы"""
        for i in range(self.interface_list.count()):
            self.interface_list.item(i).setSelected(True)
        self.scan_btn.setEnabled(self.interface_list.count() > 0)
    
    def deselect_all(self):
        """Снять выбор со всех интерфейсов"""
        for i in range(self.interface_list.count()):
            self.interface_list.item(i).setSelected(False)
        self.scan_btn.setEnabled(False)
    
    def get_selected_networks(self) -> list:
        """Получение списка выбранных сетей"""
        selected = []
        for item in self.interface_list.selectedItems():
            iface = item.data(Qt.UserRole)
            selected.append(iface)
        return selected


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = NetworkSelectorDialog()
    
    def on_networks_selected(networks):
        print(f"\n✅ Выбрано сетей: {len(networks)}")
        for net in networks:
            print(f"   {net['name']}: {net['ip']} -> {net['broadcast']}")
    
    dialog.networks_selected.connect(on_networks_selected)
    
    if dialog.exec_() == QDialog.Accepted:
        networks = dialog.get_selected_networks()
        dialog.networks_selected.emit(networks)
    
    sys.exit(0)