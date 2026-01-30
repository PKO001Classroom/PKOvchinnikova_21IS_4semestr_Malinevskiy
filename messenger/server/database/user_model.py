from datetime import datetime
from database.db import get_db_connection
import sqlite3

class UserModel:
    @staticmethod
    def create_user(username: str, password_hash: str, is_admin: bool = False):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, password_hash, is_admin)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id

    @staticmethod
    def get_user_by_username(username: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def get_user_by_id(user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def update_user_status(user_id: int, is_online: bool, status: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        last_seen = datetime.now() if not is_online else None
        cursor.execute(
            "UPDATE users SET is_online = ?, status = ?, last_seen = ? WHERE id = ?",
            (is_online, status, last_seen, user_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def update_last_seen(user_id: int):
        """Обновление времени последней активности"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET last_seen = ? WHERE id = ?",
                (datetime.now(), user_id)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def check_inactive_users(timeout_minutes: int = 5):
        """Пометить пользователей, которые не активны дольше timeout_minutes"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Вычисляем пороговое время
        timeout_ago = datetime.now() - timedelta(minutes=timeout_minutes)
        
        # Находим пользователей онлайн, у которых last_seen слишком старый
        cursor.execute("""
            SELECT id FROM users 
            WHERE is_online = TRUE 
            AND last_seen < ?
        """, (timeout_ago,))
        
        inactive_users = [row["id"] for row in cursor.fetchall()]
        
        # Устанавливаем их статус в оффлайн
        for user_id in inactive_users:
            cursor.execute("""
                UPDATE users 
                SET is_online = FALSE, status = 'offline' 
                WHERE id = ?
            """, (user_id,))
        
        conn.commit()
        conn.close()
        return inactive_users

    @staticmethod
    def get_all_users():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, is_online, status, last_seen FROM users")
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users

    @staticmethod
    def is_admin(user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result["is_admin"] if result else False