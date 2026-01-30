# API Документация
## Локальный мессенджер для образовательных учреждений

**Версия документа:** 1.0  
**Дата:** 2026  
**Автор:** Малиневский Егор Сергеевич/21ИС-24  
**Базовый URL:** `http://localhost:8000` или `http://<server_ip>:8000`

---

## Оглавление

1. [Введение](#введение)
2. [Базовые концепции](#базовые-концепции)
3. [Аутентификация](#аутентификация)
4. [Endpoints: Аутентификация](#endpoints-аутентификация)
5. [Endpoints: Пользователи](#endpoints-пользователи)
6. [Endpoints: Сообщения](#endpoints-сообщения)
7. [Endpoints: Администрирование](#endpoints-администрирование)
8. [Endpoints: WebSocket](#endpoints-websocket)
9. [Модели данных](#модели-данных)
10. [Коды ошибок](#коды-ошибок)
11. [Примеры использования](#примеры-использования)
12. [Postman коллекция](#postman-коллекция)

---

<a name="введение"></a>
## 1. Введение

### 1.1. Назначение документа

Данный документ описывает REST API и WebSocket интерфейсы системы "Локальный мессенджер". API используется для:

- Аутентификации и регистрации пользователей
- Обмена текстовыми и мультимедийными сообщениями
- Управления пользователями и их статусами
- Административных функций

### 1.2. Технологический стек

| Компонент | Технология | Версия |
|-----------|------------|---------|
| **Фреймворк** | FastAPI | 0.104.1 |
| **Документация** | OpenAPI 3.0 + Swagger UI | - |
| **Аутентификация** | JWT (JSON Web Tokens) | - |
| **База данных** | SQLite + SQLAlchemy | - |
| **WebSocket** | WebSockets (RFC 6455) | - |

### 1.3. Форматы данных

- **Запросы/Ответы:** JSON
- **Кодировка:** UTF-8
- **Тип контента:** `application/json`
- **Изображения:** Base64 в JSON

### 1.4. Автоматическая документация

API предоставляет автоматически генерируемую документацию:

| URL | Назначение | Доступ |
|-----|------------|--------|
| `/docs` | Интерактивная документация (Swagger UI) | Публичный |
| `/redoc` | Альтернативная документация (ReDoc) | Публичный |
| `/openapi.json` | OpenAPI спецификация | Публичный |

---

<a name="базовые-концепции"></a>
## 2. Базовые концепции

### 2.1. Структура запросов и ответов

#### Пример успешного ответа:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "username": "john_doe"
  },
  "message": "Операция выполнена успешно"
}
```

#### Пример ответа с ошибкой:
```json
{
  "success": false,
  "error": {
    "code": "AUTH_001",
    "message": "Неверные учетные данные",
    "details": "Неверный логин или пароль"
  },
  "timestamp": "2026-01-19T10:30:00Z"
}
```

### 2.2. Заголовки запросов

| Заголовок | Обязательный | Описание | Пример |
|-----------|--------------|----------|--------|
| `Content-Type` | Да | Тип контента | `application/json` |
| `Authorization` | Да* | Токен аутентификации | `Bearer eyJhbG...` |
| `Accept` | Нет | Ожидаемый тип ответа | `application/json` |
| `User-Agent` | Нет | Идентификатор клиента | `Messenger-Client/1.0` |

*Заголовок Authorization обязателен для защищенных endpoints.

### 2.3. Пагинация

Для endpoints, возвращающих списки, поддерживается пагинация:

**Параметры запроса:**
- `page` - номер страницы (по умолчанию: 1)
- `size` - количество элементов на странице (по умолчанию: 20, максимум: 100)

**Ответ с пагинацией:**
```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "size": 20,
    "total": 150,
    "pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

### 2.4. Сортировка

**Параметры запроса:**
- `sort_by` - поле для сортировки
- `sort_order` - направление сортировки (`asc` или `desc`)

---

<a name="аутентификация"></a>
## 3. Аутентификация

### 3.1. JWT Authentication

Система использует JWT (JSON Web Tokens) для аутентификации:

```
1. Клиент отправляет логин/пароль → /auth/login
2. Сервер проверяет учетные данные
3. Сервер возвращает access_token
4. Клиент использует token в заголовке Authorization
5. Сервер проверяет token на каждом защищенном запросе
```

### 3.2. Формат токена

**Access Token:**
- Тип: Bearer Token
- Алгоритм: HS256
- Время жизни: 30 минут
- Содержимое: user_id, username, role, exp

**Пример:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzQwMTIzNDU2fQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

### 3.3. Обновление токена

Токены автоматически обновляются при активности пользователя. Для получения нового токена:

1. Выполнить запрос к любому защищенному endpoint
2. Если токен истек, клиент должен перенаправить пользователя на `/auth/login`

### 3.4. Роли пользователей

| Роль | Права | Описание |
|------|-------|----------|
| **user** | Базовые | Обычный пользователь мессенджера |
| **admin** | Полные | Администратор системы (первый зарегистрированный) |

---

<a name="endpoints-аутентификация"></a>
## 4. Endpoints: Аутентификация

### 4.1. Регистрация нового пользователя

**POST** `/auth/register`

Регистрирует нового пользователя в системе. Первый зарегистрированный пользователь автоматически получает роль `admin`.

**Тело запроса:**
```json
{
  "username": "john_doe",
  "password": "SecurePass123!",
  "display_name": "John Doe"
}
```

**Параметры:**
| Параметр | Тип | Обязательный | Валидация | Описание |
|----------|-----|--------------|-----------|----------|
| `username` | string | Да | 3-50 chars, уникальный | Имя пользователя |
| `password` | string | Да | 8+ chars, буквы+цифры | Пароль |
| `display_name` | string | Нет | 1-100 chars | Отображаемое имя |

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "username": "john_doe",
    "display_name": "John Doe",
    "role": "admin",
    "created_at": "2026-01-19T10:30:00Z"
  },
  "message": "Регистрация успешна"
}
```

**Коды ответа:**
- `201 Created` - Регистрация успешна
- `400 Bad Request` - Неверные данные
- `409 Conflict` - Пользователь уже существует

### 4.2. Вход в систему

**POST** `/auth/login`

Аутентифицирует пользователя и возвращает JWT токен.

**Тело запроса:**
```json
{
  "username": "john_doe",
  "password": "SecurePass123!"
}
```

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "username": "john_doe",
      "display_name": "John Doe",
      "role": "admin"
    }
  },
  "message": "Вход выполнен успешно"
}
```

**Коды ответа:**
- `200 OK` - Вход успешен
- `401 Unauthorized` - Неверные учетные данные

### 4.3. Получение информации о текущем пользователе

**GET** `/auth/me`

Возвращает информацию о текущем аутентифицированном пользователе.

**Заголовки:**
```
Authorization: Bearer <token>
```

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "username": "john_doe",
    "display_name": "John Doe",
    "role": "admin",
    "created_at": "2026-01-19T10:30:00Z",
    "last_login": "2026-01-19T14:45:00Z",
    "is_online": true
  }
}
```

**Коды ответа:**
- `200 OK` - Успешно
- `401 Unauthorized` - Токен недействителен

### 4.4. Выход из системы

**POST** `/auth/logout`

Деактивирует текущий токен пользователя.

**Заголовки:**
```
Authorization: Bearer <token>
```

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Выход выполнен успешно"
}
```

---

<a name="endpoints-пользователи"></a>
## 5. Endpoints: Пользователи

### 5.1. Получение списка пользователей

**GET** `/users/`

Возвращает список всех пользователей с их онлайн-статусами.

**Заголовки:**
```
Authorization: Bearer <token>
```

**Параметры запроса:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `online_only` | boolean | false | Только онлайн пользователи |
| `search` | string | - | Поиск по username или display_name |
| `page` | integer | 1 | Номер страницы |
| `size` | integer | 50 | Количество пользователей на странице |

**Ответ (успех):**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "username": "john_doe",
      "display_name": "John Doe",
      "role": "admin",
      "is_online": true,
      "last_seen": "2026-01-19T14:45:00Z"
    },
    {
      "id": 2,
      "username": "jane_smith",
      "display_name": "Jane Smith",
      "role": "user",
      "is_online": false,
      "last_seen": "2026-01-19T13:20:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "size": 50,
    "total": 2,
    "pages": 1
  }
}
```

### 5.2. Получение информации о конкретном пользователе

**GET** `/users/{user_id}`

Возвращает информацию о пользователе по ID.

**Параметры пути:**
- `user_id` - ID пользователя (integer)

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "id": 2,
    "username": "jane_smith",
    "display_name": "Jane Smith",
    "role": "user",
    "is_online": false,
    "last_seen": "2026-01-19T13:20:00Z",
    "created_at": "2026-01-18T09:15:00Z"
  }
}
```

**Коды ответа:**
- `200 OK` - Успешно
- `404 Not Found` - Пользователь не найден

### 5.3. Обновление профиля пользователя

**PUT** `/users/{user_id}`

Обновляет информацию профиля пользователя. Пользователь может обновлять только свой профиль.

**Тело запроса:**
```json
{
  "display_name": "John Doe Updated",
  "password": "NewSecurePass123!"  // опционально
}
```

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "username": "john_doe",
    "display_name": "John Doe Updated",
    "role": "admin"
  },
  "message": "Профиль обновлен"
}
```

**Коды ответа:**
- `200 OK` - Успешно
- `403 Forbidden` - Попытка обновить чужой профиль
- `404 Not Found` - Пользователь не найден

---

<a name="endpoints-сообщения"></a>
## 6. Endpoints: Сообщения

### 6.1. Отправка сообщения

**POST** `/messages/`

Отправляет сообщение другому пользователю.

**Тело запроса:**
```json
{
  "receiver_id": 2,
  "content": "Привет, как дела?",
  "message_type": "text"  // или "image"
}
```

**Для отправки изображения:**
```json
{
  "receiver_id": 2,
  "content": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "message_type": "image",
  "file_name": "screenshot.png",
  "file_size": 1024
}
```

**Параметры:**
| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `receiver_id` | integer | Да | ID получателя |
| `content` | string | Да | Текст или base64 изображения |
| `message_type` | string | Да | `text` или `image` |
| `file_name` | string | Нет* | Имя файла (только для image) |
| `file_size` | integer | Нет* | Размер файла в байтах (только для image) |

*Обязательно для сообщений типа `image`

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "sender_id": 1,
    "receiver_id": 2,
    "content": "Привет, как дела?",
    "message_type": "text",
    "timestamp": "2026-01-19T15:30:00Z",
    "is_read": false
  },
  "message": "Сообщение отправлено"
}
```

### 6.2. Получение истории сообщений

**GET** `/messages/conversation/{user_id}`

Возвращает историю переписки с указанным пользователем.

**Параметры пути:**
- `user_id` - ID собеседника

**Параметры запроса:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `limit` | integer | 100 | Количество сообщений |
| `before` | datetime | now | Получить сообщения до указанной даты |
| `after` | datetime | - | Получить сообщения после указанной даты |

**Ответ (успех):**
```json
{
  "success": true,
  "data": [
    {
      "id": 120,
      "sender_id": 2,
      "receiver_id": 1,
      "content": "Привет!",
      "message_type": "text",
      "timestamp": "2026-01-19T15:25:00Z",
      "is_read": true
    },
    {
      "id": 123,
      "sender_id": 1,
      "receiver_id": 2,
      "content": "Как дела?",
      "message_type": "text",
      "timestamp": "2026-01-19T15:30:00Z",
      "is_read": false
    }
  ]
}
```

### 6.3. Удаление сообщения

**DELETE** `/messages/{message_id}`

Удаляет сообщение по ID. Пользователь может удалять только свои сообщения.

**Параметры пути:**
- `message_id` - ID сообщения

**Ответ (успех):**
```json
{
  "success": true,
  "message": "Сообщение удалено"
}
```

**Коды ответа:**
- `200 OK` - Успешно
- `403 Forbidden` - Попытка удалить чужое сообщение
- `404 Not Found` - Сообщение не найдено

### 6.4. Отметка сообщений как прочитанных

**POST** `/messages/mark-read`

Отмечает сообщения от указанного пользователя как прочитанные.

**Тело запроса:**
```json
{
  "sender_id": 2
}
```

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "marked_count": 5
  },
  "message": "Сообщения отмечены как прочитанные"
}
```

---

<a name="endpoints-администрирование"></a>
## 7. Endpoints: Администрирование

*Требуют роли `admin`*

### 7.1. Получение списка всех пользователей (расширенный)

**GET** `/admin/users`

Возвращает полную информацию обо всех пользователях.

**Параметры запроса:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `include_inactive` | boolean | false | Включая неактивных |
| `sort_by` | string | created_at | Поле для сортировки |
| `sort_order` | string | desc | Направление сортировки |

**Ответ (успех):**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "username": "admin",
      "display_name": "Администратор",
      "role": "admin",
      "is_online": true,
      "last_login": "2026-01-19T14:45:00Z",
      "created_at": "2026-01-15T09:00:00Z",
      "message_count": 150,
      "is_active": true
    }
  ]
}
```

