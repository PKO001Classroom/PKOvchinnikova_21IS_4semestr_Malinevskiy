"""
Виджет чата для обмена сообщениями.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QLineEdit, QPushButton, QLabel, QScrollArea, 
                             QMessageBox, QInputDialog, QFileDialog, QMenu,
                             QProgressBar, QFrame, QApplication)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QUrl
from PyQt5.QtGui import (QTextCursor, QPixmap, QTextImageFormat, QTextCharFormat,
                        QFont, QDesktopServices, QTextDocument, QColor)
import requests
import os
import base64
import tempfile
import json
from datetime import datetime, timedelta

# Импорт модулей из новой структуры
try:
    from client.config import SERVER_URL, WEBSOCKET_URL, APP_NAME
    from client.models.message import Message
    from client.network.websocket_client import MessengerWebSocket
except ImportError as e:
    print(f"Ошибка импорта в chat_widget.py: {e}")


class ChatWidget(QWidget):
    # Добавляем сигнал для обновления статуса
    status_updated = pyqtSignal(dict)
    # Сигнал для уведомлений о новых сообщениях
    new_message_signal = pyqtSignal(str, str, bool)  # sender_name, message_text, is_important
    
    def __init__(self, auth_token, current_user, contact, server_url=None):
        super().__init__()
        self.auth_token = auth_token
        self.current_user = current_user
        self.contact = contact
        self.server_url = server_url or SERVER_URL
        self.contact_label = None  # Сохраняем ссылку на label
        self.messages = []
        self.temp_files = []
        self.init_ui()
        self.load_messages()
        
        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.check_new_messages)
        self.update_timer.start(5000)  # Check every 5 seconds
        
        # Timer для обновления статуса
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_contact_status)
        self.status_timer.start(10000)  # Обновлять статус каждые 10 секунд
        
        # Инициализация WebSocket
        self.websocket = None
        self.init_websocket()
        
        # Подключаем сигнал
        self.status_updated.connect(self.on_status_updated)

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Панель контакта
        contact_panel = QFrame()
        contact_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
                padding: 10px 15px;
            }
            QLabel {
                font-size: 14px;
            }
        """)
        
        contact_layout = QHBoxLayout(contact_panel)
        
        # Информация о контакте
        self.contact_layout = QHBoxLayout()
        self.update_status_display()  # Выносим в отдельный метод
        contact_layout.addLayout(self.contact_layout)
        
        # Действия с контактом
        actions_layout = QHBoxLayout()
        
        # Кнопка информации
        info_btn = QPushButton("ℹ️")
        info_btn.setToolTip("Информация о контакте")
        info_btn.setFixedSize(30, 30)
        info_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 15px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        info_btn.clicked.connect(self.show_contact_info)
        actions_layout.addWidget(info_btn)
        
        contact_layout.addLayout(actions_layout)
        layout.addWidget(contact_panel)
        
        # Область сообщений
        messages_frame = QFrame()
        messages_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: none;
            }
        """)
        
        messages_layout = QVBoxLayout(messages_frame)
        
        # Прокручиваемая область для сообщений
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f0f0f0;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
        """)
        
        self.messages_area = QTextEdit()
        self.messages_area.setReadOnly(True)
        self.messages_area.setAcceptRichText(True)
        self.messages_area.document().setDocumentMargin(10)
        self.messages_area.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: none;
                font-size: 13px;
                padding: 10px;
            }
        """)
        
        # Устанавливаем минимальную высоту
        self.messages_area.setMinimumHeight(300)
        
        scroll_area.setWidget(self.messages_area)
        messages_layout.addWidget(scroll_area)
        
        layout.addWidget(messages_frame, 1)  # Растягиваем на все доступное пространство
        
        # Панель ввода
        input_panel = QFrame()
        input_panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border-top: 1px solid #dee2e6;
                padding: 10px;
            }
        """)
        
        input_layout = QHBoxLayout(input_panel)
        input_layout.setSpacing(10)
        
        # Кнопка прикрепления файла
        self.file_button = QPushButton("📎")
        self.file_button.setToolTip("Прикрепить файл")
        self.file_button.setFixedSize(40, 40)
        self.file_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 20px;
                background-color: white;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.file_button.clicked.connect(self.send_file)
        input_layout.addWidget(self.file_button)
        
        # Поле ввода сообщения
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 20px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #1976d2;
            }
        """)
        input_layout.addWidget(self.message_input, 1)  # Растягиваем
        
        # Кнопка отправки
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setFixedSize(100, 40)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        input_layout.addWidget(self.send_button)
        
        layout.addWidget(input_panel)
        
        self.setLayout(layout)
        
        # Контекстное меню для сообщений
        self.messages_area.setContextMenuPolicy(Qt.CustomContextMenu)
        self.messages_area.customContextMenuRequested.connect(self.show_context_menu)
        
    def init_websocket(self):
        """Инициализация WebSocket соединения"""
        try:
            self.websocket = MessengerWebSocket(self.current_user["id"], self.server_url)
            self.websocket.message_received.connect(self.handle_websocket_message)
            self.websocket.status_updated.connect(self.handle_status_update)
            self.websocket.connect()
        except Exception as e:
            print(f"⚠️ WebSocket initialization error: {e}")
            QMessageBox.warning(self, "WebSocket", 
                              f"Не удалось инициализировать WebSocket: {str(e)}")

    def handle_websocket_message(self, data):
        """Обработка сообщений от WebSocket"""
        if data.get("type") == "message_deleted":
            message_id = data.get("message_id")
            self._remove_message(message_id)
            
    def _remove_message(self, message_id):
        """Удаление сообщения из интерфейса"""
        # Удаляем из списка сообщений
        self.messages = [msg for msg in self.messages if msg.id != message_id]
        
        # Обновляем отображение
        self.display_messages()
        
    def delete_message(self, message_id):
        """Удаление сообщения с уведомлением через WebSocket"""
        print(f"🔧 Attempting to delete message {message_id}")
        
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.delete(
                f"{self.server_url}/messages/{message_id}", 
                headers=headers,
                timeout=5
            )
            
            print(f"🔧 Delete response: {response.status_code}")
            
            if response.status_code == 200:
                # Локально удаляем сообщение
                self._remove_message(message_id)
                print(f"✅ Message {message_id} deleted locally")
                
                # Проверяем WebSocket соединение
                if self.websocket and self.websocket.is_connected:
                    # Отправляем уведомление через WebSocket
                    notification = {
                        "type": "message_deleted", 
                        "message_id": message_id,
                        "deleted_by": self.current_user["id"],
                        "timestamp": datetime.now().isoformat()
                    }
                    print(f"🔧 Sending WebSocket notification: {notification}")
                    self.websocket.send_message(notification)
                else:
                    print("⚠️ WebSocket not connected, cannot send notification")
                    # Если WebSocket не работает, обновляем чат через HTTP
                    self.load_messages()
                    
            else:
                error_msg = f"Cannot delete message: {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text}"
                QMessageBox.warning(self, "Error", error_msg)
                print(f"❌ Delete failed: {error_msg}")
                
        except requests.exceptions.ConnectionError:
            QMessageBox.warning(self, "Error", "Cannot connect to server")
            print(f"❌ Connection error during delete")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot delete message: {str(e)}")
            print(f"❌ Unexpected error during delete: {e}")

    def send_file(self):
        """Отправка файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Выберите файл", 
            "", 
            "Изображения (*.png *.jpg *.jpeg *.gif *.bmp);;Все файлы (*.*)"
        )
        
        if file_path:
            try:
                # Проверяем размер файла
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                if file_size > 10:  # Максимальный размер 10MB
                    QMessageBox.warning(self, "Ошибка", 
                                      f"Файл слишком большой ({file_size:.1f} MB). Максимальный размер: 10 MB")
                    return
                
                # Показываем прогресс
                progress_dialog = QMessageBox(self)
                progress_dialog.setWindowTitle("Отправка файла")
                progress_dialog.setText("Загрузка файла...")
                progress_dialog.setStandardButtons(QMessageBox.Cancel)
                progress_dialog.show()
                
                # Читаем файл
                with open(file_path, "rb") as f:
                    file_data = base64.b64encode(f.read()).decode('utf-8')
                
                filename = os.path.basename(file_path)
                
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "content": f"Файл: {filename}",
                    "receiver_id": self.contact["id"],
                    "message_type": "image" if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')) else "file",
                    "file_data": file_data
                }
                
                response = requests.post(
                    f"{self.server_url}/messages", 
                    json=payload, 
                    headers=headers,
                    timeout=30
                )
                
                progress_dialog.close()
                
                if response.status_code == 200:
                    message_data = response.json()
                    message_data["file_data"] = file_data  # Сохраняем данные файла
                    message = Message.from_dict(message_data)
                    self.messages.append(message)
                    self.add_message_to_display(message)
                    
                    # Прокручиваем к последнему сообщению
                    self.messages_area.ensureCursorVisible()
                    
                else:
                    QMessageBox.warning(self, "Ошибка", 
                                      f"Не удалось отправить файл: {response.status_code}")
                    
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Ошибка отправки файла: {str(e)}")
                            
    def show_context_menu(self, position):
        """Показ контекстного меню"""
        menu = QMenu()
        
        # Копировать
        copy_action = menu.addAction("📋 Копировать")
        copy_action.triggered.connect(self.copy_selected_text)
        
        # Удалить сообщение
        delete_action = menu.addAction("🗑️ Удалить сообщение")
        delete_action.triggered.connect(self.show_delete_dialog)
        
        menu.exec_(self.messages_area.mapToGlobal(position))

    def show_delete_dialog(self):
        """Диалог удаления сообщения"""
        message_id, ok = QInputDialog.getInt(
            self, 
            "Удалить сообщение", 
            "Введите ID сообщения:", 
            min=1
        )
        
        if ok:
            self.delete_message(message_id)
            
    def copy_selected_text(self):
        """Копирование выделенного текста"""
        cursor = self.messages_area.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            QApplication.clipboard().setText(selected_text)
            
    def load_messages(self):
        """Загрузка сообщений"""
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(
                f"{self.server_url}/messages?contact_id={self.contact['id']}&limit=100",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                messages_data = response.json()["messages"]
                self.messages = [Message.from_dict(msg) for msg in messages_data]
                self.display_messages()
                
                # Прокручиваем к последнему сообщению
                self.messages_area.moveCursor(QTextCursor.End)
            else:
                print(f"Failed to load messages: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("Cannot connect to server")
        except Exception as e:
            print(f"Error loading messages: {e}")
            
    def display_messages(self):
        """Отображение всех сообщений"""
        self.messages_area.clear()
        
        # Группируем сообщения по дате
        messages_by_date = {}
        for message in sorted(self.messages, key=lambda x: x.timestamp):
            date_key = message.timestamp.date()
            if date_key not in messages_by_date:
                messages_by_date[date_key] = []
            messages_by_date[date_key].append(message)
        
        # Отображаем сообщения с заголовками дат
        for date, messages in messages_by_date.items():
            self.add_date_separator(date)
            for message in messages:
                self.add_message_to_display(message)
                
    def add_date_separator(self, date):
        """Добавление разделителя даты"""
        cursor = self.messages_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Форматируем дату
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        if date == today:
            date_text = "Сегодня"
        elif date == yesterday:
            date_text = "Вчера"
        else:
            date_text = date.strftime("%d %B %Y")
        
        html = f"""
        <div style="text-align: center; margin: 20px 0;">
            <span style="background-color: #e0e0e0; color: #666; 
                       padding: 5px 15px; border-radius: 15px; 
                       font-size: 12px;">
                {date_text}
            </span>
        </div>
        """
        
        self.messages_area.append(html)
            
    def add_message_to_display(self, message):
        """Добавление одного сообщения в отображение"""
        cursor = self.messages_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Определяем отправителя и стили
        is_outgoing = message.is_outgoing(self.current_user["id"])
        sender_name = "Вы" if is_outgoing else self.contact["username"]
        alignment = "right" if is_outgoing else "left"
        bg_color = "#e3f2fd" if is_outgoing else "#f5f5f5"
        text_color = "#1976d2" if is_outgoing else "#333333"
        
        # Отправляем сигнал для уведомлений если сообщение от другого пользователя
        if not is_outgoing and self.parent() and not self.parent().isActiveWindow():
            # Проверяем, активно ли окно родителя
            self.new_message_signal.emit(
                sender_name,
                message.content[:100] + ("..." if len(message.content) > 100 else ""),
                False
            )
        
        # Для изображений создаем временный файл и отображаем картинку
        if message.message_type == "image" and hasattr(message, 'file_data') and message.file_data:
            try:
                # Декодируем base64 и создаем временный файл
                image_data = base64.b64decode(message.file_data)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                temp_file.write(image_data)
                temp_file.close()
                self.temp_files.append(temp_file.name)  # Сохраняем для очистки
                
                # Добавляем заголовок с именем отправителя и временем
                header_html = f"""
                <div style="text-align: {alignment}; margin-bottom: 5px;">
                    <span style="font-size: 12px; color: {text_color}; font-weight: bold;">
                        {sender_name} • {message.get_formatted_time()}
                    </span>
                </div>
                """
                self.messages_area.append(header_html)
                
                # Добавляем изображение в текст
                cursor = self.messages_area.textCursor()
                cursor.movePosition(QTextCursor.End)
                
                # Вставляем HTML с изображением
                image_html = f"""
                <div style="text-align: {alignment}; margin: 5px 0;">
                    <img src="file:///{temp_file.name}" 
                         style="max-width: 300px; max-height: 300px; 
                                border-radius: 10px; border: 1px solid #ddd;" 
                         alt="Изображение">
                </div>
                """
                self.messages_area.append(image_html)
                
                # Добавляем ID сообщения под изображением
                footer_html = f"""
                <div style="text-align: {alignment}; margin-top: 5px;">
                    <span style="font-size: 10px; color: #999;">
                        ID: {message.id}
                    </span>
                </div>
                <div style="clear: both; margin-bottom: 15px;"></div>
                """
                self.messages_area.append(footer_html)
                
            except Exception as e:
                print(f"Error displaying image: {e}")
                # Fallback to text representation
                self.add_text_message(message, sender_name, alignment, bg_color, text_color)
        else:
            # Обычное текстовое сообщение
            self.add_text_message(message, sender_name, alignment, bg_color, text_color)
        
        self.messages_area.ensureCursorVisible()

    def add_text_message(self, message, sender_name, alignment, bg_color, text_color):
        """Добавление текстового сообщения с полной информацией"""
        html = f"""
        <div style="margin: 5px 0; text-align: {alignment};">
            <div style="display: inline-block; max-width: 70%; 
                      background-color: {bg_color}; 
                      border-radius: 15px; padding: 10px 15px;
                      border-top-{alignment}-radius: 5px;">
                <div style="font-size: 12px; color: {text_color}; 
                          font-weight: bold; margin-bottom: 5px;">
                    {sender_name} • {message.get_formatted_time()}
                </div>
                <div style="color: #333; word-wrap: break-word; 
                          white-space: pre-wrap;">
                    {message.content}
                </div>
                <div style="font-size: 10px; color: #999; margin-top: 5px; 
                          text-align: right;">
                    ID: {message.id}
                </div>
            </div>
        </div>
        <div style="clear: both; margin-bottom: 5px;"></div>
        """
        self.messages_area.append(html)
        
    def send_message(self):
        """Отправка сообщения"""
        message_text = self.message_input.text().strip()
        if not message_text:
            return
            
        try:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "content": message_text,
                "receiver_id": self.contact["id"],
                "message_type": "text"
            }
            
            print(f"🔧 Debug - Sending message to: {self.server_url}/messages")
            print(f"🔧 Debug - Payload: {payload}")
            
            response = requests.post(
                f"{self.server_url}/messages",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            print(f"🔧 Debug - Response Status: {response.status_code}")
            
            if response.status_code == 200:
                self.message_input.clear()
                message_data = response.json()
                message = Message.from_dict(message_data)
                self.messages.append(message)
                self.add_message_to_display(message)
                
                # Прокручиваем к последнему сообщению
                self.messages_area.moveCursor(QTextCursor.End)
                
                print("✅ Message sent successfully!")
            else:
                print(f"❌ Failed to send message. Status: {response.status_code}")
                print(f"❌ Response: {response.text}")
                
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                    QMessageBox.warning(self, "Ошибка", f"Не удалось отправить сообщение: {error_detail}")
                except:
                    QMessageBox.warning(self, "Ошибка", f"Не удалось отправить сообщение. Статус: {response.status_code}")
                    
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к серверу")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Неожиданная ошибка: {str(e)}")
            print(f"❌ Unexpected error: {e}")

    def update_status_display(self):
        """Обновление отображения статуса контакта"""
        # Очищаем layout
        while self.contact_layout.count():
            item = self.contact_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Создаем новый label с актуальным статусом
        status_icon = "🟢" if self.contact.get("is_online", False) else "⚫"
        last_seen_text = ""
        
        # Добавляем время последней активности, если есть
        if self.contact.get("last_seen"):
            try:
                last_seen = datetime.fromisoformat(self.contact["last_seen"])
                now = datetime.now()
                diff = now - last_seen
                
                if diff.days > 0:
                    last_seen_text = f" (был {diff.days} д. назад)"
                elif diff.seconds > 3600:
                    hours = diff.seconds // 3600
                    last_seen_text = f" (был {hours} ч. назад)"
                elif diff.seconds > 60:
                    minutes = diff.seconds // 60
                    last_seen_text = f" (был {minutes} мин. назад)"
                else:
                    last_seen_text = " (только что)"
            except:
                pass
        
        username = self.contact.get("username", "Unknown")
        status_text = f"{status_icon} {username}{last_seen_text}"
        
        self.contact_label = QLabel(status_text)
        self.contact_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.contact_layout.addWidget(self.contact_label)
        
        # Добавляем кнопку информации
        info_btn = QPushButton("ℹ️")
        info_btn.setFixedSize(24, 24)
        info_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-radius: 12px;
            }
        """)
        info_btn.clicked.connect(self.show_contact_info)
        info_btn.setToolTip("Информация о контакте")
        self.contact_layout.addWidget(info_btn)
        
        # Растягивающийся спейсер
        self.contact_layout.addStretch()
    
    def on_status_updated(self, updated_contact):
        """Обработчик сигнала обновления статуса"""
        try:
            # Обновляем отображение
            self.update_status_display()
            
            # Обновляем заголовок вкладки (если есть доступ)
            parent = self.parent()
            if parent and hasattr(parent, 'setTabText'):
                tab_index = parent.indexOf(self)
                if tab_index >= 0:
                    status_icon = "🟢" if updated_contact.get("is_online", False) else "⚫"
                    parent.setTabText(tab_index, f"{status_icon} {updated_contact['username']}")
                    
        except Exception as e:
            print(f"⚠️ Error updating status display: {e}")
    
    def handle_status_update(self, status_data):
        """Обработка уведомления об изменении статуса"""
        try:
            user_id = status_data.get("user_id")
            is_online = status_data.get("is_online", False)
            
            # Проверяем, относится ли уведомление к нашему контакту
            if user_id == self.contact["id"]:
                print(f"📡 WebSocket status update: {self.contact['username']} is now {'🟢 online' if is_online else '⚫ offline'}")
                
                # Обновляем статус контакта
                self.contact["is_online"] = is_online
                self.contact["last_seen"] = status_data.get("timestamp")
                
                # Обновляем отображение
                self.status_updated.emit(self.contact)
                
        except Exception as e:
            print(f"⚠️ Error handling status update: {e}")
        
    def check_new_messages(self):
        """Проверка новых сообщений"""
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(
                f"{self.server_url}/messages/unread",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                unread_messages = response.json()["messages"]
                for msg_data in unread_messages:
                    message = Message.from_dict(msg_data)
                    if message.sender_id == self.contact["id"]:
                        self.messages.append(message)
                        self.add_message_to_display(message)
                        
                        # Прокручиваем к последнему сообщению
                        self.messages_area.moveCursor(QTextCursor.End)
                        
                        # Mark as read
                        requests.put(
                            f"{self.server_url}/messages/{message.id}/read",
                            headers=headers,
                            timeout=5
                        )
                        
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"Error checking new messages: {e}")
            
    def update_contact_status(self):
        """Обновление информации о контакте с сервера"""
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = requests.get(
                f"{self.server_url}/users/{self.contact['id']}",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                updated_contact = response.json()
                
                # Проверяем, изменился ли статус
                old_status = self.contact.get("is_online", False)
                new_status = updated_contact.get("is_online", False)
                
                if old_status != new_status:
                    print(f"🔄 Status changed for {updated_contact['username']}: "
                          f"{'🟢 online' if new_status else '⚫ offline'}")
                
                # Обновляем контакт
                self.contact.update(updated_contact)
                
                # Используем сигнал для безопасного обновления UI
                self.status_updated.emit(self.contact)
                
        except requests.exceptions.ConnectionError:
            print("⚠️ Cannot connect to server for status update")
        except requests.exceptions.Timeout:
            print("⚠️ Status update request timeout")
        except Exception as e:
            print(f"⚠️ Error updating contact status: {e}")
    
    def show_contact_info(self):
        """Показ информации о контакте"""
        info_text = f"""
        <h3>Информация о контакте</h3>
        <p><b>Имя:</b> {self.contact.get('username', 'Неизвестно')}</p>
        <p><b>Статус:</b> {'🟢 В сети' if self.contact.get('is_online', False) else '⚫ Не в сети'}</p>
        <p><b>ID:</b> {self.contact.get('id', 'Неизвестно')}</p>
        """
        
        if self.contact.get('last_seen'):
            info_text += f"<p><b>Был в сети:</b> {self.contact['last_seen']}</p>"
        
        QMessageBox.information(self, "Информация о контакте", info_text)
    
    def closeEvent(self, event):
        """Обработчик закрытия виджета"""
        # Закрываем WebSocket соединение
        if self.websocket:
            try:
                self.websocket.disconnect()
            except:
                pass
        
        # Очищаем временные файлы
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        # Останавливаем таймеры
        self.update_timer.stop()
        self.status_timer.stop()
        
        event.accept()