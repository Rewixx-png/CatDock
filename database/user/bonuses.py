import logging
from ..core import get_db
from .profile import _clear_user_cache

async def set_user_tariff_discount(user_id: int, percent: int, code: str | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET active_discount_percent = $1, active_discount_code = $2 WHERE user_id = $3",
                percent, code, user_id
            )
            if result == "UPDATE 0":
                logging.warning(f"⚠️ [BONUS] Не удалось установить скидку пользователю {user_id}: пользователь не найден в БД.")
            else:
                logging.info(f"✅ [BONUS] Пользователю {user_id} установлена скидка {percent}% (код: {code}). Результат: {result}")
    except Exception as e:
        logging.error(f"❌ [BONUS] Ошибка при установке скидки для {user_id}: {e}", exc_info=True)

    _clear_user_cache(user_id)

async def set_user_deposit_bonus(user_id: int, percent: int, code: str | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET active_deposit_bonus_percent = $1, active_deposit_bonus_code = $2 WHERE user_id = $3",
                percent, code, user_id
            )
            if result == "UPDATE 0":
                logging.warning(f"⚠️ [BONUS] Не удалось установить бонус к депозиту пользователю {user_id}.")
            else:
                logging.info(f"✅ [BONUS] Пользователю {user_id} установлен бонус к депозиту {percent}% (код: {code}). Результат: {result}")
    except Exception as e:
        logging.error(f"❌ [BONUS] Ошибка при установке бонуса к депозиту для {user_id}: {e}", exc_info=True)

    _clear_user_cache(user_id)

async def set_user_free_container_promo(user_id: int, has_promo: bool, code: str | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET has_free_container_promo = $1, free_container_promo_code = $2 WHERE user_id = $3",
                has_promo, code, user_id
            )
    except Exception as e:
        logging.error(f"❌ [BONUS] Ошибка при установке фри-контейнера для {user_id}: {e}")
    _clear_user_cache(user_id)

async def set_user_free_server_change(user_id: int, has_promo: bool, code: str | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET has_free_server_change = $1, free_server_change_code = $2 WHERE user_id = $3",
                has_promo, code, user_id
            )
    except Exception as e:
        logging.error(f"❌ [BONUS] Ошибка при установке фри-смены сервера для {user_id}: {e}")
    _clear_user_cache(user_id)

async def increment_user_roulette_spins(user_id: int):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET roulette_spins_total = roulette_spins_total + 1 WHERE user_id = $1", user_id)
    _clear_user_cache(user_id)

async def set_user_last_weekly_spin(user_id: int, timestamp: int):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET last_weekly_roulette_ts = $1 WHERE user_id = $2", timestamp, user_id)
    _clear_user_cache(user_id)

async def add_user_free_spins(user_id: int, amount: int = 1):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET free_spins = free_spins + $1 WHERE user_id = $2", amount, user_id)
    _clear_user_cache(user_id)

async def use_user_free_spin(user_id: int) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.execute("UPDATE users SET free_spins = free_spins - 1 WHERE user_id = $1 AND free_spins > 0", user_id)
            is_success = "UPDATE 0" not in result
            if is_success:
                _clear_user_cache(user_id)
            return is_success
    except Exception as e:
        logging.error(f"Ошибка при использовании фри-спина для {user_id}: {e}")
        return False

async def get_last_bonus_claim_time(user_id: int) -> int:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT last_bonus_claim_ts FROM users WHERE user_id = $1", user_id)
            return val or 0
    except Exception as e:
        logging.error(f"DB Error get_last_bonus_claim_time: {e}")
        return 0

async def set_last_bonus_claim_time(user_id: int, timestamp: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET last_bonus_claim_ts = $1 WHERE user_id = $2", timestamp, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error set_last_bonus_claim_time: {e}")