### 7.2. Получение всех сообщений

**GET** `/admin/messages`

Возвращает все сообщения в системе.

**Параметры запроса:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `user_id` | integer | - | Фильтр по отправителю/получателю |
| `type` | string | - | Фильтр по типу сообщения |
| `date_from` | datetime | - | Сообщения с даты |
| `date_to` | datetime | - | Сообщения до даты |

**Ответ (успех):**
```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "sender": {
        "id": 1,
        "username": "john_doe"
      },
      "receiver": {
        "id": 2,
        "username": "jane_smith"
      },
      "content_preview": "Привет, как дела?",
      "message_type": "text",
      "timestamp": "2026-01-19T15:30:00Z",
      "is_read": false
    }
  ],
  "pagination": {
    "page": 1,
    "size": 50,
    "total": 1234,
    "pages": 25
  }
}
```

### 7.3. Статистика системы

**GET** `/admin/stats`

Возвращает статистику использования системы.

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "users": {
      "total": 42,
      "online": 12,
      "admins": 1,
      "new_today": 3
    },
    "messages": {
      "total": 12345,
      "today": 156,
      "text": 12000,
      "images": 345
    },
    "system": {
      "uptime": "5d 3h 15m",
      "disk_usage_mb": 245.7,
      "active_connections": 12
    }
  }
}
```

### 7.4. Экспорт данных

**GET** `/admin/export/{data_type}`

Экспортирует данные в формате JSON или CSV.

**Параметры пути:**
- `data_type` - Тип данных (`users`, `messages`, `all`)

**Параметры запроса:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `format` | string | json | Формат экспорта (`json` или `csv`) |
| `date_from` | datetime | - | Данные с даты |
| `date_to` | datetime | - | Данные до даты |

**Заголовки ответа (для CSV):**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="users_export_20260119.csv"
```

