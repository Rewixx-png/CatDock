import logging
import secrets
from datetime import datetime, timedelta
from ..core import get_db
from .profile import _clear_user_cache

async def check_if_user_used_free_tariff(user_id: int) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT has_used_free_tariff FROM users WHERE user_id = $1", user_id)
            return bool(val)
    except Exception:
        return False

async def mark_free_tariff_as_used(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET has_used_free_tariff = TRUE WHERE user_id = $1", user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error mark_free_tariff_as_used: {e}")

async def admin_reset_free_tariff_usage(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET has_used_free_tariff = FALSE, last_verified_ip = NULL WHERE user_id = $1", user_id)
        _clear_user_cache(user_id)
        logging.info(f"Администратор сбросил лимит бесплатного тарифа для пользователя {user_id}")
    except Exception as e:
        logging.error(f"DB Error admin_reset_free_tariff_usage: {e}")

async def create_verification_token(user_id: int, server_id: str, image_id: str, tariff_id: str, username: str | None, message_id: int = 0, chat_id: int = 0) -> str:
    token = secrets.token_urlsafe(32)
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO verification_tokens 
                   (token, user_id, server_id, image_id, tariff_id, username, creation_date, message_id, chat_id) 
                   VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8)""",
                token, user_id, server_id, image_id, tariff_id, username, message_id, chat_id
            )
        return token
    except Exception as e:
        logging.error(f"DB Error create_verification_token: {e}")
        return ""

async def get_user_by_verification_token(token: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_time = datetime.now() - timedelta(minutes=30)
            row = await conn.fetchrow(
                "SELECT * FROM verification_tokens WHERE token = $1 AND is_used = FALSE AND creation_date > $2",
                token, valid_time
            )
            if row: return dict(row)
        return None
    except Exception as e:
        logging.error(f"Ошибка при поиске по токену верификации: {e}")
        return None

async def consume_verification_token(token: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE verification_tokens SET is_used = TRUE WHERE token = $1", token)
    except Exception as e:
        logging.error(f"Ошибка при сжигании токена {token}: {e}")

async def get_token_info_any_status(token: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            time_limit = datetime.now() - timedelta(minutes=60)
            row = await conn.fetchrow(
                "SELECT * FROM verification_tokens WHERE token = $1 AND creation_date > $2",
                token, time_limit
            )
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Ошибка get_token_info_any_status: {e}")
        return None

async def ip_exists_in_db(ip_address: str) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1 FROM users WHERE last_verified_ip = $1 LIMIT 1", ip_address)
            return val is not None
    except Exception as e:
        logging.error(f"Ошибка при проверке IP в БД: {e}")
        return False

async def set_user_verified_ip(user_id: int, ip_address: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET last_verified_ip = $1 WHERE user_id = $2", ip_address, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error set_user_verified_ip: {e}")
