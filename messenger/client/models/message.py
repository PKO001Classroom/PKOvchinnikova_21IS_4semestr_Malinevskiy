from datetime import datetime
from typing import List, Optional

class Message:
    def __init__(
        self,
        message_id: int,
        sender_id: int,
        receiver_id: int,
        content: str,
        timestamp: datetime,
        is_read: bool = False,
        message_type: str = "text",
        file_data: str = None  # Добавляем поле для хранения данных файла
    ):
        self.id = message_id
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.content = content
        self.timestamp = timestamp
        self.is_read = is_read
        self.message_type = message_type
        self.file_data = file_data  # Хранение base64 данных файла
        self.attachments = []

    def mark_as_read(self):
        self.is_read = True

    def add_attachment(self, attachment_path: str):
        self.attachments.append(attachment_path)

    def get_formatted_time(self) -> str:
        return self.timestamp.strftime("%H:%M")

    def is_outgoing(self, current_user_id: int) -> bool:
        return self.sender_id == current_user_id

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "is_read": self.is_read,
            "message_type": self.message_type,
            "file_data": self.file_data,  # Включаем file_data в сериализацию
            "attachments": self.attachments
        }

    @classmethod
    def from_dict(cls, data: dict):
        timestamp = datetime.fromisoformat(data["timestamp"])
        message = cls(
            message_id=data["id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            content=data["content"],
            timestamp=timestamp,
            is_read=data.get("is_read", False),
            message_type=data.get("message_type", "text"),
            file_data=data.get("file_data")  # Важно: получаем file_data из данных
        )
        message.attachments = data.get("attachments", [])
        return message