---

<a name="endpoints-websocket"></a>
## 8. Endpoints: WebSocket

### 8.1. Подключение к WebSocket

**WebSocket** `/ws/{user_id}`

Устанавливает WebSocket соединение для real-time обновлений.

**Параметры пути:**
- `user_id` - ID пользователя

**Заголовки:**
```
Authorization: Bearer <token>
```

**Протокол:**
1. Клиент подключается к `/ws/{user_id}`
2. Сервер отправляет `connection_ack` с `connection_id`
3. Клиент периодически отправляет `ping` (каждые 25 секунд)
4. Сервер отправляет события в реальном времени

### 8.2. События WebSocket

#### 8.2.1. От сервера к клиенту:

**Новое сообщение:**
```json
{
  "event": "new_message",
  "data": {
    "id": 123,
    "sender_id": 2,
    "content": "Привет!",
    "message_type": "text",
    "timestamp": "2026-01-19T15:30:00Z"
  }
}
```

**Обновление статуса пользователя:**
```json
{
  "event": "user_status",
  "data": {
    "user_id": 2,
    "is_online": true,
    "last_seen": "2026-01-19T15:31:00Z"
  }
}
```

**Удаление сообщения:**
```json
{
  "event": "message_deleted",
  "data": {
    "message_id": 123,
    "deleted_by": 2
  }
}
```

