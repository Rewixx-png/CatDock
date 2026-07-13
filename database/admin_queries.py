import logging
from .core import get_db

async def get_dashboard_stats():
    stats = {
        "total_users": 0,
        "active_containers": 0,
        "revenue_24h": 0.0,
        "open_tickets": 0
    }
    error_detail = None

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            try:
                stats["total_users"] = await conn.fetchval("SELECT COUNT(*) FROM users")
            except Exception as e:
                logging.error(f"DB Error (Users): {e}")
                error_detail = f"Users Query: {e}"

            try:
                stats["active_containers"] = await conn.fetchval("SELECT COUNT(*) FROM user_containers WHERE is_frozen = FALSE")
            except Exception as e:
                logging.error(f"DB Error (Containers): {e}")
                error_detail = f"Containers Query: {e}"

            try:
                crypto_24h = await conn.fetchval("""
                    SELECT COALESCE(SUM(fiat_amount), 0) 
                    FROM crypto_payments 
                    WHERE creation_date > NOW() - INTERVAL '24 hours'
                """) or 0.0

                stars_24h = await conn.fetchval("""
                    SELECT COALESCE(SUM(rub_amount), 0) 
                    FROM star_payments 
                    WHERE creation_date > NOW() - INTERVAL '24 hours'
                """) or 0.0

                stats["revenue_24h"] = float(crypto_24h) + float(stars_24h)
            except Exception as e:
                logging.error(f"DB Error (Revenue): {e}")
                if not error_detail: error_detail = f"Revenue Query: {e}"

            try:
                stats["open_tickets"] = await conn.fetchval("SELECT COUNT(*) FROM support_tickets WHERE status != 'closed'")
            except Exception as e:
                logging.error(f"DB Error (Tickets): {e}")

            return stats, error_detail

    except Exception as e:
        logging.critical(f"Critical DB connection error in dashboard: {e}")
        return stats, str(e)

async def get_recent_admin_logs(limit=5):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT l.message, l.action_type, l.created_at, u.username, u.first_name
                FROM system_logs l
                LEFT JOIN users u ON l.actor_id = u.user_id
                ORDER BY l.created_at DESC 
                LIMIT $1
            """, limit)

            result = []
            for r in rows:
                name = r.get('first_name') or r.get('username') or "System"
                result.append({
                    "action": r.get('message', 'Unknown action'),
                    "type": r.get('action_type', 'info'),
                    "admin": name,
                    "time": str(r.get('created_at', ''))
                })
            return result
    except Exception as e:
        logging.error(f"DB Error (Logs): {e}")
        return []
