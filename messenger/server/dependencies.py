from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from database.user_model import UserModel

security = HTTPBearer()
SECRET_KEY = "your-secret-key-here"

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = UserModel.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Обновляем время последней активности при каждом запросе
        try:
            UserModel.update_last_seen(user["id"])
        except:
            pass  # Игнорируем ошибки обновления last_seen
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")