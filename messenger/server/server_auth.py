"""
Аутентификация запуска сервера.
Проверка пароля при запуске сервера.
"""

import hashlib
import sys
import getpass
from typing import Optional, Tuple
from server.server_config import get_server_config


class ServerAuth:
    """
    Класс для аутентификации запуска сервера.
    Проверяет пароль при запуске защищенного сервера.
    """
    
    def __init__(self, config_path: str = "server_config.json"):
        """
        Инициализация аутентификации.
        
        Args:
            config_path: Путь к файлу конфигурации сервера
        """
        self.server_config = get_server_config(config_path)
    
    def require_password_check(self) -> bool:
        """
        Проверяет, требуется ли запрос пароля.
        
        Returns:
            True если сервер защищен паролем
        """
        return self.server_config.require_password()
    
    def verify_startup_password(self, password: Optional[str] = None) -> Tuple[bool, str]:
        """
        Проверка пароля для запуска сервера.
        
        Args:
            password: Пароль для проверки (если None, запрашивается у пользователя)
            
        Returns:
            (успех, сообщение)
        """
        if not self.server_config.is_protected():
            return True, "Сервер не защищен паролем"
        
        try:
            if password is None:
                # Запрашиваем пароль у пользователя
                print("\n🔐 Сервер защищен паролем")
                password = getpass.getpass("Введите пароль для запуска сервера: ")
            
            if not password:
                return False, "Пароль не может быть пустым"
            
            # Проверяем пароль
            if self.server_config.verify_password(password):
                return True, "Пароль верный"
            else:
                return False, "Неверный пароль"
                
        except KeyboardInterrupt:
            print("\n🚪 Запуск сервера отменен")
            sys.exit(0)
        except Exception as e:
            return False, f"Ошибка проверки пароля: {str(e)}"
    
    def prompt_for_password(self) -> Optional[str]:
        """
        Запрос пароля у пользователя.
        
        Returns:
            Введенный пароль или None если отменено
        """
        try:
            print("\n🔐 Для запуска сервера требуется пароль")
            print("Этот сервер был создан другим пользователем и защищен паролем.")
            print("Для запуска сервера необходимо знать пароль.")
            
            password = getpass.getpass("\nВведите пароль для запуска сервера: ")
            
            if not password:
                print("❌ Пароль не может быть пустым")
                return None
            
            return password
            
        except KeyboardInterrupt:
            print("\n🚪 Ввод пароля отменен")
            return None
        except Exception as e:
            print(f"❌ Ошибка ввода пароля: {e}")
            return None
    
    def check_and_start_server(self, start_server_func, *args, **kwargs) -> bool:
        """
        Проверка пароля и запуск сервера.
        
        Args:
            start_server_func: Функция запуска сервера
            *args, **kwargs: Аргументы для функции запуска
            
        Returns:
            True если сервер запущен успешно
        """
        if not self.require_password_check():
            # Сервер не защищен паролем, запускаем сразу
            return start_server_func(*args, **kwargs)
        
        # Сервер защищен паролем
        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"\n🔐 Попытка {attempt + 1} из {max_attempts}")
            
            password = self.prompt_for_password()
            if password is None:
                continue
            
            success, message = self.verify_startup_password(password)
            print(f"  {message}")
            
            if success:
                print("✅ Пароль верный, запуск сервера...")
                return start_server_func(*args, **kwargs)
            else:
                print(f"❌ Неверный пароль")
                
                if attempt < max_attempts - 1:
                    print("Попробуйте еще раз")
                else:
                    print(f"🚪 Превышено максимальное количество попыток ({max_attempts})")
                    return False
        
        return False
    
    def can_user_start_server(self, username: str, provided_password: Optional[str] = None) -> Tuple[bool, str]:
        """
        Проверка, может ли пользователь запустить сервер.
        Вызывается из внешних программ.
        
        Args:
            username: Имя пользователя (для логирования)
            provided_password: Пароль (если None, будет запрошен)
            
        Returns:
            (может_запустить, сообщение)
        """
        if not self.server_config.is_protected():
            return True, f"Пользователь {username} может запустить сервер (без пароля)"
        
        success, message = self.verify_startup_password(provided_password)
        
        if success:
            return True, f"Пользователь {username} может запустить сервер (пароль верный)"
        else:
            return False, f"Пользователь {username} не может запустить сервер: {message}"
    
    def get_security_info(self) -> dict:
        """Получение информации о защите сервера"""
        return {
            "password_protected": self.server_config.is_protected(),
            "requires_password_for_startup": self.server_config.require_password(),
            "can_start_without_password": not self.server_config.is_protected()
        }


# Глобальный экземпляр
_server_auth_instance: Optional[ServerAuth] = None

def get_server_auth(config_path: str = "server_config.json") -> ServerAuth:
    """Получение глобального экземпляра аутентификации"""
    global _server_auth_instance
    if _server_auth_instance is None:
        _server_auth_instance = ServerAuth(config_path)
    return _server_auth_instance


def require_password_prompt(config_path: str = "server_config.json") -> bool:
    """
    Запрос пароля если требуется.
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        True если пароль верный или не требуется
    """
    auth = get_server_auth(config_path)
    
    if not auth.require_password_check():
        return True
    
    success, message = auth.verify_startup_password()
    
    if not success:
        print(f"❌ {message}")
        return False
    
    print(f"✅ {message}")
    return True