import logging
import secrets
import time
from .core import get_db

TRANSFER_TOKEN_LIFETIME_SECONDS = 15 * 60

async def create_transfer_token(container_id: int, creator_user_id: int) -> str | None:
    await delete_token_for_container(container_id)

    token = f"claim_{secrets.token_urlsafe(16)}"
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO container_transfer_tokens (token, container_id, creator_user_id, created_ts) VALUES ($1, $2, $3, $4)",
                token, container_id, creator_user_id, int(time.time())
            )
        logging.info(f"Создан токен передачи {token} для контейнера {container_id} от пользователя {creator_user_id}.")
        return token
    except Exception as e:
        logging.error(f"Ошибка при создании токена передачи для контейнера {container_id}: {e}", exc_info=True)
        return None

async def get_transfer_data_by_token(token: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_after_ts = int(time.time()) - TRANSFER_TOKEN_LIFETIME_SECONDS

            row = await conn.fetchrow(
                "SELECT * FROM container_transfer_tokens WHERE token = $1 AND created_ts > $2",
                token, valid_after_ts
            )
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Ошибка при поиске токена передачи {token}: {e}", exc_info=True)
        return None

async def delete_transfer_token(token: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM container_transfer_tokens WHERE token = $1", token)
    except Exception as e:
        logging.error(f"Ошибка при удалении токена передачи {token}: {e}", exc_info=True)

async def delete_token_for_container(container_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM container_transfer_tokens WHERE container_id = $1", container_id)
        logging.info(f"Удален токен передачи для контейнера {container_id}.")
    except Exception as e:
        logging.error(f"Ошибка при удалении токена для контейнера {container_id}: {e}", exc_info=True)

async def get_active_token_for_container(container_id: int) -> str | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_after_ts = int(time.time()) - TRANSFER_TOKEN_LIFETIME_SECONDS
            val = await conn.fetchval(
                "SELECT token FROM container_transfer_tokens WHERE container_id = $1 AND created_ts > $2",
                container_id, valid_after_ts
            )
            return val
    except Exception as e:
        logging.error(f"Ошибка при поиске активного токена для контейнера {container_id}: {e}")
        return None
