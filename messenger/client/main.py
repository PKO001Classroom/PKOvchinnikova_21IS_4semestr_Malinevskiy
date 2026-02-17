"""
Точка входа клиентской части Local Messenger.
Обновленная версия с поддержкой тем и уведомлений.
"""

import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer

# Добавляем путь к корневой директории
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорт модулей из новой структуры
try:
    from client.ui.login_dialog import LoginDialog
    from client.ui.main_window import MainWindow
    from client.auth_manager import get_auth_manager
    from client.server_manager import get_server_manager
    from client.utils.theme_manager import get_theme_manager, init_theme
    from client.utils.notifications import get_notification_manager
    from client.config import update_server_config, APP_NAME, APP_VERSION
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Проверьте структуру проекта и наличие необходимых модулей.")
    sys.exit(1)


class MessengerClient:
    """
    Основной класс клиента мессенджера.
    Управляет жизненным циклом приложения.
    """
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.auth_token = None
        self.current_user = None
        self.server_url = None
        self.server_data = None
        
        # Инициализация менеджеров
        self.auth_manager = get_auth_manager()
        self.server_manager = get_server_manager()
        self.theme_manager = get_theme_manager()
        self.notification_manager = get_notification_manager()
        
        # Настройка приложения
        self.app.setApplicationName(APP_NAME)
        self.app.setApplicationVersion(APP_VERSION)
        self.app.setOrganizationName("Local Messenger Team")
        
        # Применяем сохраненную тему
        init_theme()
        
    def run(self):
        """Запуск клиента"""
        print("=" * 50)
        print(f"{APP_NAME} Client v{APP_VERSION}")
        print("=" * 50)
        
        try:
            # Проверяем настройки уведомлений
            if self.auth_manager.get_setting('notifications', True):
                print("Уведомления включены")
            
            if self.auth_manager.get_setting('sound_notifications', True):
                print("Звуковые уведомления включены")
            
            print(f"Текущая тема: {self.theme_manager.current_theme}")
            
            # Автозапуск серверов
            self.auto_start_servers()
            
            # Показываем диалог авторизации
            login_dialog = LoginDialog()
            
            # Обработчик выбора сервера
            def on_server_selected(server_data):
                self.server_data = server_data
                self.auth_token = server_data.get('auth_token')
                self.current_user = server_data.get('user_data')
                
                # Обновляем конфигурацию сервера
                update_server_config(server_data['ip'], server_data['port'])
                self.server_url = f"http://{server_data['ip']}:{server_data['port']}"
                
                print(f"Подключено к серверу: {server_data['name']}")
                print(f"Адрес: {server_data['ip']}:{server_data['port']}")
                print(f"Пользователь: {self.current_user.get('username')}")
                print(f"Защита паролем: {'Да' if server_data.get('is_password_protected') else 'Нет'}")
                
                # Показываем уведомление об успешном подключении
                self.notification_manager.show_notification(
                    "Подключение успешно",
                    f"Вы подключены к серверу {server_data['name']}",
                    "message"
                )
                
            login_dialog.server_selected.connect(on_server_selected)
            
            if login_dialog.exec_():
                if self.auth_token and self.current_user and self.server_url:
                    # Показываем главное окно
                    main_window = MainWindow(self.auth_token, self.current_user, self.server_url)
                    main_window.show()
                    
                    # Настраиваем иконку в трее
                    minimize_to_tray = self.auth_manager.get_setting('minimize_to_tray', True)
                    if minimize_to_tray:
                        self.notification_manager.setup_tray_icon(main_window)
                    
                    # Сохраняем настройки
                    self.save_settings()
                    
                    return self.app.exec_()
                else:
                    QMessageBox.critical(None, "Ошибка", 
                                       "Не удалось получить данные для подключения")
                    return 1
            else:
                print("Выход из приложения")
                return 0
                
        except Exception as e:
            print(f"Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
            
            # Показываем уведомление об ошибке
            self.notification_manager.notify_error(f"Критическая ошибка: {str(e)}")
            
            QMessageBox.critical(None, "Критическая ошибка", 
                               f"Не удалось запустить приложение:\n{str(e)}")
            return 1
    
    def auto_start_servers(self):
        """Автозапуск серверов с флагом auto_start"""
        print("Проверка серверов для автозапуска...")
        
        try:
            servers = self.server_manager.get_server_list()
            auto_start_servers = [s for s in servers if s.get('auto_start', False)]
            
            if auto_start_servers:
                print(f"Найдено серверов для автозапуска: {len(auto_start_servers)}")
                
                for server in auto_start_servers:
                    server_name = server['name']
                    
                    # Проверяем, запущен ли уже сервер
                    if not self.server_manager.check_server_connection(server_name):
                        print(f"Запуск сервера: {server_name}")
                        
                        # Для автозапуска пропускаем серверы с паролями
                        if server.get('password_protected'):
                            print(f"Сервер {server_name} требует пароль - пропускаем")
                            continue
                        
                        success, message = self.server_manager.start_server(server_name)
                        if success:
                            print(f"✅ {message}")
                            
                            # Уведомление об автозапуске
                            self.notification_manager.show_notification(
                                "Автозапуск сервера",
                                f"Сервер {server_name} успешно запущен",
                                "message"
                            )
                        else:
                            print(f"❌ Ошибка: {message}")
                    else:
                        print(f"Сервер {server_name} уже запущен")
            else:
                print("Серверы для автозапуска не найдены")
                
        except Exception as e:
            print(f"Ошибка при автозапуске серверов: {e}")
    
    def save_settings(self):
        """Сохранение настроек приложения"""
        try:
            # Сохраняем последние настройки
            if self.server_data:
                self.auth_manager.save_last_server(self.server_data)
            
            print("Настройки сохранены")
            
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
    
    def cleanup(self):
        """Очистка ресурсов при завершении"""
        print("Очистка ресурсов...")
        # Здесь можно добавить закрытие всех соединений


def main():
    """Точка входа в приложение"""
    client = MessengerClient()
    
    try:
        exit_code = client.run()
        client.cleanup()
        return exit_code
    except KeyboardInterrupt:
        print("\n\nПриложение завершено пользователем")
        return 0
    except Exception as e:
        print(f"\n\nНеобработанное исключение: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())