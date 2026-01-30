from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from enum import Enum

class UserStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"

class UserCreate(BaseModel):
    username: str
    password: str
    # email убран, так как не используется

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str

    is_online: bool
    last_seen: Optional[datetime] = None
    status: UserStatus
    is_admin: bool = False
    
class UserResponse(BaseModel):
    id: int
    username: str

    is_online: bool
    last_seen: Optional[datetime] = None
    status: UserStatus

class UserUpdate(BaseModel):

    status: Optional[UserStatus] = None