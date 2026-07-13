import logging
import secrets
import time
from .core import get_db

TRANSFER_TOKEN_LIFETIME_SECONDS = 15 * 60

async def create_transfer_token(container_id: int, creator_user_id: int) -> str | None:
    token = f"ct_{secrets.token_urlsafe(16)}"
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                owner_id = await conn.fetchval(
                    "SELECT user_id FROM user_containers WHERE id = $1 FOR UPDATE",
                    container_id,
                )
                if owner_id is None or int(owner_id) != int(creator_user_id):
                    logging.warning(
                        "Отказ в создании токена передачи контейнера %s пользователем %s",
                        container_id,
                        creator_user_id,
                    )
                    return None

                await conn.execute(
                    "DELETE FROM container_transfer_tokens WHERE container_id = $1",
                    container_id,
                )
                await conn.execute(
                    "INSERT INTO container_transfer_tokens "
                    "(token, container_id, creator_user_id, created_ts) "
                    "VALUES ($1, $2, $3, $4)",
                    token,
                    container_id,
                    creator_user_id,
                    int(time.time()),
                )
        logging.info(f"Создан токен передачи {token} для контейнера {container_id} от пользователя {creator_user_id}.")
        return token
    except Exception as e:
        logging.error(f"Ошибка при создании токена передачи для контейнера {container_id}: {e}", exc_info=True)
        return None

async def claim_container_transfer(
    token: str,
    new_owner_id: int,
) -> tuple[dict | None, str]:
    """Atomically consume a transfer token and change container ownership."""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                transfer = await conn.fetchrow(
                    "SELECT * FROM container_transfer_tokens WHERE token = $1 FOR UPDATE",
                    token,
                )
                if not transfer:
                    return None, "invalid"

                if int(transfer['created_ts']) <= int(time.time()) - TRANSFER_TOKEN_LIFETIME_SECONDS:
                    await conn.execute(
                        "DELETE FROM container_transfer_tokens WHERE token = $1",
                        token,
                    )
                    return None, "expired"

                container = await conn.fetchrow(
                    "SELECT * FROM user_containers WHERE id = $1 FOR UPDATE",
                    transfer['container_id'],
                )
                if not container:
                    await conn.execute(
                        "DELETE FROM container_transfer_tokens WHERE token = $1",
                        token,
                    )
                    return None, "invalid"

                current_owner_id = int(container['user_id'])
                creator_user_id = int(transfer['creator_user_id'])
                if current_owner_id != creator_user_id:
                    await conn.execute(
                        "DELETE FROM container_transfer_tokens WHERE token = $1",
                        token,
                    )
                    return None, "stale"
                if current_owner_id == int(new_owner_id):
                    return None, "self"

                await conn.execute(
                    "UPDATE user_containers SET user_id = $1 WHERE id = $2",
                    new_owner_id,
                    container['id'],
                )
                await conn.execute(
                    "DELETE FROM container_transfer_tokens WHERE token = $1",
                    token,
                )

                result = dict(container)
                result['original_owner_id'] = current_owner_id
                result['user_id'] = new_owner_id
                return result, "ok"
    except Exception as e:
        logging.error(
            "Ошибка получения контейнера по токену %s: %s",
            token,
            e,
            exc_info=True,
        )
        return None, "database_error"

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