**Пинг (keep-alive):**
```json
{
  "event": "ping",
  "timestamp": "2026-01-19T15:32:00Z"
}
```

#### 8.2.2. От клиента к серверу:

**Понг (ответ на пинг):**
```json
{
  "event": "pong",
  "timestamp": "2026-01-19T15:32:00Z"
}
```

**Типирование (typing indicator):**
```json
{
  "event": "typing",
  "data": {
    "receiver_id": 2,
    "is_typing": true
  }
}
```

### 8.3. Коды закрытия WebSocket

| Код | Причина | Действие клиента |
|-----|---------|-------------------|
| `1000` | Нормальное закрытие | - |
| `1001` | Сервер ушел | Попробовать переподключиться |
| `1006` | Аномальное закрытие | Переподключиться с задержкой |
| `4001` | Неавторизован | Получить новый токен |
| `4003` | Неверный user_id | Проверить параметры подключения |

---

<a name="модели-данных"></a>
## 9. Модели данных

### 9.1. Пользователь (User)

```json
{
  "id": "integer, уникальный идентификатор",
  "username": "string, уникальное имя пользователя",
  "display_name": "string, отображаемое имя",
  "password_hash": "string, хэш пароля (не возвращается в API)",
  "role": "string, роль (user или admin)",
  "is_online": "boolean, онлайн статус",
  "last_seen": "datetime, последняя активность",
  "last_login": "datetime, последний вход",
  "created_at": "datetime, дата регистрации",
  "is_active": "boolean, активен ли аккаунт"
}
```

