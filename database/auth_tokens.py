import logging
import time
import secrets
from typing import Optional, Dict
from .core import get_db
from .user.api_tokens import create_api_token
import settings 

async def create_auth_token() -> str:
    token = f"login_{secrets.token_urlsafe(16)}"
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO auth_tokens (token, created_ts) VALUES ($1, $2)",
                token, int(time.time())
            )
        return token
    except Exception as e:
        logging.error(f"Ошибка при создании auth_token: {e}", exc_info=True)
        return ""

async def approve_auth_token(token: str, user_id: int) -> Optional[str]:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_after_ts = int(time.time()) - settings.AUTH_TOKEN_LIFETIME

            row = await conn.fetchrow(
                "SELECT token FROM auth_tokens WHERE token = $1 AND created_ts > $2 AND status = 'pending'",
                token, valid_after_ts
            )

            if not row:
                logging.warning(f"Попытка подтвердить недействительный/устаревший токен: {token}")
                return None

            api_key = await create_api_token(user_id)
            if not api_key:
                raise Exception(f"Не удалось создать API ключ для пользователя {user_id}")

            await conn.execute(
                "UPDATE auth_tokens SET status = 'approved', api_key = $1, user_id = $2 WHERE token = $3",
                api_key, user_id, token
            )
            return api_key
    except Exception as e:
        logging.error(f"Ошибка при подтверждении auth_token {token}: {e}", exc_info=True)
        return None

async def get_auth_token_status(token: str) -> Optional[Dict]:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_after_ts = int(time.time()) - settings.AUTH_TOKEN_LIFETIME

            row = await conn.fetchrow(
                "SELECT status, api_key FROM auth_tokens WHERE token = $1 AND created_ts > $2",
                token, valid_after_ts
            )

            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Ошибка при получении статуса auth_token {token}: {e}", exc_info=True)
        return None

async def delete_auth_token(token: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM auth_tokens WHERE token = $1", token)
    except Exception as e:
        logging.error(f"Ошибка при удалении auth_token {token}: {e}", exc_info=True)
