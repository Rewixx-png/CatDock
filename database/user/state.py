import logging
from ..core import get_db
from .profile import _clear_user_cache
from utils import bot_state

async def get_user_language(user_id: int) -> str | None:
    if user_id in bot_state.user_language_cache:
        return bot_state.user_language_cache[user_id]

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT language_code FROM users WHERE user_id = $1", user_id)

            result = val if val else 'ru' 
            bot_state.user_language_cache[user_id] = result
            return result
    except Exception:
        return None

async def set_user_language(user_id: int, language_code: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET language_code = $1 WHERE user_id = $2", language_code, user_id)

        bot_state.user_language_cache[user_id] = language_code
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error set_user_language: {e}")
