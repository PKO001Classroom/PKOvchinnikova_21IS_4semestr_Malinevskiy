from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db import init_db
from routers import auth, messages, users, admin
from fastapi import WebSocket, WebSocketDisconnect
from websocket_manager import manager
import asyncio
from database.user_model import UserModel

async def check_inactive_users_periodically():
    """Периодическая проверка неактивных пользователей"""
    while True:
        try:
            inactive_users = UserModel.check_inactive_users(timeout_minutes=1)
            if inactive_users:
                print(f"📴 Marked users as offline due to inactivity: {inactive_users}")
        except Exception as e:
            print(f"Error checking inactive users: {e}")
        
        await asyncio.sleep(60)  # Проверка каждую минуту

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация базы данных при запуске
    init_db()
    
    # Запускаем фоновую задачу для проверки неактивных пользователей
    task = asyncio.create_task(check_inactive_users_periodically())
    
    yield
    
    # Останавливаем задачу при остановке приложения
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация базы данных при запуске
    init_db()
    yield
    # Опционально: код для закрытия соединений при остановке

app = FastAPI(
    title="Local Messenger API",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    try:
        while True:
            try:
                # Ожидаем сообщения
                data = await websocket.receive_text()
                
                # Обрабатываем ping/pong
                if data == 'ping':
                    await websocket.send_text('pong')
                elif data == 'pong':
                    continue
                else:
                    # Можно добавить обработку других сообщений
                    try:
                        message = json.loads(data)
                        # Здесь можно добавить логику обработки сообщений
                        pass
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break
                
    except Exception as e:
        print(f"WebSocket endpoint error: {e}")
    finally:
        # Всегда вызываем disconnect
        try:
            manager.disconnect(websocket, user_id)
        except:
            pass
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="192.168.0.51", port=8000)