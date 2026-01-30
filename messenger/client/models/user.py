from datetime import datetime
from typing import Optional

class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        is_online: bool = False,
        last_seen: Optional[datetime] = None,
        status: str = "offline"
    ):
        self.id = user_id
        self.username = username
        self.is_online = is_online
        self.last_seen = last_seen
        self.status = status
        self.avatar = None

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "is_online": self.is_online,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: dict):
        last_seen = datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else None
        return cls(
            user_id=data["id"],
            username=data["username"],
            is_online=data.get("is_online", False),
            last_seen=last_seen,
            status=data.get("status", "offline")
        )

    def update_status(self, is_online: bool, status: str):
        self.is_online = is_online
        self.status = status
        if not is_online:
            self.last_seen = datetime.now()