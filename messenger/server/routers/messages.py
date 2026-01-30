from fastapi import APIRouter, HTTPException, Depends, Query
from database.message_model import MessageModel  # Измененный импорт
from database.user_model import UserModel  # Измененный импорт
from database.db import get_db_connection
from schemas.message import MessageCreate, MessageResponse, MessagesList
from dependencies import get_current_user
from websocket_manager import manager
import logging
import base64

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=MessagesList)
async def get_messages(
    current_user: dict = Depends(get_current_user),
    contact_id: int = Query(...),
    limit: int = Query(100, ge=1, le=1000)
):
    messages = MessageModel.get_messages_between_users(current_user["id"], contact_id, limit)
    return MessagesList(
        messages=[MessageResponse(**msg) for msg in messages],
        total_count=len(messages)
    )

@router.post("/", response_model=MessageResponse)
async def send_message(
    message: MessageCreate,
    current_user: dict = Depends(get_current_user)
):
    # Для изображений сохраняем file_data в базе
    message_type = message.message_type.value
    content = message.content
    
    # Если это изображение и есть file_data, сохраняем его
    file_data = None
    if hasattr(message, 'file_data') and message.file_data:
        file_data = message.file_data
    
    message_id = MessageModel.create_message(
        current_user["id"],
        message.receiver_id,
        content,
        message_type,
        file_data
    )
    
    # Get the created message with file_data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
    message_data = dict(cursor.fetchone())
    conn.close()
    
    # Явно добавляем file_data в ответ, если он есть
    response_data = dict(message_data)
    if file_data:
        response_data["file_data"] = file_data
    
    return MessageResponse(**response_data)

@router.put("/{message_id}/read")
async def mark_message_as_read(
    message_id: int,
    current_user: dict = Depends(get_current_user)
):
    MessageModel.mark_as_read(message_id)
    return {"status": "success", "message": "Message marked as read"}

@router.get("/unread", response_model=MessagesList)
async def get_unread_messages(current_user: dict = Depends(get_current_user)):
    messages = MessageModel.get_unread_messages(current_user["id"])
    return MessagesList(
        messages=[MessageResponse(**msg) for msg in messages],
        total_count=len(messages)
    )

@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    current_user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем полную информацию о сообщении
        cursor.execute("SELECT id, sender_id, receiver_id, content, timestamp FROM messages WHERE id = ?", (message_id,))
        message = cursor.fetchone()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Проверяем права на удаление
        if message["sender_id"] != current_user["id"] and not UserModel.is_admin(current_user["id"]):
            raise HTTPException(status_code=403, detail="Cannot delete other users messages")
        
        # Удаляем сообщение
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()
        
        # Получаем ID участников переписки
        participant_ids = [message["sender_id"], message["receiver_id"]]
        
        # Отправляем real-time уведомление обоим пользователям
        update_message = {
            "type": "message_deleted",
            "message_id": message_id,
            "chat_id": f"{min(message['sender_id'], message['receiver_id'])}_{max(message['sender_id'], message['receiver_id'])}",
            "deleted_by": current_user["id"],
            "timestamp": message["timestamp"]
        }
        
        await manager.broadcast_to_users(update_message, participant_ids)
        logger.info(f"Message {message_id} deleted by user {current_user['id']}. Notified users: {participant_ids}")
        
        return {
            "status": "success", 
            "message": "Message deleted",
            "deleted_message_id": message_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        conn.close()