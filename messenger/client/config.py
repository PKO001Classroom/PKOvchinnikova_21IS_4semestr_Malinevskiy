import json
import os

# Путь к файлу config.json в той же папке, что и этот скрипт
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# Значения по умолчанию
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            SERVER_HOST = data.get('server', {}).get('host', SERVER_HOST)
            SERVER_PORT = data.get('server', {}).get('port', SERVER_PORT)
    except Exception as e:
        print(f"Ошибка чтения конфига: {e}. Используем defaults.")

SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
