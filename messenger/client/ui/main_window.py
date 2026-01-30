from PyQt5.QtWidgets import (QMainWindow, QSplitter, QTabWidget, QListWidget,
                             QVBoxLayout, QHBoxLayout, QWidget, QLabel,
                             QStatusBar, QMenuBar, QAction, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon
from ui.chat_widget import ChatWidget
import requests
from config import SERVER_URL

class MainWindow(QMainWindow):
    connection_status_changed = pyqtSignal(bool)
    
    def __init__(self, auth_token, current_user):
        super().__init__()
        self.auth_token = auth_token
        self.current_user = current_user
        self.contacts = []
        self.init_ui()
        self.load_contacts()
        
        # Таймер для автообновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_contacts)
        self.update_timer.start(10000)  # Обновлять каждые 10 секунд

    def update_contacts(self):
        """Обновление списка контактов"""
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(f"{SERVER_URL}/users", headers=headers)
            
            if response.status_code == 200:
                updated_contacts = response.json()
                
                # Обновляем основной список контактов
                self.contacts = updated_contacts
                
                # Обновляем отображение в списке
                self.contacts_list.clear()
                for user in self.contacts:
                    status_icon = "🟢" if user["is_online"] else "⚫"
                    self.contacts_list.addItem(f"{status_icon} {user['username']}")
                
                self.statusBar().showMessage("Contacts updated")
            else:
                QMessageBox.warning(self, "Error", "Failed to load contacts")
                
        except requests.exceptions.ConnectionError:
            self.statusBar().showMessage("Disconnected")
            QMessageBox.critical(self, "Error", "Cannot connect to server")
    
    def init_ui(self):
        self.setWindowTitle("Local Messenger")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Contacts list
        self.contacts_list = QListWidget()
        self.contacts_list.currentRowChanged.connect(self.on_contact_selected)
        splitter.addWidget(self.contacts_list)
        
        # Chat area
        self.chat_tabs = QTabWidget()
        self.chat_tabs.setTabsClosable(True)
        self.chat_tabs.tabCloseRequested.connect(self.close_chat_tab)
        splitter.addWidget(self.chat_tabs)
        
        splitter.setSizes([300, 900])
        layout.addWidget(splitter)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Status bar
        self.statusBar().showMessage("Connected")
        
    def create_menu_bar(self):
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        # Добавляем метод logout
        logout_action = QAction("Logout", self)
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menu_bar.addMenu("View")
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def load_contacts(self):
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(f"{SERVER_URL}/users", headers=headers)
            
            if response.status_code == 200:
                self.contacts = response.json()
                self.contacts_list.clear()
                for user in self.contacts:
                    # УБРАНА ПРОВЕРКА - теперь видим всех пользователей включая себя
                    status_icon = "🟢" if user["is_online"] else "⚫"
                    self.contacts_list.addItem(f"{status_icon} {user['username']}")
            else:
                QMessageBox.warning(self, "Error", "Failed to load contacts")
                
        except requests.exceptions.ConnectionError:
            self.statusBar().showMessage("Disconnected")
            QMessageBox.critical(self, "Error", "Cannot connect to server")
            
    def on_contact_selected(self, row):
        if row >= 0 and row < len(self.contacts):
            contact = self.contacts[row]
            self.open_chat(contact)
            
    def open_chat(self, contact):
        print(f"🔧 Opening chat with: {contact['username']} (ID: {contact['id']})")
        
        # Check if chat already open
        for i in range(self.chat_tabs.count()):
            if self.chat_tabs.widget(i).contact["id"] == contact["id"]:
                self.chat_tabs.setCurrentIndex(i)
                return
        
        # Create new chat tab
        chat_widget = ChatWidget(self.auth_token, self.current_user, contact)
        self.chat_tabs.addTab(chat_widget, contact["username"])
        self.chat_tabs.setCurrentIndex(self.chat_tabs.count() - 1)
        
    def close_chat_tab(self, index):
        self.chat_tabs.removeTab(index)
        
    def logout(self):
        """Выход из системы с обновлением статуса"""
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Отправляем запрос на выход
            response = requests.post(
                f"{SERVER_URL}/auth/logout",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✅ User {self.current_user['id']} logged out successfully")
            else:
                print(f"⚠️ Logout API error: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("⚠️ Cannot connect to server during logout")
        except Exception as e:
            print(f"⚠️ Logout error: {e}")
        finally:
            # Закрываем все WebSocket соединения в чатах
            for i in range(self.chat_tabs.count()):
                chat_widget = self.chat_tabs.widget(i)
                if hasattr(chat_widget, 'websocket'):
                    try:
                        chat_widget.websocket.disconnect()
                    except:
                        pass
            
            # Закрываем окно
            self.close()
        
    def show_about(self):
        QMessageBox.about(self, "About", "Local Messenger v1.0 FORK by Malinevskiy Egor\nA simple local messaging application\n meow miaw :D")
        
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        try:
            # Пытаемся отправить запрос на выход при закрытии
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.post(
                f"{SERVER_URL}/auth/logout",
                headers=headers,
                timeout=2
            )
        except:
            pass  # Игнорируем ошибки при закрытии
        
        # Закрываем все WebSocket соединения
        for i in range(self.chat_tabs.count()):
            chat_widget = self.chat_tabs.widget(i)
            if hasattr(chat_widget, 'websocket'):
                try:
                    chat_widget.websocket.disconnect()
                except:
                    pass
        
        event.accept()