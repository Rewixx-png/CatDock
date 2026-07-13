import logging
from ..core import get_db

async def add_user_session(user_id: int, session_string: str, comment: str | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO user_sessions (user_id, session_string, comment) VALUES ($1, $2, $3)",
                user_id, session_string, comment
            )
    except Exception as e:
        logging.error(f"Ошибка при добавлении сессии для {user_id}: {e}")

async def get_user_sessions(user_id: int) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM user_sessions WHERE user_id = $1 ORDER BY creation_date DESC", user_id)
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка при получении сессий для {user_id}: {e}")
        return []

async def delete_user_session(session_id: int, user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM user_sessions WHERE id = $1 AND user_id = $2", session_id, user_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сессии {session_id} для пользователя {user_id}: {e}")
