import logging
from .core import get_db

async def get_bot_setting(key: str) -> str | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT value FROM bot_settings WHERE key = $1", key)
            return val
    except Exception as e:
        logging.error(f"Ошибка при получении настройки '{key}': {e}")
        return None

async def set_bot_setting(key: str, value: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO bot_settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                key, value
            )
    except Exception as e:
        logging.error(f"Ошибка при установке настройки '{key}': {e}")