### 9.2. Сообщение (Message)

```json
{
  "id": "integer, уникальный идентификатор",
  "sender_id": "integer, ID отправителя",
  "receiver_id": "integer, ID получателя",
  "content": "string, содержимое сообщения",
  "message_type": "string, тип (text или image)",
  "file_name": "string, имя файла (для изображений)",
  "file_size": "integer, размер файла в байтах",
  "timestamp": "datetime, время отправки",
  "is_read": "boolean, прочитано ли",
  "deleted_at": "datetime, время удаления (если удалено)"
}
```

### 9.3. Сессия (Session)

```json
{
  "id": "string, идентификатор сессии",
  "user_id": "integer, ID пользователя",
  "access_token": "string, JWT токен",
  "expires_at": "datetime, время истечения",
  "created_at": "datetime, время создания",
  "last_used": "datetime, последнее использование"
}
```

---

<a name="коды-ошибок"></a>
## 10. Коды ошибок

### 10.1. Общие ошибки

| Код | Сообщение | HTTP статус | Описание |
|-----|-----------|-------------|----------|
| `AUTH_001` | Неверные учетные данные | 401 | Неверный логин или пароль |
| `AUTH_002` | Токен истек | 401 | JWT токен просрочен |
| `AUTH_003` | Недействительный токен | 401 | Токен невалиден |
| `AUTH_004` | Доступ запрещен | 403 | Недостаточно прав |
| `VAL_001` | Неверные данные запроса | 400 | Ошибка валидации |

### 10.2. Ошибки пользователей

| Код | Сообщение | HTTP статус | Описание |
|-----|-----------|-------------|----------|
| `USER_001` | Пользователь не найден | 404 | Пользователь с таким ID не существует |
| `USER_002` | Имя пользователя занято | 409 | Пользователь с таким username уже существует |
| `USER_003` | Неверный формат пароля | 400 | Пароль не соответствует требованиям |

### 10.3. Ошибки сообщений

| Код | Сообщение | HTTP статус | Описание |
|-----|-----------|-------------|----------|
| `MSG_001` | Сообщение не найдено | 404 | Сообщение с таким ID не существует |
| `MSG_002` | Получатель не найден | 404 | Пользователь-получатель не существует |
| `MSG_003` | Невозможно удалить чужое сообщение | 403 | Попытка удалить сообщение другого пользователя |
| `MSG_004` | Превышен размер файла | 413 | Размер файла превышает 5 МБ |

