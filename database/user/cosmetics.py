import logging
from ..core import get_db

async def set_container_icon(container_id: int, icon_emoji: str | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET cosmetic_icon = $1 WHERE id = $2",
                icon_emoji, container_id
            )
    except Exception as e:
        logging.error(f"Ошибка при установке иконки для контейнера {container_id}: {e}")
