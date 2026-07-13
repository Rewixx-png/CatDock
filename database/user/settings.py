import logging
from ..core import get_db
from .profile import _clear_user_cache

VALID_SETTING_KEYS = [
    'show_id', 'show_name', 'show_username', 'show_role',
    'show_userbots', 'show_main_balance', 'show_ref_balance',
    'use_custom_photo', 'use_old_banners' 
]

async def get_user_settings(user_id: int) -> dict:
    default_settings = {key: False if key in ['use_custom_photo', 'use_old_banners'] else True for key in VALID_SETTING_KEYS}

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM user_settings WHERE user_id = $1", user_id)

            if row:
                return dict(row)
            else:
                return default_settings
    except Exception as e:
        logging.error(f"Ошибка получения настроек для пользователя {user_id}: {e}")
        return default_settings

async def toggle_user_setting(user_id: int, setting_key: str):
    if setting_key not in VALID_SETTING_KEYS:
        logging.error(f"Попытка изменить невалидный ключ настройки: {setting_key}")
        return

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO user_settings (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING", 
                user_id
            )

            query = f"UPDATE user_settings SET {setting_key} = NOT {setting_key} WHERE user_id = $1"
            await conn.execute(query, user_id)

        _clear_user_cache(user_id)
        logging.info(f"Настройка '{setting_key}' для пользователя {user_id} была переключена.")

    except Exception as e:
        logging.error(f"Ошибка при переключении настройки '{setting_key}' для {user_id}: {e}", exc_info=True)
