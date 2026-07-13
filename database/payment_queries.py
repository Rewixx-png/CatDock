import logging
from .core import get_db
import json
from config import REFERRAL_PERCENTAGE, ADVANCED_REFERRAL_PERCENTAGE

async def create_payment_request(user_id: int, amount: float, method: str, details: dict) -> int | None:
    if amount <= 0 or not method:
        return None
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            request_id = await conn.fetchval(
                """INSERT INTO payment_requests (user_id, amount, method, details) 
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                user_id, amount, method, json.dumps(details)
            )
            return request_id
    except Exception as e:
        logging.error(f"DB Error create_payment_request: {e}")
        return None

async def get_payment_request_by_id(request_id: int) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT pr.*, u.username, u.first_name 
                FROM payment_requests pr
                LEFT JOIN users u ON pr.user_id = u.user_id
                WHERE pr.id = $1
            """, request_id)
            if row:
                res = dict(row)
                if isinstance(res['details'], str):
                    res['details'] = json.loads(res['details'])
                return res
            return None
    except Exception as e:
        logging.error(f"DB Error get_payment_request_by_id: {e}")
        return None

async def get_user_payment_history(user_id: int, limit: int = 50) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:

            requests_rows = await conn.fetch("""
                SELECT id, amount, method, status, created_at, decline_reason 
                FROM payment_requests 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, user_id, limit)
            
            history = [dict(row) for row in requests_rows]

            star_rows = await conn.fetch("""
                SELECT id, rub_amount as amount, 'stars' as method, 'approved' as status, creation_date as created_at, NULL as decline_reason
                FROM star_payments
                WHERE user_id = $1
                ORDER BY creation_date DESC
                LIMIT $2
            """, user_id, limit)
            
            for row in star_rows:
                history.append(dict(row))

            crypto_rows = await conn.fetch("""
                SELECT id, fiat_amount as amount, 'crypto' as method, 'approved' as status, creation_date as created_at, NULL as decline_reason
                FROM crypto_payments
                WHERE user_id = $1
                ORDER BY creation_date DESC
                LIMIT $2
            """, user_id, limit)

            for row in crypto_rows:
                history.append(dict(row))

            history.sort(key=lambda x: x['created_at'], reverse=True)
            
            return history[:limit]

    except Exception as e:
        logging.error(f"DB Error get_user_payment_history: {e}")
        return []

async def update_payment_request_status(request_id: int, status: str, admin_id: int | None = None, reason: str | None = None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE payment_requests 
                SET status = $1, processed_by = $2, decline_reason = $3, updated_at = NOW()
                WHERE id = $4
            """, status, admin_id, reason, request_id)
    except Exception as e:
        logging.error(f"DB Error update_payment_request_status: {e}")

async def approve_payment_request(request_id: int, admin_id: int) -> tuple[dict | None, str]:
    """Atomically approve and credit a pending manual payment exactly once."""
    target_user_id = None
    referrer_id = None
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                request = await conn.fetchrow(
                    "SELECT * FROM payment_requests WHERE id = $1 FOR UPDATE",
                    request_id,
                )
                if not request:
                    return None, "not_found"
                if request['status'] != 'pending':
                    return dict(request), "already_processed"

                amount = float(request['amount'])
                if amount <= 0:
                    return None, "invalid_amount"

                target_user_id = int(request['user_id'])
                user = await conn.fetchrow(
                    "SELECT active_deposit_bonus_percent, referrer_id "
                    "FROM users WHERE user_id = $1 FOR UPDATE",
                    target_user_id,
                )
                if not user:
                    return None, "user_not_found"

                bonus_percent = max(0, int(user['active_deposit_bonus_percent'] or 0))
                bonus_amount = round(amount * bonus_percent / 100.0, 2)
                final_amount = round(amount + bonus_amount, 2)
                await conn.execute(
                    "UPDATE users SET balance = balance + $1, "
                    "active_deposit_bonus_percent = 0, active_deposit_bonus_code = NULL "
                    "WHERE user_id = $2",
                    final_amount,
                    target_user_id,
                )

                referrer_id = user['referrer_id']
                referral_reward = 0.0
                if referrer_id:
                    is_advanced = await conn.fetchval(
                        "SELECT has_advanced_referral FROM users WHERE user_id = $1 FOR UPDATE",
                        referrer_id,
                    )
                    referral_percent = (
                        ADVANCED_REFERRAL_PERCENTAGE if is_advanced else REFERRAL_PERCENTAGE
                    )
                    referral_reward = round(amount * referral_percent, 2)
                    await conn.execute(
                        "UPDATE users SET ref_balance = ref_balance + $1 WHERE user_id = $2",
                        referral_reward,
                        referrer_id,
                    )

                await conn.execute(
                    "UPDATE payment_requests SET status = 'approved', processed_by = $1, "
                    "decline_reason = NULL, updated_at = NOW() WHERE id = $2",
                    admin_id,
                    request_id,
                )

                result = dict(request)
                result.update(
                    final_amount=final_amount,
                    bonus_percent=bonus_percent,
                    referral_reward=referral_reward,
                )

        from .user.profile import _clear_user_cache

        _clear_user_cache(target_user_id)
        if referrer_id:
            _clear_user_cache(int(referrer_id))
        return result, "ok"
    except Exception as e:
        logging.error(f"DB Error approve_payment_request: {e}", exc_info=True)
        return None, "database_error"

