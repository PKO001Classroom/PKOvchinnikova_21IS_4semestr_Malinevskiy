from fastapi import APIRouter, HTTPException, Depends

# Исправляем импорты - добавляем server.
from server.database.user_model import UserModel
from server.database.message_model import MessageModel
from server.dependencies import get_current_user
from server.database.db import get_db_connection

router = APIRouter()

@router.get("/all-messages")
async def get_all_messages(current_user: dict = Depends(get_current_user)):
    if not UserModel.is_admin(current_user["id"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    messages = [dict(row) for row in rows] if rows else []
    conn.close()
    
    return {"messages": messages}

@router.get("/all-users")
async def get_all_users_info(current_user: dict = Depends(get_current_user)):
    if not UserModel.is_admin(current_user["id"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = UserModel.get_all_users()
    return {"users": users}