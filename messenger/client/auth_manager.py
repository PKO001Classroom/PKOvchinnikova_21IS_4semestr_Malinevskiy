"""
Менеджер аутентификации и управления сессиями клиента.
"""

import json
import os
import hashlib
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

# Импорт модулей из новой структуры
try:
    from client.config import APP_DATA_DIR, APP_NAME
except ImportError as e:
    print(f"Ошибка импорта в auth_manager.py: {e}")

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Менеджер для управления аутентификацией, сессиями и настройками клиента.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Инициализация менеджера аутентификации.
        
        Args:
            config_dir: Директория для хранения данных клиента
        """
        if config_dir is None:
            config_dir = os.path.join(APP_DATA_DIR, "auth")
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_file = self.config_dir / "session.json"
        self.settings_file = self.config_dir / "settings.json"
        
        self.current_session: Optional[Dict] = None
        self.settings: Dict = {}
        
        self._load_settings()
        self._load_session()
        
        logger.info(f"AuthManager инициализирован. Директория: {self.config_dir}")
    
    def _load_settings(self):
        """Загрузка настроек клиента"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                logger.debug("Настройки загружены")
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")
            self.settings = {
                "auto_login": False,
                "remember_me": False,
                "last_server": None,
                "theme": "light",
                "notifications": True,
                "sound_notifications": True,
                "tray_notifications": True,
                "notify_messages": True,
                "notify_files": True,
                "notify_calls": True,
                "notify_errors": True,
                "notification_duration": 5,
                "auto_start": False,
                "minimize_to_tray": True,
                "message_limit": 1000,
                "show_timestamps": True,
                "max_file_size": 10,
                "auto_save_files": False,
                "font_size": "medium",
                "font_smoothing": True,
                "animations": True,
                "connection_timeout": 10,
                "reconnect_attempts": 3,
                "use_proxy": False,
                "proxy_address": "",
                "proxy_username": "",
                "proxy_password": "",
                "use_broadcast": True,
                "auto_discovery": True,
                "language": "ru"
            }
    
    def _load_session(self):
        """Загрузка сессии из файла"""
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    
                    # Проверяем срок действия сессии
                    expires_at = session_data.get('expires_at', 0)
                    if datetime.now().timestamp() < expires_at:
                        self.current_session = session_data
                        logger.debug("Сессия загружена из файла")
                    else:
                        logger.debug("Сессия истекла")
                        self._clear_session()
                        
        except Exception as e:
            logger.error(f"Ошибка загрузки сессии: {e}")
            self.current_session = None
    
    def save_settings(self):
        """Сохранение настроек"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            logger.debug("Настройки сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")
    
    def create_session(self, auth_token: str, user_data: Dict, remember_me: bool = False):
        """
        Создание новой сессии.
        
        Args:
            auth_token: Токен аутентификации
            user_data: Данные пользователя
            remember_me: Сохранять ли сессию
        """
        # Рассчитываем время истечения сессии
        expires_at = datetime.now().timestamp() + (30 * 24 * 3600 if remember_me else 24 * 3600)
        
        self.current_session = {
            'auth_token': auth_token,
            'user_data': user_data,
            'created_at': datetime.now().timestamp(),
            'expires_at': expires_at,
            'remember_me': remember_me
        }
        
        # Сохраняем сессию если remember_me=True
        if remember_me:
            self._save_session()
        
        # Обновляем настройки
        self.settings['remember_me'] = remember_me
        
        logger.info(f"Создана сессия для пользователя {user_data.get('username')}")
    
    def _save_session(self):
        """Сохранение сессии в файл"""
        if not self.current_session:
            return
            
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_session, f, indent=2, ensure_ascii=False)
            logger.debug("Сессия сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения сессии: {e}")
    
    def _clear_session(self):
        """Очистка сессии"""
        try:
            if self.session_file.exists():
                os.remove(self.session_file)
        except Exception as e:
            logger.error(f"Ошибка удаления файла сессии: {e}")
        
        self.current_session = None
        logger.debug("Сессия очищена")
    
    def logout(self):
        """Выход из системы"""
        self._clear_session()
        
        # Сбрасываем некоторые настройки
        self.settings['auto_login'] = False
        
        logger.info("Пользователь вышел из системы")
    
    def get_auth_token(self) -> Optional[str]:
        """Получение токена аутентификации"""
        if self.current_session:
            return self.current_session.get('auth_token')
        return None
    
    def get_user_data(self) -> Optional[Dict]:
        """Получение данных пользователя"""
        if self.current_session:
            return self.current_session.get('user_data')
        return None
    
    def is_session_valid(self) -> bool:
        """Проверка валидности сессии"""
        if not self.current_session:
            return False
        
        expires_at = self.current_session.get('expires_at', 0)
        return datetime.now().timestamp() < expires_at
    
    def set_setting(self, key: str, value: Any):
        """Установка настройки"""
        self.settings[key] = value
        self.save_settings()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Получение настройки"""
        return self.settings.get(key, default)
    
    def save_last_server(self, server_data: Dict):
        """Сохранение последнего сервера"""
        # Сохраняем только необходимые данные
        server_info = {
            'name': server_data.get('name'),
            'ip': server_data.get('ip'),
            'port': server_data.get('port'),
            'description': server_data.get('description'),
            'is_password_protected': server_data.get('is_password_protected', False)
        }
        
        self.set_setting("last_server", server_info)
        logger.debug(f"Сохранен последний сервер: {server_info.get('name')}")
    
    def get_last_server(self) -> Optional[Dict]:
        """Получение последнего сервера"""
        return self.get_setting("last_server")
    
    def hash_password(self, password: str) -> str:
        """Хэширование пароля"""
        # Используем соль для дополнительной безопасности
        salt = "local_messenger_salt_2024"
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def verify_password_hash(self, password: str, password_hash: str) -> bool:
        """Проверка хэша пароля"""
        return self.hash_password(password) == password_hash
    
    def get_session_info(self) -> Dict:
        """Получение информации о сессии"""
        if not self.current_session:
            return {"has_session": False}
        
        expires_at = self.current_session.get('expires_at', 0)
        expires_dt = datetime.fromtimestamp(expires_at)
        time_left = expires_dt - datetime.now()
        
        return {
            "has_session": True,
            "username": self.current_session.get('user_data', {}).get('username'),
            "created_at": datetime.fromtimestamp(self.current_session.get('created_at', 0)),
            "expires_at": expires_dt,
            "time_left": str(time_left),
            "remember_me": self.current_session.get('remember_me', False)
        }
    
    def clear_all_data(self):
        """Очистка всех данных пользователя"""
        try:
            # Удаляем все файлы в директории
            for file in self.config_dir.glob("*"):
                try:
                    if file.is_file():
                        file.unlink()
                except:
                    pass
            
            # Сбрасываем все настройки
            self.current_session = None
            self.settings = {
                "auto_login": False,
                "remember_me": False,
                "last_server": None,
                "theme": "light",
                "notifications": True,
                "sound_notifications": True,
                "auto_start": False,
                "minimize_to_tray": True
            }
            
            logger.info("Все данные пользователя очищены")
            
        except Exception as e:
            logger.error(f"Ошибка очистки данных: {e}")


# Глобальный экземпляр
_auth_manager_instance: Optional[AuthManager] = None

def get_auth_manager() -> AuthManager:
    """Получение глобального экземпляра AuthManager"""
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance


def clear_auth_manager():
    """Очистка глобального экземпляра AuthManager"""
    global _auth_manager_instance
    _auth_manager_instance = None