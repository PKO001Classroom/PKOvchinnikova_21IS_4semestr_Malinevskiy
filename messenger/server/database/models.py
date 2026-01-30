from database.db import get_db_connection
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
from typing import List, Optional
from enum import Enum
import os, zoneinfo


class MessageModel:
    @staticmethod
    def create_message(sender_id: int, receiver_id: int, content: str, 
                     message_type: str = "text", file_data: Optional[str] = None) -> int:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now(tz=ZoneInfo("Europe/Moscow"))

        cursor.execute("""
            INSERT INTO messages (sender_id, receiver_id, content, message_type, file_data, timestamp, is_read)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sender_id, receiver_id, content, message_type, file_data, now, False))
        
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message_id

    @staticmethod
    def get_messages_between_users(user1_id: int, user2_id: int, limit: int = 100) -> List[dict]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.*, u1.username as sender_username, u2.username as receiver_username
            FROM messages m
            JOIN users u1 ON m.sender_id = u1.id
            JOIN users u2 ON m.receiver_id = u2.id
            WHERE (m.sender_id = ? AND m.receiver_id = ?)
               OR (m.sender_id = ? AND m.receiver_id = ?)
            ORDER BY m.timestamp DESC
            LIMIT ?
        """, (user1_id, user2_id, user2_id, user1_id, limit))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages

    @staticmethod
    def get_unread_messages(user_id: int) -> List[dict]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.*, u.username as sender_username
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.receiver_id = ? AND m.is_read = FALSE
            ORDER BY m.timestamp
        """, (user_id,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages

    @staticmethod
    def mark_as_read(message_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE messages SET is_read = TRUE WHERE id = ?
        """, (message_id,))
        
        conn.commit()
        conn.close()

    @staticmethod
    def delete_message(message_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()
        conn.close()
class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"

class UserStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"