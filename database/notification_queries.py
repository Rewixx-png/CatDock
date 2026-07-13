import logging
from .core import get_db

async def create_notification(user_id: int, text: str, link: str | None = None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO notifications (user_id, text, link) VALUES ($1, $2, $3)",
                user_id, text, link
            )
    except Exception as e:
        logging.error(f"Ошибка при создании уведомления для {user_id}: {e}")

async def get_user_notifications(user_id: int, limit: int = 50) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2", 
                user_id, limit
            )
            return [dict(row) for row in rows]
    except Exception:
        return []

async def count_unread_notifications(user_id: int) -> int:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(id) FROM notifications WHERE user_id = $1 AND is_read = FALSE", user_id)
            return count or 0
    except Exception:
        return 0

async def mark_all_notifications_as_read(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = $1 AND is_read = FALSE", user_id)
    except Exception as e:
        logging.error(f"Ошибка при пометке уведомлений как прочитанных для {user_id}: {e}")

async def delete_all_user_notifications(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM notifications WHERE user_id = $1", user_id)
        logging.info(f"Все уведомления для пользователя {user_id} были удалены.")
    except Exception as e:
        logging.error(f"Ошибка при удалении всех уведомлений для {user_id}: {e}")

async def delete_old_notifications(days: int = 30) -> int:
    """Удаляет уведомления старше указанного количества дней."""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            
            result = await conn.execute(
                f"DELETE FROM notifications WHERE created_at < NOW() - INTERVAL '{days} days'"
            )
            
            count = int(result.split()[-1])
            return count
    except Exception as e:
        logging.error(f"Ошибка при удалении старых уведомлений: {e}")
        return 0
