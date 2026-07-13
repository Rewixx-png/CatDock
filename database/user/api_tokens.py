import logging
import secrets
import time
from datetime import datetime
from ..core import get_db

async def create_web_token(user_id: int) -> str:
    token = f"rew_web_{secrets.token_urlsafe(32)}"
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE web_access_tokens SET is_active = FALSE WHERE user_id = $1", user_id)
            await conn.execute("INSERT INTO web_access_tokens (user_id, token) VALUES ($1, $2)", user_id, token)
        logging.info(f"DB: Создан и сохранен новый веб-токен для user_id: {user_id}")
        return token
    except Exception as e:
        logging.error(f"Ошибка при создании веб-токена для {user_id}: {e}", exc_info=True)
        return ""

async def get_user_by_web_token(token: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT u.* FROM users u
                JOIN web_access_tokens w ON u.user_id = w.user_id
                WHERE w.token = $1 AND w.is_active = TRUE
            """, token)

            if row:
                user_data = dict(row)
                await conn.execute(
                    "UPDATE web_access_tokens SET last_used_date = NOW() WHERE token = $1", 
                    token
                )
                return user_data
            else:
                return None
    except Exception as e:
        logging.error(f"Ошибка при поиске пользователя по веб-токену: {e}")
        return None

async def get_user_id_by_token(token: str) -> int | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT user_id FROM web_access_tokens 
                WHERE token = $1 AND is_active = TRUE
            """, token)

            if row:
                await conn.execute(
                    "UPDATE web_access_tokens SET last_used_date = NOW() WHERE token = $1", 
                    token
                )
                return row['user_id']
            return None
    except Exception as e:
        logging.error(f"DB Error checking token ownership: {e}")
        return None

async def revoke_all_web_tokens(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE web_access_tokens SET is_active = FALSE WHERE user_id = $1", user_id)
        logging.info(f"DB: Все веб-токены для user_id: {user_id} были отозваны.")
    except Exception as e:
        logging.error(f"Ошибка при отзыве всех веб-токенов для {user_id}: {e}", exc_info=True)

create_api_token = create_web_token

async def create_log_token(container_id: int) -> str:
    token = secrets.token_urlsafe(32)
    created_ts = int(time.time())
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM log_access_tokens WHERE container_id = $1", container_id)
            await conn.execute(
                "INSERT INTO log_access_tokens (token, container_id, created_ts) VALUES ($1, $2, $3)",
                token, container_id, created_ts
            )
        return token
    except Exception as e:
        logging.error(f"Ошибка создания токена логов для контейнера {container_id}: {e}")
        return ""

async def get_container_by_log_token(token: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_after_ts = int(time.time()) - 1800

            await conn.execute("DELETE FROM log_access_tokens WHERE created_ts < $1", valid_after_ts)

            row = await conn.fetchrow("""
                SELECT c.* 
                FROM user_containers c
                JOIN log_access_tokens l ON c.id = l.container_id
                WHERE l.token = $1 AND l.created_ts >= $2
            """, token, valid_after_ts)

            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Ошибка при поиске контейнера по токену логов: {e}")
        return None
