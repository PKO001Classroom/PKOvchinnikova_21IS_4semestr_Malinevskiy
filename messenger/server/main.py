"""
Точка входа серверной части Local Messenger.
Поддержка парольной защиты при запуске.
"""

import argparse
import sys
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

# Добавляем путь к корневой директории
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорт модулей сервера
try:
    from server.database.db import init_db
    from server.routers import auth, messages, users, admin
    from server.websocket_manager import manager
    from server.database.user_model import UserModel
    from server.server_config import init_server_config_from_args, get_server_config
    from server.server_auth import get_server_auth, require_password_prompt
    from server.broadcast_server import init_broadcast_server, get_broadcast_server
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Проверьте структуру проекта и наличие необходимых модулей.")
    sys.exit(1)


async def check_inactive_users_periodically():
    """Периодическая проверка неактивных пользователей"""
    while True:
        try:
            inactive_users = UserModel.check_inactive_users(timeout_minutes=5)
            if inactive_users:
                print(f"Пользователи отмечены как оффлайн из-за неактивности: {inactive_users}")
        except Exception as e:
            print(f"Ошибка проверки неактивных пользователей: {e}")
        
        await asyncio.sleep(60)  # Проверка каждую минуту


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления жизненным циклом приложения.
    """
    print("Инициализация сервера...")
    
    # Инициализация базы данных
    init_db()
    print("База данных инициализирована")
    
    # Получаем конфигурацию
    config = get_server_config()
    server_info = config.get_server_info()
    
    # Инициализация broadcast сервера
    broadcast_server = init_broadcast_server(
        server_name=config.config["server_name"],
        server_port=config.config["port"],
        broadcast_port=config.config["broadcast_port"],
        description=config.config["description"],
        max_users=config.config["max_users"],
        password_required=config.config["password_protected"]
    )
    
    # Запускаем broadcast сервер
    if broadcast_server.start():
        print(f"Broadcast сервер запущен на порту {config.config['broadcast_port']}")
    else:
        print("Не удалось запустить broadcast сервер")
    
    # Запускаем фоновую задачу для проверки неактивных пользователей
    task = asyncio.create_task(check_inactive_users_periodically())
    
    print(f"\n{'='*50}")
    print(f"Сервер {server_info['name']} запущен!")
    print(f"Адрес: http://{server_info['host']}:{server_info['port']}")
    print(f"Пользователей онлайн: {server_info['users_count']}")
    print(f"Защита паролем: {'Да' if config.is_protected() else 'Нет'}")
    print(f"{'='*50}\n")
    
    yield
    
    # Останавливаем задачу при остановке приложения
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    # Останавливаем broadcast сервер
    broadcast_server = get_broadcast_server()
    if broadcast_server:
        broadcast_server.stop()
        print("Broadcast сервер остановлен")
    
    print("\nСервер остановлен")


def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения"""
    
    # Получаем конфигурацию
    config = get_server_config()
    
    app = FastAPI(
        title=f"Local Messenger API - {config.config['server_name']}",
        description=config.config["description"],
        version=config.config["version"],
        lifespan=lifespan
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В продакшене нужно ограничить
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(messages.router, prefix="/messages", tags=["messages"])
    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    
    @app.get("/")
    async def root():
        """Корневой эндпоинт с информацией о сервере"""
        config = get_server_config()
        return {
            "app": "Local Messenger Server",
            "version": config.config["version"],
            "server_name": config.config["server_name"],
            "description": config.config["description"],
            "host": config.get_server_host(),
            "port": config.config["port"],
            "max_users": config.config["max_users"],
            "password_protected": config.config["password_protected"],
            "online_users": config.get_online_users_count(),
            "endpoints": {
                "auth": "/auth",
                "messages": "/messages",
                "users": "/users",
                "admin": "/admin",
                "websocket": "/ws/{user_id}"
            }
        }
    
    @app.websocket("/ws/{user_id}")
    async def websocket_endpoint(websocket: WebSocket, user_id: int):
        """WebSocket endpoint для real-time общения"""
        await manager.connect(websocket, user_id)
        try:
            while True:
                try:
                    # Ожидаем сообщения
                    data = await websocket.receive_text()
                    
                    # Обрабатываем ping/pong
                    if data == 'ping':
                        await websocket.send_text('pong')
                    elif data == 'pong':
                        continue
                    else:
                        # Можно добавить обработку других сообщений
                        try:
                            message = json.loads(data)
                            # Здесь можно добавить логику обработки сообщений
                            pass
                        except json.JSONDecodeError:
                            pass
                            
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"WebSocket error: {e}")
                    break
                    
        except Exception as e:
            print(f"WebSocket endpoint error: {e}")
        finally:
            # Всегда вызываем disconnect
            try:
                manager.disconnect(websocket, user_id)
            except:
                pass
    
    return app


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description="Local Messenger Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s                         # Запуск с настройками по умолчанию
  %(prog)s --name "Мой сервер"     # Запуск с именем
  %(prog)s --host 192.168.1.100    # Запуск на конкретном IP
  %(prog)s --port 8888             # Запуск на другом порту
  %(prog)s --password-protected    # Защитить сервер паролем
  %(prog)s --max-users 100         # Максимум 100 пользователей
        """
    )
    
    # Основные параметры
    parser.add_argument(
        "--name",
        type=str,
        help="Имя сервера (по умолчанию: 'Local Messenger Server')"
    )
    
    parser.add_argument(
        "--description",
        type=str,
        help="Описание сервера"
    )
    
    # Сетевые параметры
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="IP адрес для привязки (по умолчанию: 0.0.0.0 - все интерфейсы)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Порт сервера (по умолчанию: 8000)"
    )
    
    parser.add_argument(
        "--broadcast-port",
        type=int,
        default=37020,
        help="Порт для broadcast (по умолчанию: 37020)"
    )
    
    # Параметры безопасности
    parser.add_argument(
        "--password-protected",
        action="store_true",
        help="Защитить сервер паролем (потребуется при создании)"
    )
    
    parser.add_argument(
        "--password",
        type=str,
        help="Пароль для сервера (не рекомендуется использовать в командной строке)"
    )
    
    # Параметры ограничений
    parser.add_argument(
        "--max-users",
        type=int,
        default=50,
        help="Максимальное количество пользователей (по умолчанию: 50)"
    )
    
    # Дополнительные параметры
    parser.add_argument(
        "--config",
        type=str,
        help="Путь к файлу конфигурации"
    )
    
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Автозапуск сервера при запуске клиента"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Local Messenger Server 1.0"
    )
    
    return parser.parse_args()


def main():
    """Основная функция запуска сервера"""
    print("Local Messenger Server")
    print("=" * 50)
    
    # Парсим аргументы
    args = parse_arguments()
    
    # Инициализируем конфигурацию из аргументов
    config_path = args.config if args.config else "server_config.json"
    server_config = init_server_config_from_args(args)
    
    # Если сервер защищен паролем, проверяем/устанавливаем пароль
    if args.password_protected and not server_config.is_protected():
        print("\nНастройка парольной защиты сервера...")
        
        if args.password:
            # Используем пароль из аргументов
            server_config.set_password(args.password)
            print("Пароль установлен из аргументов командной строки")
        else:
            # Запрашиваем пароль у пользователя
            import getpass
            try:
                password = getpass.getpass("Введите пароль для сервера: ")
                confirm = getpass.getpass("Подтвердите пароль: ")
                
                if password != confirm:
                    print("Пароли не совпадают")
                    return 1
                
                if not password:
                    print("Пароль не может быть пустым")
                    return 1
                
                server_config.set_password(password)
                server_config.save_config()
                print("Пароль установлен")
                
            except KeyboardInterrupt:
                print("\nОтмена запуска сервера")
                return 0
    
    # Проверяем пароль если сервер защищен
    auth = get_server_auth(config_path)
    if not auth.check_and_start_server(lambda: True):
        print("Не удалось пройти аутентификацию")
        return 1
    
    # Создаем и запускаем приложение
    app = create_app()
    
    # Получаем параметры запуска из конфигурации
    host = server_config.config["host"]
    port = server_config.config["port"]
    
    print(f"\nЗапуск сервера на {host}:{port}")
    print("Ожидание подключений...")
    print("Нажмите Ctrl+C для остановки\n")
    
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\nОстановка сервера...")
        return 0
    except Exception as e:
        print(f"\nОшибка запуска сервера: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())