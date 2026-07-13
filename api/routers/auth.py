import logging
import asyncio
from fastapi import APIRouter, HTTPException
import database as db
from config import get_bot_username
from api.schemas import GenerateTokenResponse, CheckTokenResponse 

router = APIRouter(tags=["Auth"])

@router.get(
    "/generate-token", 
    response_model=GenerateTokenResponse,
    summary="Создать токен входа",
    description="Генерирует временный токен для авторизации через Telegram бота."
)
async def generate_auth_token():
    try:
        token, bot_username = await asyncio.gather(
            db.create_auth_token(),
            asyncio.to_thread(get_bot_username)
        )
        if not token or not bot_username:
            raise Exception("Failed to generate token")

        return {
            "status": "success",
            "login_token": token,
            "bot_username": bot_username
        }
    except Exception as e:
        logging.error(f"Auth Generate Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get(
    "/check-token/{token}", 
    response_model=CheckTokenResponse,
    summary="Проверить статус токена",
    description="Возвращает API ключ, если пользователь подтвердил вход в боте."
)
async def check_auth_token(token: str):
    try:
        token_data = await db.get_auth_token_status(token)

        if not token_data:
            return {"status": "expired"}

        if token_data['status'] == 'approved':
            await db.delete_auth_token(token)
            return {
                "status": "success",
                "api_key": token_data['api_key']
            }
        else:
            return {"status": "pending"}

    except Exception as e:
        logging.error(f"Auth Check Error: {e}")
        raise HTTPException(status_code=500, detail="Server Error")
