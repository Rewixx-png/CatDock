import logging
from ..core import get_db
from config import REFERRAL_PERCENTAGE
from .profile import _clear_user_cache

async def get_referrer_id(user_id: int) -> int | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT referrer_id FROM users WHERE user_id = $1", user_id)
            return val
    except Exception as e:
        logging.error(f"Ошибка при получении ID реферера: {e}")
        return None

async def add_referral_reward(referrer_id: int, deposit_amount: float) -> float | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            percentage = REFERRAL_PERCENTAGE
            reward_amount = deposit_amount * percentage

            await conn.execute("UPDATE users SET ref_balance = ref_balance + $1 WHERE user_id = $2", reward_amount, referrer_id)

        _clear_user_cache(referrer_id)
        return reward_amount
    except Exception as e:
        logging.error(f"Ошибка при начислении реф. вознаграждения: {e}")
        return None

async def get_referral_stats(user_id: int):
    stats = {'count': 0, 'referrer_name': None}
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            stats['count'] = await conn.fetchval("SELECT COUNT(*) FROM users WHERE referrer_id = $1", user_id)

            referrer_id = await conn.fetchval("SELECT referrer_id FROM users WHERE user_id = $1", user_id)

            if referrer_id:
                ref_row = await conn.fetchrow("SELECT first_name, username FROM users WHERE user_id = $1", referrer_id)
                if ref_row:
                    name = ref_row['username'] if ref_row['username'] else ref_row['first_name']
                    prefix = "@" if ref_row['username'] else ""
                    stats['referrer_name'] = f"{prefix}{name}"
    except Exception as e:
        logging.error(f"Ошибка при получении реферальной статистики: {e}")
    return stats

async def set_advanced_referral(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET has_advanced_referral = TRUE WHERE user_id = $1", user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"Ошибка set_advanced_referral: {e}")
