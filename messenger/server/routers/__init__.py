"""
Пакет маршрутов API сервера.
"""

from server.routers import auth, messages, users, admin

__all__ = ['auth', 'messages', 'users', 'admin']