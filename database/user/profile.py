import logging
import time
import json
from datetime import datetime
from ..core import get_db
from roles import DEFAULT_ROLE, UserRole
from utils import bot_state

def _clear_user_cache(user_id: int):
    bot_state.user_profile_cache.pop(user_id, None)
    bot_state.user_role_cache.pop(user_id, None)
    bot_state.user_language_cache.pop(user_id, None)
    bot_state.user_block_cache.pop(user_id, None)

async def update_user_telemetry(user_id: int, ip: str, country: str, device_info: dict):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users 
                SET last_ip = $1, 
                    country_code = $2, 
                    device_info = $3 
                WHERE user_id = $4
                """,
                ip, country, json.dumps(device_info), user_id
            )

        if user_id in bot_state.user_profile_cache:
             bot_state.user_profile_cache[user_id]['last_ip'] = ip
             bot_state.user_profile_cache[user_id]['country_code'] = country
             bot_state.user_profile_cache[user_id]['device_info'] = device_info 

    except Exception as e:
        logging.error(f"DB Error update_user_telemetry: {e}")

async def get_user_custom_avatar(user_id: int) -> str | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT custom_avatar_url FROM users WHERE user_id = $1", user_id)
            return val
    except Exception as e:
        logging.error(f"DB Error get_user_custom_avatar: {e}")
        return None

async def set_user_custom_avatar(user_id: int, file_url: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET custom_avatar_url = $1 WHERE user_id = $2", file_url, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error set_user_custom_avatar: {e}")

async def add_user(user_id: int, username: str, first_name: str, referrer_id: int | None = None) -> bool:
    is_new_user = False
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM users WHERE user_id = $1", user_id)
            if not exists:
                is_new_user = True
                await conn.execute(
                    """INSERT INTO users (user_id, username, first_name, reg_date, referrer_id, role) 
                       VALUES ($1, $2, $3, NOW(), $4, $5) ON CONFLICT (user_id) DO NOTHING""",
                    user_id, username, first_name, referrer_id, DEFAULT_ROLE
                )
                logging.info(f"Новый пользователь зарегистрирован: {user_id} ({first_name}).")
    except Exception as e:
        logging.error(f"DB Error add_user: {e}")

    if is_new_user:
        _clear_user_cache(user_id)
    return is_new_user

async def get_user_profile(user_id: int, use_cache: bool = True):
    if use_cache and user_id in bot_state.user_profile_cache:
        return bot_state.user_profile_cache[user_id]

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if row:
                profile = dict(row)
                if profile.get('reg_date'):
                    profile['reg_date'] = str(profile['reg_date'])

                if 'game_checks' not in profile:
                    profile['game_checks'] = 0

                if 'device_info' in profile:
                    d_info = profile['device_info']
                    if isinstance(d_info, str):
                        try: 
                            profile['device_info'] = json.loads(d_info)
                        except: 
                            profile['device_info'] = {}
                    elif d_info is None:
                        profile['device_info'] = {}

                if not use_cache:
                    logging.info(f"🔍 [DB_READ] User {user_id} profile loaded.")

                bot_state.user_profile_cache[user_id] = profile
                return profile
    except Exception as e:
        logging.error(f"DB Error get_user_profile: {e}")
    return None

async def get_all_user_ids() -> list[int]:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users WHERE is_blocked = FALSE")
            return [r['user_id'] for r in rows]
    except Exception as e:
        logging.error(f"DB Error get_all_user_ids: {e}")
        return []

async def get_user_role(user_id: int) -> UserRole:
    if user_id in bot_state.user_role_cache:
        return bot_state.user_role_cache[user_id]

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            role_str = await conn.fetchval("SELECT role FROM users WHERE user_id = $1", user_id)
            role = UserRole.PARTICIPANT
            if role_str is not None:
                try:
                    if role_str.isdigit():
                        role = UserRole(int(role_str))
                    else:
                        try:
                            role = UserRole[role_str]
                        except KeyError:
                            pass 
                except (ValueError, TypeError):
                    pass
            bot_state.user_role_cache[user_id] = role
            return role
    except Exception as e:
        logging.error(f"DB Error get_user_role: {e}")
        return UserRole.PARTICIPANT

async def get_user_balance(user_id: int) -> float:
    profile = await get_user_profile(user_id)
    return profile.get('balance', 0.0) if profile else 0.0

async def update_user_balance(user_id: int, amount: float):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)

    _clear_user_cache(user_id)

async def try_deduct_user_balance(user_id: int, amount: float) -> bool:
    if amount < 0: amount = abs(amount)

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2 AND balance >= $1", 
                amount, user_id
            )

            if "UPDATE 1" in result:
                _clear_user_cache(user_id)
                return True
            return False
    except Exception as e:
        logging.error(f"DB Error try_deduct_user_balance: {e}")
        return False

async def get_user_ref_balance(user_id: int) -> float:
    profile = await get_user_profile(user_id)
    return profile.get('ref_balance', 0.0) if profile else 0.0

async def admin_update_user_ref_balance(user_id: int, delta: float):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET ref_balance = ref_balance + $1 WHERE user_id = $2", delta, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error admin_update_user_ref_balance: {e}")

async def debit_referral_balance(user_id: int, amount: float):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET ref_balance = ref_balance - $1 WHERE user_id = $2", amount, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error debit_referral_balance: {e}")