### 10.4. Ошибки WebSocket

| Код | Сообщение | WebSocket код | Описание |
|-----|-----------|---------------|----------|
| `WS_001` | Неавторизованное подключение | 4001 | Отсутствует или неверный токен |
| `WS_002` | Неверный user_id | 4003 | user_id не соответствует токену |
| `WS_003` | Слишком много подключений | 4008 | Превышено максимальное количество подключений |

---

<a name="примеры-использования"></a>
## 11. Примеры использования

### 11.1. Python: Отправка сообщения

```python
import requests
import json

# 1. Аутентификация
login_data = {
    "username": "john_doe",
    "password": "SecurePass123!"
}
response = requests.post("http://localhost:8000/auth/login", json=login_data)
token = response.json()["data"]["access_token"]

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 2. Отправка сообщения
message_data = {
    "receiver_id": 2,
    "content": "Привет от API!",
    "message_type": "text"
}
response = requests.post("http://localhost:8000/messages/", 
                        json=message_data, 
                        headers=headers)
print(response.json())
```

### 11.2. Python: WebSocket клиент

```python
import asyncio
import websockets
import json

async def websocket_client():
    token = "your_jwt_token_here"
    user_id = 1
    
    uri = f"ws://localhost:8000/ws/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with websockets.connect(uri, extra_headers=headers) as websocket:
        print("Подключено к WebSocket")
        
        # Получение приветственного сообщения
        welcome = await websocket.recv()
        print(f"Сервер: {welcome}")
        
        # Основной цикл получения сообщений
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                if data["event"] == "new_message":
                    print(f"Новое сообщение от {data['data']['sender_id']}: {data['data']['content']}")
                elif data["event"] == "ping":
                    # Отправляем pong в ответ
                    pong = json.dumps({"event": "pong", "timestamp": data["timestamp"]})
                    await websocket.send(pong)
                    
            except websockets.exceptions.ConnectionClosed:
                print("Соединение закрыто")
                break

# Запуск клиента
asyncio.run(websocket_client())
```

### 11.3. JavaScript: Отправка сообщения

```javascript
// Отправка сообщения с помощью fetch API
async function sendMessage() {
    const token = "your_jwt_token_here";
    
    const response = await fetch('http://localhost:8000/messages/', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            receiver_id: 2,
            content: 'Привет из JavaScript!',
            message_type: 'text'
        })
    });
    
    const data = await response.json();
    console.log('Ответ сервера:', data);
}

// WebSocket соединение
function connectWebSocket() {
    const token = "your_jwt_token_here";
    const userId = 1;
    
    const ws = new WebSocket(`ws://localhost:8000/ws/${userId}`);
    
    ws.onopen = function() {
        console.log('WebSocket соединение установлено');
        ws.send(JSON.stringify({
            event: 'auth',
            token: token
        }));
    };
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('Получено сообщение:', data);
    };
    
    ws.onclose = function() {
        console.log('WebSocket соединение закрыто');
    };
}
```

### 11.4. curl: Примеры запросов

```bash
# Регистрация нового пользователя
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test_user", "password": "Test123!", "display_name": "Test User"}'

# Вход в систему
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test_user", "password": "Test123!"}'

# Получение списка пользователей (с токеном)
curl -X GET http://localhost:8000/users/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Отправка сообщения
curl -X POST http://localhost:8000/messages/ \
  -H "Authorization: Bearer ..." \
  -H "Content-Type: application/json" \
  -d '{"receiver_id": 2, "content": "Привет!", "message_type": "text"}'
