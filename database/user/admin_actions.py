import logging
from ..core import get_db
from config import ALL_ADMIN_IDS
from roles import UserRole
from .profile import _clear_user_cache
from utils import bot_state

async def get_all_admin_ids() -> set[int]:
    admin_ids = set(ALL_ADMIN_IDS)
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, role FROM users")
            for row in rows:
                try:
                    role_val = row['role']
                    if str(role_val).isdigit():
                        role = UserRole(int(role_val))
                    else:
                        role = UserRole[role_val]

                    if role >= UserRole.JUNIOR_ADMIN:
                        admin_ids.add(row['user_id'])
                except (ValueError, KeyError):
                    continue
    except Exception as e:
        logging.error(f"DB Error get_all_admin_ids: {e}")

    return admin_ids

get_admin_ids = get_all_admin_ids

async def get_all_admins() -> list[dict]:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, username, first_name, role FROM users WHERE role NOT IN ('PARTICIPANT', '0')"
            )

            admins = []
            for row in rows:
                data = dict(row)
                role_raw = data['role']

                role_enum = UserRole.PARTICIPANT
                try:
                    if str(role_raw).isdigit():
                        role_enum = UserRole(int(role_raw))
                    else:
                        role_enum = UserRole[role_raw] 
                except (ValueError, KeyError):
                    continue

                if role_enum >= UserRole.JUNIOR_ADMIN:
                    data['role_value'] = role_enum.value 
                    admins.append(data)

            admins.sort(key=lambda x: x.get('role_value', 0), reverse=True)
            return admins

    except Exception as e:
        logging.error(f"DB Error in get_all_admins: {e}")
        return []

async def find_user(query: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            sql_query = "SELECT *, is_blocked FROM users WHERE "
            params = []
            if query.isdigit():
                sql_query += "user_id = $1"
                params = [int(query)]
            else:
                username = query.lstrip('@')
                sql_query += "username = $1"
                params = [username]

            row = await conn.fetchrow(sql_query, *params)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"DB Error in find_user: {e}")
        return None

async def admin_update_user_balance(user_id: int, delta: float):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", delta, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error in admin_update_user_balance: {e}")

async def get_all_users_paginated(page: int, page_size: int = 30, search_query: str | None = None) -> tuple[list, int]:
    offset = page * page_size
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            base_query = "FROM users"
            where_clause = ""
            params = []

            if search_query:
                where_clause = " WHERE user_id::text LIKE $1 OR username ILIKE $1 OR first_name ILIKE $1"
                like_query = f"%{search_query}%"
                params.append(like_query)

            count_query = f"SELECT COUNT(*) {base_query}{where_clause}"
            total_count = await conn.fetchval(count_query, *params)

            select_query = f"SELECT user_id, username, first_name, role, balance, is_blocked {base_query}{where_clause} ORDER BY reg_date DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
            params.extend([page_size, offset])

            rows = await conn.fetch(select_query, *params)
            return [dict(row) for row in rows], total_count

    except Exception as e:
        logging.error(f"DB Error in get_all_users_paginated: {e}", exc_info=True)
        return [], 0

async def is_user_blocked(user_id: int) -> bool:
    if user_id in bot_state.user_block_cache:
        return bot_state.user_block_cache[user_id]

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT is_blocked FROM users WHERE user_id = $1", user_id)

            is_blocked = bool(val)
            bot_state.user_block_cache[user_id] = is_blocked
            return is_blocked
    except Exception:
        return False

async def toggle_user_block(user_id: int) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            current_status = await conn.fetchval("SELECT is_blocked FROM users WHERE user_id = $1", user_id)
            if current_status is None: return False

            toggled_status = not current_status
            await conn.execute("UPDATE users SET is_blocked = $1 WHERE user_id = $2", toggled_status, user_id)

            _clear_user_cache(user_id)
            bot_state.user_block_cache[user_id] = toggled_status

            return toggled_status
    except Exception as e:
        logging.error(f"DB Error in toggle_user_block: {e}")
        return False

