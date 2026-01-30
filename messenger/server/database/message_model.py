from datetime import datetime
from database.db import get_db_connection
from typing import List, Optional

class MessageModel:
    @staticmethod
    def create_message(sender_id: int, receiver_id: int, content: str, 
                     message_type: str = "text", file_data: Optional[str] = None) -> int:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO messages (sender_id, receiver_id, content, message_type, file_data)
            VALUES (?, ?, ?, ?, ?)
        """, (sender_id, receiver_id, content, message_type, file_data))
        
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message_id

    @staticmethod
    def get_messages_between_users(user1_id: int, user2_id: int, limit: int = 100) -> List[dict]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM messages 
            WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
            ORDER BY timestamp DESC LIMIT ?
        """, (user1_id, user2_id, user2_id, user1_id, limit))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages

    @staticmethod
    def get_unread_messages(user_id: int) -> List[dict]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM messages WHERE receiver_id = ? AND is_read = FALSE
        """, (user_id,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages

    @staticmethod
    def mark_as_read(message_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE messages SET is_read = TRUE WHERE id = ?", (message_id,))
        
        conn.commit()
        conn.close()

    @staticmethod
    def delete_message(message_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()
        conn.close()