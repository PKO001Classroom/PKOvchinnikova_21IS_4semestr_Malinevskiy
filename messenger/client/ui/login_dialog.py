from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QInputDialog)
from PyQt5.QtCore import Qt
import requests
from config import SERVER_URL

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.auth_token = None
        self.current_user = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Login")
        self.setGeometry(300, 300, 300, 150)
        
        layout = QVBoxLayout()
        
        # Username
        layout.addWidget(QLabel("Username:"))
        self.username_edit = QLineEdit()
        layout.addWidget(self.username_edit)
        
        # Password
        layout.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.login_btn = QPushButton("Login")
        self.register_btn = QPushButton("Register")
        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.register_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect signals - УБЕДИТЕСЬ ЧТО ЭТИ СТРОКИ ЕСТЬ!
        self.login_btn.clicked.connect(self.login)
        self.register_btn.clicked.connect(self.register)
        
    def login(self):  # ЭТОТ МЕТОД ДОЛЖЕН БЫТЬ!
        username = self.username_edit.text()
        password = self.password_edit.text()
        
        print(f"Trying to login: {username}")  # Debug
        
        try:
            response = requests.post(
                f"{SERVER_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=10
            )
            
            print(f"Status: {response.status_code}")  # Debug
            print(f"Response text: {response.text}")  # Debug
            
            if response.status_code == 200:
                try:
                    self.auth_token = response.json()["access_token"]
                    self.current_user = self.get_current_user()
                    self.accept()
                except:
                    QMessageBox.warning(self, "Error", "Invalid server response")
            else:
                # Пробуем получить JSON ошибки
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", "Invalid credentials")
                    QMessageBox.warning(self, "Error", error_detail)
                except:
                    QMessageBox.warning(self, "Error", 
                                      f"Login failed: {response.status_code}\n"
                                      f"Response: {response.text[:100]}...")
                    
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Error", "Cannot connect to server")
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Error", "Request timeout")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
    
    def register(self):  # И ЭТОТ МЕТОД ТОЖЕ ДОЛЖЕН БЫТЬ!
        username = self.username_edit.text()
        password = self.password_edit.text()
        
        print(f"Trying to register: {username}")  # Debug
        
        try:
            response = requests.post(
                f"{SERVER_URL}/auth/register",
                json={"username": username, "password": password},
                timeout=10
            )
            
            print(f"Status: {response.status_code}")  # Debug
            print(f"Response text: {response.text}")  # Debug
            
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Registration successful")
            else:
                # Пробуем получить JSON ошибки, если доступен
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", "Unknown error")
                    QMessageBox.warning(self, "Error", error_detail)
                except:
                    # Если не JSON, показываем сырой текст ответа
                    QMessageBox.warning(self, "Error", 
                                      f"Server error: {response.status_code}\n"
                                      f"Response: {response.text[:100]}...")
                    
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Error", "Cannot connect to server")
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Error", "Request timeout")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
    
    def get_current_user(self):
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(f"{SERVER_URL}/users/me", headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get user info: {response.status_code}")
                return None
        except:
            return None