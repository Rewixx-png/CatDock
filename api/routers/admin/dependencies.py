from fastapi import Depends, HTTPException
import database as db
from roles import UserRole, ROLE_NAMES
from api.dependencies import get_current_user_id

async def get_current_admin(user_id: int = Depends(get_current_user_id)) -> dict:
    """
    Проверяет, является ли пользователь администратором.
    Возвращает профиль администратора с расширенными полями.
    """
    user_role = await db.get_user_role(user_id)
    if not user_role or user_role < UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    profile = await db.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Admin profile not found")

    profile['user_id'] = user_id
    profile['role_enum'] = user_role 
    return profile
