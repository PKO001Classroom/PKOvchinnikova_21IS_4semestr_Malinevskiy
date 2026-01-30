from fastapi import APIRouter, HTTPException, Depends
from database.user_model import UserModel  # Измененный импорт
from schemas.user import UserResponse, UserUpdate
from dependencies import get_current_user

router = APIRouter()

@router.get("/", response_model=list[UserResponse])
async def get_all_users(current_user: dict = Depends(get_current_user)):
    users = UserModel.get_all_users()
    return [UserResponse(**user) for user in users]

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    user = UserModel.get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, current_user: dict = Depends(get_current_user)):
    user = UserModel.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    if user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Cannot update other users")
    
    user = UserModel.get_user_by_id(user_id)
    return UserResponse(**user)