```

---

<a name="postman-коллекция"></a>
## 12. Postman коллекция

### 12.1. Импорт коллекции

Скопируйте следующий JSON в Postman:

```json
{
  "info": {
    "name": "Local Messenger API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Аутентификация",
      "item": [
        {
          "name": "Регистрация",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"username\": \"test_user\",\n  \"password\": \"Test123!\",\n  \"display_name\": \"Test User\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/auth/register",
              "host": ["{{base_url}}"],
              "path": ["auth", "register"]
            }
          }
        },
        {
          "name": "Вход в систему",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"username\": \"test_user\",\n  \"password\": \"Test123!\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/auth/login",
              "host": ["{{base_url}}"],
              "path": ["auth", "login"]
            }
          }
        }
      ]
    },
    {
      "name": "Пользователи",
      "item": [
        {
          "name": "Получить текущего пользователя",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer {{access_token}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/auth/me",
              "host": ["{{base_url}}"],
              "path": ["auth", "me"]
            }
          }
        },
        {
          "name": "Получить список пользователей",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer {{access_token}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/users/",
              "host": ["{{base_url}}"],
              "path": ["users", ""]
            }
          }
        }
      ]
    },
    {
      "name": "Сообщения",
      "item": [
        {
          "name": "Отправить сообщение",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer {{access_token}}"
              },
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"receiver_id\": 2,\n  \"content\": \"Привет из Postman!\",\n  \"message_type\": \"text\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/messages/",
              "host": ["{{base_url}}"],
              "path": ["messages", ""]
            }
          }
        },
        {
          "name": "Получить историю сообщений",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer {{access_token}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/messages/conversation/2",
              "host": ["{{base_url}}"],
              "path": ["messages", "conversation", "2"]
            }
          }
        }
      ]
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    },
    {
      "key": "access_token",
      "value": "ваш_jwt_токен_здесь"
    }
  ]
}
```

### 12.2. Переменные окружения

Создайте environment в Postman:

| Variable | Initial Value | Current Value |
|----------|---------------|---------------|
| `base_url` | `http://localhost:8000` | `http://localhost:8000` |
| `access_token` | - | (заполнится после логина) |

### 12.3. Тестовые скрипты

Добавьте следующий тестовый скрипт к запросу `/auth/login`:

```javascript
// Сохраняем токен в переменные окружения
if (pm.response.code === 200) {
    const responseData = pm.response.json();
    pm.environment.set("access_token", responseData.data.access_token);
    console.log("Токен сохранен:", pm.environment.get("access_token"));
}
```

### 12.4. Pre-request скрипты

Для автоматической проверки токена добавьте pre-request скрипт:

```javascript
// Проверяем, что токен установлен
const token = pm.environment.get("access_token");
if (!token && !pm.request.url.toString().includes("/auth/")) {
    pm.sendRequest({
        url: pm.environment.get("base_url") + "/auth/login",
        method: 'POST',
        header: {
            'Content-Type': 'application/json'
        },
        body: {
            mode: 'raw',
            raw: JSON.stringify({
                username: "test_user",
                password: "Test123!"
            })
        }
    }, function (err, res) {
        if (!err && res.code === 200) {
            pm.environment.set("access_token", res.json().data.access_token);
            console.log("Токен автоматически получен");
        }
    });
}
```

---

## Заключение

### Ключевые особенности API:

1. **RESTful дизайн** - логичная структура endpoints
2. **JWT аутентификация** - безопасный доступ к ресурсам
3. **Real-time обновления** - WebSocket для мгновенных уведомлений
4. **Полная документация** - Swagger UI по адресу `/docs`
5. **Обработка ошибок** - стандартизированные коды ошибок

### Ограничения API:

1. **Rate limiting** - отсутствует (для учебного проекта)
2. **HTTPS** - только HTTP (рекомендуется использовать HTTPS в production)
3. **Кэширование** - не реализовано
4. **Версионирование API** - не поддерживается

### Рекомендации по использованию:

1. Всегда проверяйте коды ответов
2. Используйте обработку ошибок на клиентской стороне
3. Реализуйте механизм повторных попыток для неудачных запросов
4. Регулярно обновляйте токены аутентификации
5. Используйте WebSocket для real-time функциональности

---

**Последнее обновление:** 2026  
**Контакты для поддержки API:** Малиневский Егор Сергеевич (21ИС-24)  
**GitHub репозиторий:** [https://github.com/Leendeseqy/PKOvchinnikova_21IS_4semestr_Malinevskiy](https://github.com/Leendeseqy/PKOvchinnikova_21IS_4semestr_Malinevskiy)

*Документация актуальна для версии 1.0 API локального мессенджера*