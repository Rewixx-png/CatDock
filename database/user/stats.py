import logging
from ..core import get_db
import settings

async def get_top_balance_user() -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT first_name, username, balance 
                FROM users 
                WHERE role = 'PARTICIPANT' 
                  AND user_id != ALL($1::bigint[])
                ORDER BY balance DESC 
                LIMIT 1
            """, settings.EXCLUDED_FROM_TOP)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching top balance: {e}")
        return None

async def get_top_specs_container() -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT u.first_name, u.username, c.ram_mb, c.cpu_limit, c.container_name
                FROM user_containers c
                JOIN users u ON c.user_id = u.user_id
                WHERE u.role = 'PARTICIPANT' 
                  AND c.tariff_id != 'admin'
                  AND u.user_id != ALL($1::bigint[])
                  AND c.ram_mb IS NOT NULL
                  AND c.cpu_limit IS NOT NULL
                ORDER BY c.ram_mb DESC, c.cpu_limit DESC
                LIMIT 1
            """, settings.EXCLUDED_FROM_TOP)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching top specs: {e}")
        return None

async def get_top_time_container() -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT u.first_name, u.username, c.remaining_seconds, c.container_name
                FROM user_containers c
                JOIN users u ON c.user_id = u.user_id
                WHERE u.role = 'PARTICIPANT' 
                  AND c.tariff_id != 'admin'
                  AND u.user_id != ALL($1::bigint[])
                ORDER BY c.remaining_seconds DESC
                LIMIT 1
            """, settings.EXCLUDED_FROM_TOP)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching top time: {e}")
        return None

async def get_oldest_user() -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT first_name, username, reg_date
                FROM users
                WHERE role = 'PARTICIPANT'
                  AND user_id != ALL($1::bigint[])
                ORDER BY reg_date ASC
                LIMIT 1
            """, settings.EXCLUDED_FROM_TOP)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching oldest user: {e}")
        return None

async def get_top_level_user() -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT first_name, username, level, xp
                FROM users
                WHERE role = 'PARTICIPANT'
                  AND user_id != ALL($1::bigint[])
                ORDER BY level DESC, xp DESC
                LIMIT 1
            """, settings.EXCLUDED_FROM_TOP)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching top level user: {e}")
        return None
