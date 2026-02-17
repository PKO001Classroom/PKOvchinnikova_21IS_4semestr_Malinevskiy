"""
Пакет маршрутов API сервера.
"""

from server.routers import auth, messages, users, admin

__all__ = ['auth', 'messages', 'users', 'admin']

"""
Пакет Pydantic схем сервера.
"""

from server.schemas.user import UserCreate, UserLogin, UserResponse, UserUpdate, UserStatus
from server.schemas.message import MessageCreate, MessageResponse, MessagesList, MessageType

__all__ = [
    'UserCreate', 'UserLogin', 'UserResponse', 'UserUpdate', 'UserStatus',
    'MessageCreate', 'MessageResponse', 'MessagesList', 'MessageType'
]