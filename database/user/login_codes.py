import logging
import time
import secrets
from typing import Optional
from ..core import get_db

CODE_LIFETIME_SECONDS = 300

async def create_login_code(user_id: Optional[int], is_qr: bool = False) -> Optional[str]:
    try:
        if is_qr:
            code = f"qr_{secrets.token_urlsafe(16)}"
        else:
            code = str(secrets.randbelow(900000) + 100000)

        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO login_codes (user_id, code, created_ts, is_qr) VALUES ($1, $2, $3, $4)",
                user_id, code, int(time.time()), is_qr
            )
        return code
    except Exception as e:
        logging.error(f"Ошибка при создании кода входа для {user_id}: {e}")
        return None

async def get_last_code_timestamp(user_id: int) -> int:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT MAX(created_ts) FROM login_codes WHERE user_id = $1", user_id)
            return val if val is not None else 0
    except Exception:
        return 0

async def get_user_id_by_login_code(code: str) -> Optional[int]:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_after_ts = int(time.time()) - CODE_LIFETIME_SECONDS
            user_id = await conn.fetchval(
                """SELECT user_id FROM login_codes 
                   WHERE code = $1 AND is_used = 0 AND created_ts > $2""",
                code, valid_after_ts
            )
            return user_id
    except Exception as e:
        logging.error(f"Ошибка при поиске user_id по коду входа: {e}")
        return None

async def delete_login_code(code: str) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM login_codes WHERE code = $1", code)
        return True
    except Exception as e:
        logging.error(f"Ошибка при удалении кода входа {code}: {e}")
        return False

async def verify_login_code(user_id: int, code: str) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            valid_after_ts = int(time.time()) - CODE_LIFETIME_SECONDS
            row = await conn.fetchrow(
                """SELECT id FROM login_codes 
                   WHERE user_id = $1 AND code = $2 AND is_used = 0 AND created_ts > $3""",
                user_id, code, valid_after_ts
            )

            if row:
                code_id = row['id']
                await conn.execute("UPDATE login_codes SET is_used = 1 WHERE id = $1", code_id)
                return True
        return False
    except Exception:
        return False
