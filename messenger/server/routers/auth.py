from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from database.user_model import UserModel
from schemas.user import UserCreate, UserLogin, UserResponse
from passlib.context import CryptContext
import jwt
from dependencies import get_current_user

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your-secret-key-here"

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

@router.post("/status")
async def update_user_status(
    status_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Обновление статуса пользователя
    """
    try:
        user_id = status_data.get("user_id")
        is_online = status_data.get("is_online", False)
        
        # Проверяем, что пользователь обновляет свой статус
        if user_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="Cannot update other user status")
        
        status_text = "online" if is_online else "offline"
        UserModel.update_user_status(user_id, is_online, status_text)
        
        return {
            "status": "success",
            "message": f"User {user_id} status updated to {status_text}",
            "user_id": user_id,
            "is_online": is_online
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status update error: {str(e)}")

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    existing_user = UserModel.get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = get_password_hash(user.password)
    
    # Автоматически делаем первого пользователя админом
    is_admin = False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users")
    user_count = cursor.fetchone()["count"]
    conn.close()
    
    if user_count == 0:  # Первый пользователь становится админом
        is_admin = True
    
    user_id = UserModel.create_user(user.username, hashed_password, is_admin)
    
    user_data = UserModel.get_user_by_id(user_id)
    return UserResponse(**user_data)

@router.post("/login")
async def login(user: UserLogin):
    user_data = UserModel.get_user_by_username(user.username)
    if not user_data or not verify_password(user.password, user_data["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    UserModel.update_user_status(user_data["id"], True, "online")
    
    access_token = create_access_token({"sub": user_data["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Выход пользователя из системы
    Обновляет статус на оффлайн
    """
    try:
        # Обновляем статус пользователя на оффлайн
        UserModel.update_user_status(current_user["id"], False, "offline")
        
        return {
            "status": "success", 
            "message": "Successfully logged out",
            "user_id": current_user["id"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout error: {str(e)}")

# Добавим функцию для получения соединения с БД
def get_db_connection():
    import sqlite3
    from pathlib import Path
    DB_PATH = Path("messenger.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn