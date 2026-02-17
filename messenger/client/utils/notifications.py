"""
Система уведомлений для клиента Local Messenger.
Поддержка desktop notifications и звуковых уведомлений.
"""

import os
import sys
import platform
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
import logging

logger = logging.getLogger(__name__)


class NotificationManager(QObject):
    """
    Менеджер уведомлений для клиента.
    """
    
    notification_clicked = pyqtSignal(str)  # Сигнал при клике на уведомление
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.enabled = True
        self.sound_enabled = True
        self.tray_icon = None
        self.notification_history = []
        self.max_history = 50
        
        self.init_notification_system()
        logger.info("NotificationManager инициализирован")
    
    def init_notification_system(self):
        """Инициализация системы уведомлений"""
        try:
            # Проверяем поддержку уведомлений для текущей ОС
            system = platform.system()
            self.supported = system in ['Windows', 'Darwin', 'Linux']
            
            if not self.supported:
                logger.warning(f"Уведомления не поддерживаются для ОС: {system}")
                return
            
            # Инициализируем звуковые уведомления
            self.init_sounds()
            
            # Загружаем настройки
            self.load_settings()
            
            logger.info(f"Система уведомлений инициализирована для {system}")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации системы уведомлений: {e}")
            self.supported = False
    
    def init_sounds(self):
        """Инициализация звуковых уведомлений"""
        self.sounds = {
            'message': self.get_sound_path('message.wav'),
            'file': self.get_sound_path('file.wav'),
            'call': self.get_sound_path('call.wav'),
            'error': self.get_sound_path('error.wav')
        }
        
        # Проверяем наличие звуковых файлов
        for name, path in self.sounds.items():
            if not os.path.exists(path):
                logger.warning(f"Звуковой файл не найден: {path}")
    
    def get_sound_path(self, filename):
        """Получение пути к звуковому файлу"""
        # Пытаемся найти в директории sounds
        base_dir = Path(__file__).parent.parent
        sound_dir = base_dir / "sounds"
        
        if not sound_dir.exists():
            sound_dir.mkdir(exist_ok=True)
        
        sound_path = sound_dir / filename
        
        # Если файла нет, создаем пустой (для совместимости)
        if not sound_path.exists():
            # Можно создать базовый WAV файл программно
            self.create_default_sound(sound_path)
        
        return str(sound_path)
    
    def create_default_sound(self, path):
        """Создание звукового файла по умолчанию"""
        try:
            # Простейший WAV файл (1 секунда синусоиды)
            import wave
            import struct
            import math
            
            # Параметры звука
            sample_rate = 44100
            duration = 0.5  # секунды
            frequency = 800  # Гц
            
            # Создаем файл
            with wave.open(str(path), 'w') as wav_file:
                wav_file.setnchannels(1)  # Моно
                wav_file.setsampwidth(2)   # 16 бит
                wav_file.setframerate(sample_rate)
                
                # Генерируем синусоиду
                frames = []
                for i in range(int(duration * sample_rate)):
                    value = int(32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
                    frames.append(struct.pack('<h', value))
                
                wav_file.writeframes(b''.join(frames))
            
            logger.info(f"Создан звуковой файл по умолчанию: {path}")
            
        except Exception as e:
            logger.error(f"Ошибка создания звукового файла: {e}")
    
    def load_settings(self):
        """Загрузка настроек уведомлений"""
        try:
            from client.auth_manager import get_auth_manager
            auth_manager = get_auth_manager()
            
            self.enabled = auth_manager.get_setting('notifications', True)
            self.sound_enabled = auth_manager.get_setting('sound_notifications', True)
            
            logger.debug(f"Настройки уведомлений: enabled={self.enabled}, sound={self.sound_enabled}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек уведомлений: {e}")
    
    def save_settings(self):
        """Сохранение настроек уведомлений"""
        try:
            from client.auth_manager import get_auth_manager
            auth_manager = get_auth_manager()
            
            auth_manager.set_setting('notifications', self.enabled)
            auth_manager.set_setting('sound_notifications', self.sound_enabled)
            
            logger.debug("Настройки уведомлений сохранены")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек уведомлений: {e}")
    
    def show_notification(self, title, message, notification_type='message', data=None):
        """
        Показать уведомление.
        
        Args:
            title: Заголовок уведомления
            message: Текст уведомления
            notification_type: Тип уведомления (message, file, call, error)
            data: Дополнительные данные для обработки клика
        """
        if not self.enabled or not self.supported:
            return
        
        try:
            # Проигрываем звук если включен
            if self.sound_enabled and notification_type in self.sounds:
                self.play_sound(notification_type)
            
            # Добавляем в историю
            notification = {
                'title': title,
                'message': message,
                'type': notification_type,
                'timestamp': self.get_timestamp(),
                'data': data
            }
            
            self.notification_history.append(notification)
            
            # Ограничиваем размер истории
            if len(self.notification_history) > self.max_history:
                self.notification_history = self.notification_history[-self.max_history:]
            
            # Показываем уведомление в зависимости от ОС
            system = platform.system()
            
            if system == 'Windows':
                self.show_windows_notification(title, message, notification_type)
            elif system == 'Darwin':  # macOS
                self.show_macos_notification(title, message, notification_type)
            elif system == 'Linux':
                self.show_linux_notification(title, message, notification_type)
            
            logger.debug(f"Показано уведомление: {title} - {message}")
            
        except Exception as e:
            logger.error(f"Ошибка показа уведомления: {e}")
    
    def show_windows_notification(self, title, message, notification_type):
        """Показать уведомление в Windows"""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            
            # Длительность уведомления в зависимости от типа
            duration = 5  # секунд
            if notification_type == 'call':
                duration = 10  # Звонок дольше
            
            # Иконка в зависимости от типа
            icon_path = self.get_notification_icon(notification_type)
            
            toaster.show_toast(
                title,
                message,
                icon_path=icon_path if icon_path else None,
                duration=duration,
                threaded=True
            )
            
        except ImportError:
            # Fallback для старых Windows
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0)
        except Exception as e:
            logger.error(f"Ошибка Windows уведомления: {e}")
    
    def show_macos_notification(self, title, message, notification_type):
        """Показать уведомление в macOS"""
        try:
            import subprocess
            
            # Используем AppleScript для показа уведомления
            applescript = f'''
            display notification "{message}" with title "{title}"
            '''
            
            subprocess.run(['osascript', '-e', applescript])
            
        except Exception as e:
            logger.error(f"Ошибка macOS уведомления: {e}")
    
    def show_linux_notification(self, title, message, notification_type):
        """Показать уведомление в Linux"""
        try:
            import subprocess
            
            # Пробуем разные команды для разных дистрибутивов
            commands = [
                ['notify-send', title, message, '-t', '5000'],
                ['zenity', '--notification', '--text', f'{title}: {message}'],
                ['kdialog', '--passivepopup', f'{title}: {message}', '5']
            ]
            
            for cmd in commands:
                try:
                    subprocess.run(cmd, check=True)
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
        except Exception as e:
            logger.error(f"Ошибка Linux уведомления: {e}")
    
    def get_notification_icon(self, notification_type):
        """Получение иконки для уведомления"""
        icon_map = {
            'message': 'message_icon.png',
            'file': 'file_icon.png',
            'call': 'call_icon.png',
            'error': 'error_icon.png'
        }
        
        icon_name = icon_map.get(notification_type, 'message_icon.png')
        icon_path = Path(__file__).parent.parent / "icons" / icon_name
        
        if icon_path.exists():
            return str(icon_path)
        
        return None
    
    def play_sound(self, sound_type):
        """Проигрывание звука"""
        try:
            sound_path = self.sounds.get(sound_type)
            if not sound_path or not os.path.exists(sound_path):
                return
            
            system = platform.system()
            
            if system == 'Windows':
                import winsound
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif system == 'Darwin':
                import subprocess
                subprocess.run(['afplay', sound_path])
            elif system == 'Linux':
                import subprocess
                # Пробуем разные плееры
                players = ['aplay', 'paplay', 'play']
                for player in players:
                    try:
                        subprocess.run([player, sound_path], check=True)
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
            
        except Exception as e:
            logger.error(f"Ошибка проигрывания звука: {e}")
    
    def get_timestamp(self):
        """Получение текущего времени в формате строки"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def enable_notifications(self, enabled=True):
        """Включение/выключение уведомлений"""
        self.enabled = enabled
        self.save_settings()
        logger.info(f"Уведомления {'включены' if enabled else 'выключены'}")
    
    def enable_sound(self, enabled=True):
        """Включение/выключение звука"""
        self.sound_enabled = enabled
        self.save_settings()
        logger.info(f"Звуковые уведомления {'включены' if enabled else 'выключены'}")
    
    def get_notification_history(self, limit=20):
        """Получение истории уведомлений"""
        return self.notification_history[-limit:] if limit > 0 else self.notification_history.copy()
    
    def clear_notification_history(self):
        """Очистка истории уведомлений"""
        self.notification_history.clear()
        logger.info("История уведомлений очищена")
    
    def setup_tray_icon(self, parent_window):
        """Настройка иконки в системном трее"""
        try:
            if self.tray_icon:
                return
            
            self.tray_icon = QSystemTrayIcon(parent_window)
            
            # Устанавливаем иконку
            icon_path = Path(__file__).parent.parent / "icons" / "app_icon.png"
            if icon_path.exists():
                self.tray_icon.setIcon(QIcon(str(icon_path)))
            
            # Создаем меню трея
            tray_menu = QMenu()
            
            # Показать/скрыть
            show_action = QAction("Показать", parent_window)
            show_action.triggered.connect(parent_window.show)
            tray_menu.addAction(show_action)
            
            hide_action = QAction("Скрыть", parent_window)
            hide_action.triggered.connect(parent_window.hide)
            tray_menu.addAction(hide_action)
            
            tray_menu.addSeparator()
            
            # Настройки уведомлений
            notifications_menu = QMenu("Уведомления", parent_window)
            
            toggle_notifications = QAction("Включить уведомления", parent_window)
            toggle_notifications.setCheckable(True)
            toggle_notifications.setChecked(self.enabled)
            toggle_notifications.triggered.connect(lambda: self.enable_notifications(toggle_notifications.isChecked()))
            notifications_menu.addAction(toggle_notifications)
            
            toggle_sound = QAction("Звуковые уведомления", parent_window)
            toggle_sound.setCheckable(True)
            toggle_sound.setChecked(self.sound_enabled)
            toggle_sound.triggered.connect(lambda: self.enable_sound(toggle_sound.isChecked()))
            notifications_menu.addAction(toggle_sound)
            
            tray_menu.addMenu(notifications_menu)
            
            tray_menu.addSeparator()
            
            # Выход
            exit_action = QAction("Выход", parent_window)
            exit_action.triggered.connect(parent_window.close)
            tray_menu.addAction(exit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
            
            # Обработка клика по иконке
            self.tray_icon.activated.connect(self.on_tray_activated)
            
            logger.info("Иконка в системном трее настроена")
            
        except Exception as e:
            logger.error(f"Ошибка настройки иконки в трее: {e}")
    
    def on_tray_activated(self, reason):
        """Обработка активации иконки в трее"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.notification_clicked.emit('tray_double_click')
    
    def notify_new_message(self, sender, message, is_important=False):
        """Уведомление о новом сообщении"""
        if not self.enabled:
            return
        
        title = f"📨 Новое сообщение от {sender}"
        
        # Обрезаем длинные сообщения
        if len(message) > 100:
            message = message[:97] + "..."
        
        notification_type = 'message'
        if is_important:
            notification_type = 'call'  # Более заметное уведомление
        
        self.show_notification(title, message, notification_type, {'sender': sender})
    
    def notify_file_received(self, sender, filename):
        """Уведомление о полученном файле"""
        if not self.enabled:
            return
        
        title = f"📎 Файл от {sender}"
        message = f"Получен файл: {filename}"
        
        self.show_notification(title, message, 'file', {'sender': sender, 'filename': filename})
    
    def notify_incoming_call(self, caller):
        """Уведомление о входящем звонке"""
        if not self.enabled:
            return
        
        title = f"📞 Входящий звонок"
        message = f"{caller} звонит вам"
        
        self.show_notification(title, message, 'call', {'caller': caller})
    
    def notify_error(self, error_message):
        """Уведомление об ошибке"""
        title = "❌ Ошибка"
        message = error_message[:150]  # Обрезаем длинные сообщения
        
        self.show_notification(title, message, 'error')


# Глобальный экземпляр
_notification_manager_instance = None

def get_notification_manager() -> NotificationManager:
    """Получение глобального экземпляра NotificationManager"""
    global _notification_manager_instance
    if _notification_manager_instance is None:
        _notification_manager_instance = NotificationManager()
    return _notification_manager_instance


# Тестирование
if __name__ == "__main__":
    print("🧪 Тестирование системы уведомлений...")
    
    # Создаем менеджер
    manager = get_notification_manager()
    
    print(f"Поддерживается: {manager.supported}")
    print(f"Включено: {manager.enabled}")
    print(f"Звук включен: {manager.sound_enabled}")
    
    # Тестовые уведомления
    print("\n📨 Тест уведомлений...")
    
    manager.notify_new_message("Иван Петров", "Привет! Как дела?")
    
    import time
    time.sleep(2)
    
    manager.notify_file_received("Мария Сидорова", "отчет_2024.pdf")
    
    time.sleep(2)
    
    manager.notify_incoming_call("Алексей Иванов")
    
    time.sleep(2)
    
    manager.notify_error("Не удалось подключиться к серверу")
    
    print("\n✅ Тест завершен!")
    print(f"История уведомлений: {len(manager.notification_history)} записей")