async def set_user_role(user_id: int, role_name: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET role = $1 WHERE user_id = $2", role_name, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error in set_user_role: {e}")

async def delete_user_fully(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                logging.info(f"Начинаю полное удаление пользователя {user_id} из БД...")

                await conn.execute("UPDATE users SET referrer_id = NULL WHERE referrer_id = $1", user_id)
                await conn.execute("UPDATE support_tickets SET assigned_admin_id = NULL WHERE assigned_admin_id = $1", user_id)
                await conn.execute("UPDATE promo_codes SET activator_id = NULL WHERE activator_id = $1", user_id)
                await conn.execute("UPDATE global_promo_codes SET activator_id = NULL WHERE activator_id = $1", user_id)

                await conn.execute("DELETE FROM promo_codes WHERE creator_id = $1", user_id)

                await conn.execute("DELETE FROM container_transfer_tokens WHERE creator_user_id = $1", user_id)
                await conn.execute("DELETE FROM user_containers WHERE user_id = $1", user_id)

                await conn.execute("DELETE FROM web_access_tokens WHERE user_id = $1", user_id)
                await conn.execute("DELETE FROM auth_tokens WHERE user_id = $1", user_id)
                await conn.execute("DELETE FROM verification_tokens WHERE user_id = $1", user_id)

                await conn.execute("DELETE FROM star_payments WHERE user_id = $1", user_id)
                await conn.execute("DELETE FROM crypto_payments WHERE user_id = $1", user_id)
                await conn.execute("DELETE FROM user_sessions WHERE user_id = $1", user_id)
                await conn.execute("DELETE FROM support_tickets WHERE user_id = $1", user_id)

                await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)

                _clear_user_cache(user_id)
                logging.info(f"Пользователь {user_id} полностью удален из БД.")

    except Exception as e:
        logging.error(f"DB Error in delete_user_fully: {e}", exc_info=True)
        raise e

async def add_user_warn(user_id: int) -> int:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            warn_count = await conn.fetchval(
                "UPDATE users SET warn_count = warn_count + 1 WHERE user_id = $1 RETURNING warn_count", 
                user_id
            )
            _clear_user_cache(user_id)
            return warn_count if warn_count is not None else 0
    except Exception as e:
        logging.error(f"DB Error add_user_warn: {e}")
        return 0

async def remove_user_warn(user_id: int) -> int:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            warn_count = await conn.fetchval(
                "UPDATE users SET warn_count = warn_count - 1 WHERE user_id = $1 AND warn_count > 0 RETURNING warn_count", 
                user_id
            )
            _clear_user_cache(user_id)
            return warn_count if warn_count is not None else 0
    except Exception as e:
        logging.error(f"DB Error remove_user_warn: {e}")
        return 0

async def get_user_warn_count(user_id: int) -> int:
    
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT warn_count FROM users WHERE user_id = $1", user_id)
            return val if val is not None else 0
    except Exception:
        return 0

async def reset_user_warns(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET warn_count = 0 WHERE user_id = $1", user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error reset_user_warns: {e}")

async def get_log_topic_id(user_id: int) -> int | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT log_topic_id FROM users WHERE user_id = $1", user_id)
            return val
    except Exception as e:
        logging.error(f"DB Error get_log_topic_id: {e}")
        return None

async def set_log_topic_id(user_id: int, topic_id: int | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET log_topic_id = $1 WHERE user_id = $2", topic_id, user_id)
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error set_log_topic_id: {e}")

async def admin_pardon_user(user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET warn_count = 0 WHERE user_id = $1", user_id)
        logging.info(f"DB: Все счетчики предупреждений для пользователя {user_id} сброшены.")
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error admin_pardon_user: {e}")

async def admin_update_user_checks(user_id: int, delta: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET game_checks = GREATEST(0, game_checks + $1) WHERE user_id = $2", 
                delta, user_id
            )
        _clear_user_cache(user_id)
    except Exception as e:
        logging.error(f"DB Error admin_update_user_checks: {e}")
