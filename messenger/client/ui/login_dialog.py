"""
Диалог авторизации и выбора сервера.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
                             QLineEdit, QPushButton, QMessageBox, QInputDialog,
                             QCheckBox, QFrame, QProgressBar)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import requests
import socket

# Импорт модулей из новой структуры - добавляем client.
try:
    from client.config import APP_NAME, APP_VERSION, SERVER_URL
    from client.ui.server_browser_dialog import ServerBrowserDialog
    from client.auth_manager import get_auth_manager
    from client.network.server_discovery import quick_discover_servers
    from client.server_manager import get_server_manager
except ImportError as e:
    print(f"Ошибка импорта в login_dialog.py: {e}")


class LoginDialog(QDialog):
    server_selected = pyqtSignal(dict)  # Сигнал с выбранным сервером
    
    def __init__(self):
        super().__init__()
        self.auth_token = None
        self.current_user = None
        self.auth_manager = get_auth_manager()
        self.server_manager = get_server_manager()
        self.server_url = None
        self.init_ui()
        
        # Проверяем сохраненную сессию
        self.check_saved_session()
        
    def init_ui(self):
        self.setWindowTitle(f"🔐 {APP_NAME} - Авторизация")
        self.setGeometry(400, 300, 500, 500)
        self.setMinimumSize(450, 450)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)
        
        # Заголовок
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel(APP_NAME)
        title_label.setAlignment(Qt.AlignCenter)
        title_font = self.font()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #1976d2; padding: 10px 0;")
        header_layout.addWidget(title_label)
        
        subtitle_label = QLabel(f"Версия {APP_VERSION}")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #666; font-style: italic; padding-bottom: 10px;")
        header_layout.addWidget(subtitle_label)
        
        main_layout.addWidget(header_widget)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #eee; margin: 10px 0;")
        main_layout.addWidget(separator)
        
        # Форма авторизации
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(15)
        
        # Username
        username_layout = QHBoxLayout()
        username_label = QLabel("👤 Имя пользователя:")
        username_label.setFixedWidth(150)
        username_label.setStyleSheet("font-weight: bold;")
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Введите имя пользователя")
        self.username_edit.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #1976d2;
            }
        """)
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_edit)
        form_layout.addLayout(username_layout)
        
        # Password
        password_layout = QHBoxLayout()
        password_label = QLabel("🔒 Пароль:")
        password_label.setFixedWidth(150)
        password_label.setStyleSheet("font-weight: bold;")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Введите пароль")
        self.password_edit.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #1976d2;
            }
        """)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_edit)
        form_layout.addLayout(password_layout)
        
        # Запомнить меня
        self.remember_checkbox = QCheckBox("💾 Запомнить меня")
        self.remember_checkbox.setChecked(True)
        self.remember_checkbox.setStyleSheet("padding: 10px 0;")
        form_layout.addWidget(self.remember_checkbox, alignment=Qt.AlignCenter)
        
        main_layout.addWidget(form_widget)
        
        # Кнопки авторизации
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setSpacing(12)
        
        self.login_btn = QPushButton("🚪 Войти")
        self.login_btn.clicked.connect(self.login)
        self.login_btn.setMinimumHeight(50)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 16px;
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
        buttons_layout.addWidget(self.login_btn)
        
        self.register_btn = QPushButton("📝 Зарегистрироваться")
        self.register_btn.clicked.connect(self.register)
        self.register_btn.setMinimumHeight(45)
        self.register_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        buttons_layout.addWidget(self.register_btn)
        
        # Кнопка быстрого входа
        self.quick_start_btn = QPushButton("⚡ Быстрый старт")
        self.quick_start_btn.clicked.connect(self.quick_start)
        self.quick_start_btn.setMinimumHeight(45)
        self.quick_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        buttons_layout.addWidget(self.quick_start_btn)
        
        main_layout.addWidget(buttons_widget)
        
        # Разделитель
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setStyleSheet("color: #eee; margin: 15px 0;")
        main_layout.addWidget(separator2)
        
        # Статус
        self.status_label = QLabel("Готов к работе")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 10px;
                background-color: #f9f9f9;
                border-radius: 6px;
                border: 1px solid #eee;
            }
        """)
        main_layout.addWidget(self.status_label)
        
        self.setLayout(main_layout)
        
        # Подключаем Enter к кнопке входа
        self.username_edit.returnPressed.connect(self.login)
        self.password_edit.returnPressed.connect(self.login)
        
    def check_saved_session(self):
        """Проверка сохраненной сессии"""
        if self.auth_manager.is_session_valid():
            user_data = self.auth_manager.get_user_data()
            if user_data:
                self.username_edit.setText(user_data.get('username', ''))
                self.status_label.setText("💾 Обнаружена сохраненная сессия")
                
                # Автоматический вход?
                auto_login = self.auth_manager.get_setting('auto_login', False)
                if auto_login:
                    QTimer.singleShot(500, self.auto_login)
        else:
            # Проверяем последний сервер
            last_server = self.auth_manager.get_last_server()
            if last_server:
                self.status_label.setText(f"📡 Последний сервер: {last_server.get('name')}")
    
    def auto_login(self):
        """Автоматический вход по сохраненной сессии"""
        if not self.auth_manager.is_session_valid():
            return
            
        user_data = self.auth_manager.get_user_data()
        self.username_edit.setText(user_data.get('username', ''))
        
        # Проверяем сервер
        last_server = self.auth_manager.get_last_server()
        if last_server:
            # Пытаемся подключиться к последнему серверу
            self.status_label.setText("📡 Подключение к последнему серверу...")
            self.connect_to_server(last_server)
        else:
            # Показываем выбор сервера
            self.status_label.setText("🔍 Поиск доступных серверов...")
            self.show_server_browser()
    
    def login(self):
        """Авторизация пользователя"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        
        if not username:
            QMessageBox.warning(self, "❌ Ошибка", "Введите имя пользователя")
            return
        
        if not password:
            QMessageBox.warning(self, "❌ Ошибка", "Введите пароль")
            return
        
        # Показываем выбор сервера
        self.status_label.setText("🔍 Поиск доступных серверов...")
        self.show_server_browser(username, password)
        
    def register(self):
        """Регистрация нового пользователя"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        
        if not username:
            QMessageBox.warning(self, "❌ Ошибка", "Введите имя пользователя")
            return
        
        if not password:
            QMessageBox.warning(self, "❌ Ошибка", "Введите пароль")
            return
        
        if len(password) < 4:
            QMessageBox.warning(self, "❌ Ошибка", "Пароль должен быть не менее 4 символов")
            return
        
        # Показываем выбор сервера для регистрации
        self.status_label.setText("🔍 Выбор сервера для регистрации...")
        self.show_server_browser(username, password, is_registration=True)
    
    def quick_start(self):
        """Быстрый старт - создание локального сервера"""
        self.status_label.setText("⚡ Быстрый старт...")
        
        try:
            # Используем менеджер серверов для создания быстрого сервера
            success, message, server_data = self.server_manager.get_quick_start_server()
            
            if not success:
                QMessageBox.warning(self, "❌ Ошибка", message)
                self.status_label.setText("❌ Ошибка быстрого старта")
                return
            
            # Запрашиваем данные пользователя
            username, ok = QInputDialog.getText(
                self, "⚡ Быстрый старт",
                "Введите имя пользователя для быстрого старта:",
                text="Гость"
            )
            
            if not ok or not username:
                return
            
            # Регистрируем пользователя на сервере
            self.register_on_server(
                server_data['ip'], 
                server_data['port'], 
                username, 
                "1234",  # Простой пароль для быстрого старта
                server_data['name']
            )
                
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Ошибка быстрого старта: {str(e)}")
            self.status_label.setText("❌ Ошибка быстрого старта")
    
    def register_on_server(self, ip: str, port: int, username: str, password: str, server_name: str):
        """Регистрация на сервере"""
        try:
            server_url = f"http://{ip}:{port}"
            response = requests.post(
                f"{server_url}/auth/register",
                json={"username": username, "password": password},
                timeout=10
            )
            
            if response.status_code == 200:
                # Авторизуемся
                response = requests.post(
                    f"{server_url}/auth/login",
                    json={"username": username, "password": password},
                    timeout=10
                )
                
                if response.status_code == 200:
                    auth_token = response.json()["access_token"]
                    
                    # Получаем данные пользователя
                    headers = {"Authorization": f"Bearer {auth_token}"}
                    response = requests.get(
                        f"{server_url}/users/me",
                        headers=headers,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        user_data = response.json()
                        
                        # Создаем сессию
                        self.auth_manager.create_session(
                            auth_token, 
                            user_data, 
                            self.remember_checkbox.isChecked()
                        )
                        
                        # Сохраняем сервер
                        server_info = {
                            'name': server_name,
                            'ip': ip,
                            'port': port,
                            'description': "Автоматически созданный сервер",
                            'is_password_protected': False
                        }
                        
                        self.auth_manager.save_last_server(server_info)
                        
                        # Отправляем сигнал
                        self.server_selected.emit({
                            **server_info,
                            'auth_token': auth_token,
                            'user_data': user_data
                        })
                        
                        self.accept()
                        return
                    
            QMessageBox.warning(self, "❌ Ошибка", "Не удалось зарегистрироваться на сервере")
            self.status_label.setText("❌ Ошибка регистрации")
            
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Ошибка подключения: {str(e)}")
            self.status_label.setText("❌ Ошибка подключения")
    
    def show_server_browser(self, username: str = "", password: str = "", is_registration: bool = False):
        """Показать диалог выбора сервера"""
        dialog = ServerBrowserDialog(self)
        
        def on_server_selected(server_data):
            # Сохраняем данные сервера
            self.server_url = f"http://{server_data['ip']}:{server_data['port']}"
            
            if is_registration:
                # Регистрация на выбранном сервере
                self.register_on_selected_server(server_data, username, password)
            else:
                # Авторизация на выбранном сервере
                self.login_on_selected_server(server_data, username, password)
        
        dialog.server_selected.connect(on_server_selected)
        dialog.exec_()
    
    def register_on_selected_server(self, server_data: dict, username: str, password: str):
        """Регистрация на выбранном сервере"""
        self.status_label.setText(f"📝 Регистрация на сервере {server_data['name']}...")
        
        try:
            response = requests.post(
                f"{self.server_url}/auth/register",
                json={"username": username, "password": password},
                timeout=10
            )
            
            if response.status_code == 200:
                QMessageBox.information(self, "✅ Успех", "Регистрация успешна!")
                # Авторизуемся после регистрации
                self.login_on_selected_server(server_data, username, password)
            else:
                error_detail = "Неизвестная ошибка"
                try:
                    error_detail = response.json().get("detail", error_detail)
                except:
                    error_detail = response.text[:100]
                
                QMessageBox.warning(self, "❌ Ошибка", f"Ошибка регистрации: {error_detail}")
                self.status_label.setText("❌ Ошибка регистрации")
                
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "❌ Ошибка", f"Не удалось подключиться к серверу {server_data['name']}")
            self.status_label.setText("❌ Ошибка подключения")
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Ошибка: {str(e)}")
            self.status_label.setText("❌ Ошибка")
    
    def login_on_selected_server(self, server_data: dict, username: str, password: str):
        """Авторизация на выбранном сервере"""
        self.status_label.setText(f"🔐 Авторизация на сервере {server_data['name']}...")
        
        try:
            response = requests.post(
                f"{self.server_url}/auth/login",
                json={"username": username, "password": password},
                timeout=10
            )
            
            print(f"🔧 Login status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    self.auth_token = response.json()["access_token"]
                    self.current_user = self.get_current_user()
                    
                    if self.current_user:
                        # Создаем сессию
                        self.auth_manager.create_session(
                            self.auth_token, 
                            self.current_user, 
                            self.remember_checkbox.isChecked()
                        )
                        
                        # Сохраняем сервер
                        server_data['auth_token'] = self.auth_token
                        server_data['user_data'] = self.current_user
                        self.auth_manager.save_last_server(server_data)
                        
                        # Отправляем сигнал
                        self.server_selected.emit(server_data)
                        self.accept()
                    else:
                        QMessageBox.warning(self, "❌ Ошибка", "Не удалось получить данные пользователя")
                        self.status_label.setText("❌ Ошибка получения данных")
                        
                except Exception as e:
                    QMessageBox.warning(self, "❌ Ошибка", f"Некорректный ответ сервера: {str(e)}")
                    self.status_label.setText("❌ Некорректный ответ")
                    
            else:
                error_detail = "Неверные учетные данные"
                try:
                    error_detail = response.json().get("detail", error_detail)
                except:
                    error_detail = response.text[:100]
                
                QMessageBox.warning(self, "❌ Ошибка", error_detail)
                self.status_label.setText("❌ Ошибка авторизации")
                
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "❌ Ошибка", f"Не удалось подключиться к серверу {server_data['name']}")
            self.status_label.setText("❌ Ошибка подключения")
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "❌ Ошибка", "Превышено время ожидания")
            self.status_label.setText("⏱️ Таймаут подключения")
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", f"Неожиданная ошибка: {str(e)}")
            self.status_label.setText("❌ Неожиданная ошибка")
    
    def get_current_user(self):
        """Получение данных текущего пользователя"""
        if not self.auth_token or not self.server_url:
            return None
            
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(f"{self.server_url}/users/me", headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get user info: {response.status_code}")
                return None
        except:
            return None
    
    def connect_to_server(self, server_data: dict):
        """Прямое подключение к серверу (для auto-login)"""
        self.server_url = f"http://{server_data['ip']}:{server_data['port']}"
        
        # Проверяем доступность сервера
        try:
            response = requests.get(f"{self.server_url}/", timeout=5)
            if response.status_code == 200:
                # Сервер доступен, используем сохраненный токен
                auth_token = self.auth_manager.get_auth_token()
                if auth_token:
                    self.auth_token = auth_token
                    self.current_user = self.auth_manager.get_user_data()
                    
                    # Обновляем серверные данные
                    server_data['auth_token'] = self.auth_token
                    server_data['user_data'] = self.current_user
                    
                    # Отправляем сигнал
                    self.server_selected.emit(server_data)
                    self.accept()
                    return
        except:
            pass
        
        # Сервер недоступен или токен недействителен
        self.status_label.setText("❌ Сервер недоступен. Выберите другой сервер.")
        self.show_server_browser()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    dialog = LoginDialog()
    
    def on_server_selected(server_data):
        print(f"✅ Server selected: {server_data.get('name')}")
        print(f"   👤 User: {server_data.get('user_data', {}).get('username')}")
        print(f"   📡 Address: {server_data.get('ip')}:{server_data.get('port')}")
    
    dialog.server_selected.connect(on_server_selected)
    
    if dialog.exec_() == QDialog.Accepted:
        print("✅ Login successful!")
    else:
        print("🚪 Login cancelled")
    
    sys.exit(0)