async def decline_payment_request(
    request_id: int,
    admin_id: int,
    reason: str,
) -> tuple[dict | None, str]:
    """Atomically decline a pending manual payment exactly once."""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE payment_requests
                SET status = 'declined', processed_by = $1,
                    decline_reason = $2, updated_at = NOW()
                WHERE id = $3 AND status = 'pending'
                RETURNING *
                """,
                admin_id,
                reason,
                request_id,
            )
            if row:
                return dict(row), "ok"

            existing = await conn.fetchrow(
                "SELECT * FROM payment_requests WHERE id = $1",
                request_id,
            )
            if not existing:
                return None, "not_found"
            return dict(existing), "already_processed"
    except Exception as e:
        logging.error(f"DB Error decline_payment_request: {e}", exc_info=True)
        return None, "database_error"

async def check_star_payment_exists(charge_id: str) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM star_payments WHERE telegram_payment_charge_id = $1", 
                charge_id
            )
            return bool(exists)
    except Exception as e:
        logging.error(f"DB Error check_star_payment_exists: {e}")
        return False

async def log_star_payment(charge_id: str, user_id: int, star_amount: int, rub_amount: float):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO star_payments 
                   (telegram_payment_charge_id, user_id, star_amount, rub_amount)
                   VALUES ($1, $2, $3, $4)""",
                charge_id, user_id, star_amount, rub_amount
            )
    except Exception as e:
        logging.error(f"DB Error log_star_payment: {e}")


async def credit_star_payment(charge_id: str, user_id: int, star_amount: int, rub_amount: float) -> bool:
    """Atomically record a Telegram Stars payment and credit it once."""
    referrer_id = None
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                payment_id = await conn.fetchval(
                    """
                    INSERT INTO star_payments
                        (telegram_payment_charge_id, user_id, star_amount, rub_amount)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (telegram_payment_charge_id) DO NOTHING
                    RETURNING id
                    """,
                    charge_id, user_id, star_amount, rub_amount,
                )
                if payment_id is None:
                    return False
                await conn.execute(
                    "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                    rub_amount, user_id,
                )
                referrer_id = await conn.fetchval(
                    "SELECT referrer_id FROM users WHERE user_id = $1",
                    user_id,
                )
                if referrer_id:
                    is_advanced = await conn.fetchval(
                        "SELECT has_advanced_referral FROM users WHERE user_id = $1 FOR UPDATE",
                        referrer_id,
                    )
                    referral_percent = (
                        ADVANCED_REFERRAL_PERCENTAGE if is_advanced else REFERRAL_PERCENTAGE
                    )
                    await conn.execute(
                        "UPDATE users SET ref_balance = ref_balance + $1 WHERE user_id = $2",
                        round(float(rub_amount) * referral_percent, 2),
                        referrer_id,
                    )

        from .user.profile import _clear_user_cache
        _clear_user_cache(user_id)
        if referrer_id:
            _clear_user_cache(int(referrer_id))
        return True
    except Exception as e:
        logging.error(f"DB Error credit_star_payment: {e}", exc_info=True)
        return False

async def check_crypto_payment_exists(invoice_id: int) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM crypto_payments WHERE invoice_id = $1", 
                invoice_id
            )
            return bool(exists)
    except Exception as e:
        logging.error(f"DB Error check_crypto_payment_exists: {e}")
        return False

async def log_crypto_payment(invoice_id: int, user_id: int, fiat_amount: float, fiat_currency: str, paid_asset: str, paid_amount: float):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO crypto_payments 
                   (invoice_id, user_id, fiat_amount, fiat_currency, paid_asset, paid_amount)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (invoice_id) DO NOTHING""",
                invoice_id, user_id, fiat_amount, fiat_currency, paid_asset, paid_amount
            )
    except Exception as e:
        logging.error(f"DB Error log_crypto_payment: {e}")
