"""
Конфигурация клиента Local Messenger.
Динамические настройки, которые обновляются при выборе сервера.
"""

import socket
import os
from pathlib import Path

def get_local_ip():
    """Получение локального IP адреса"""
    try:
        # Способ 1: Через временное соединение (наиболее надежный)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('10.255.255.255', 1))  # Несуществующий адрес
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        try:
            # Способ 2: Альтернативный метод
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            # Способ 3: Через hostname
            try:
                return socket.gethostbyname(socket.gethostname())
            except:
                return "127.0.0.1"


# ===================== СЕТЕВЫЕ НАСТРОЙКИ =====================
# Динамическое определение IP
LOCAL_IP = get_local_ip()

# Конфигурация по умолчанию (будет переопределяться при выборе сервера)
SERVER_HOST = LOCAL_IP  # По умолчанию локальный IP
SERVER_PORT = 8000      # Порт по умолчанию
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# WebSocket настройки (автоматически определяются на основе SERVER_HOST/SERVER_PORT)
def get_websocket_url():
    """Получение URL для WebSocket соединения"""
    return f"ws://{SERVER_HOST}:{SERVER_PORT}/ws"

WEBSOCKET_URL = get_websocket_url()

# Broadcast настройки
BROADCAST_PORT = 37020
BROADCAST_ADDRESS = '255.255.255.255'  # Более надежно чем '<broadcast>'
BROADCAST_TIMEOUT = 3.0  # секунды
BROADCAST_BUFFER_SIZE = 1024


# ===================== ПУТИ И ДИРЕКТОРИИ =====================
def get_app_data_dir():
    """Получение директории для данных приложения"""
    # Для Windows: %APPDATA%/Local Messenger
    # Для Linux/Mac: ~/.local/share/local-messenger
    if os.name == 'nt':  # Windows
        base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
        app_dir = Path(base_dir) / "Local Messenger"
    else:  # Linux/Mac
        base_dir = os.path.expanduser('~')
        app_dir = Path(base_dir) / ".local" / "share" / "local-messenger"
    
    # Создаем директорию если не существует
    app_dir.mkdir(parents=True, exist_ok=True)
    return str(app_dir)

# Основные директории
APP_DATA_DIR = get_app_data_dir()
CONFIG_DIR = os.path.join(APP_DATA_DIR, "config")
SERVERS_DIR = os.path.join(APP_DATA_DIR, "servers")
LOGS_DIR = os.path.join(APP_DATA_DIR, "logs")

# Создаем необходимые директории
for directory in [CONFIG_DIR, SERVERS_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)


# ===================== НАСТРОЙКИ ПРИЛОЖЕНИЯ =====================
APP_NAME = "Local Messenger"
APP_VERSION = "1.1.0"
ORGANIZATION_NAME = "Local Messenger Team"

# Настройки UI
UI_THEME = "light"  # light, dark, blue, midnight
UI_LANGUAGE = "ru"    # ru, en

# Настройки подключения
CONNECTION_TIMEOUT = 10  # секунды
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 5  # секунды между попытками переподключения

# Настройки сообщений
MESSAGE_HISTORY_LIMIT = 1000
AUTO_LOAD_MESSAGES = True
SHOW_MESSAGE_TIMESTAMPS = True
MAX_FILE_SIZE_MB = 10  # Максимальный размер файла для отправки


# ===================== ФУНКЦИИ ДЛЯ ОБНОВЛЕНИЯ =====================
def update_server_config(host: str, port: int):
    """
    Обновление конфигурации сервера.
    Вызывается при выборе сервера.
    
    Args:
        host: IP адрес сервера
        port: Порт сервера
    """
    global SERVER_HOST, SERVER_PORT, SERVER_URL, WEBSOCKET_URL
    
    SERVER_HOST = host
    SERVER_PORT = port
    SERVER_URL = f"http://{host}:{port}"
    WEBSOCKET_URL = f"ws://{host}:{port}/ws"
    
    print(f"🔧 Конфигурация обновлена: {SERVER_URL}")
    print(f"🔧 WebSocket URL: {WEBSOCKET_URL}")


def reset_to_default():
    """Сброс конфигурации к значениям по умолчанию"""
    update_server_config(LOCAL_IP, 8000)


def get_config_summary() -> dict:
    """Получение сводки текущей конфигурации"""
    return {
        "app": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "data_dir": APP_DATA_DIR
        },
        "server": {
            "host": SERVER_HOST,
            "port": SERVER_PORT,
            "url": SERVER_URL,
            "websocket_url": WEBSOCKET_URL
        },
        "network": {
            "local_ip": LOCAL_IP,
            "broadcast_port": BROADCAST_PORT,
            "broadcast_address": BROADCAST_ADDRESS
        },
        "directories": {
            "config": CONFIG_DIR,
            "servers": SERVERS_DIR,
            "logs": LOGS_DIR
        }
    }