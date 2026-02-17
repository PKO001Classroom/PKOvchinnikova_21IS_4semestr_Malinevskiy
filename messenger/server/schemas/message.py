from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"

class MessageBase(BaseModel):
    content: str
    receiver_id: int
    message_type: MessageType = MessageType.TEXT
    file_data: Optional[str] = None  # Добавляем поле для данных файла

class MessageCreate(MessageBase):
    pass

class MessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    timestamp: datetime
    is_read: bool
    message_type: str
    file_data: Optional[str] = None  # Добавляем в ответ

    class Config:
        from_attributes = True

class MessagesList(BaseModel):
    messages: list[MessageResponse]
    total_count: int