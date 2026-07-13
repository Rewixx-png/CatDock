import logging
from ..core import get_db
from .profile import _clear_user_cache

async def add_user_xp(user_id: int, amount: int) -> tuple[int, int, bool]:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT level, xp FROM users WHERE user_id = $1", user_id)
            if not row:
                return 1, 0, False

            current_level = row['level']
            current_xp = row['xp']

            new_xp = current_xp + amount

            next_level_threshold = int(100 * (current_level ** 1.5))

            is_level_up = False
            new_level = current_level

            while new_xp >= next_level_threshold:
                new_xp -= next_level_threshold
                new_level += 1
                is_level_up = True
                next_level_threshold = int(100 * (new_level ** 1.5))

            await conn.execute(
                "UPDATE users SET level = $1, xp = $2 WHERE user_id = $3",
                new_level, new_xp, user_id
            )

        _clear_user_cache(user_id)
        return new_level, new_xp, is_level_up

    except Exception as e:
        logging.error(f"Ошибка при добавлении XP пользователю {user_id}: {e}", exc_info=True)
        return 1, 0, False
