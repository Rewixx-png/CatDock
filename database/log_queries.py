import logging
from typing import List, Optional
from .core import get_db

async def add_system_log(
    actor_id: int, 
    action_type: str, 
    message: str, 
    target_id: int | None = None, 
    is_admin_action: bool = False
):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO system_logs 
                   (actor_id, target_id, action_type, message, is_admin_action, created_at) 
                   VALUES ($1, $2, $3, $4, $5, NOW())""",
                actor_id, target_id, action_type, message, is_admin_action
            )
    except Exception as e:
        logging.error(f"Ошибка при записи системного лога: {e}", exc_info=True)

async def get_system_logs(
    page: int = 0, 
    page_size: int = 50, 
    actor_id: Optional[int] = None, 
    target_id: Optional[int] = None, 
    action_type: Optional[str] = None,
    only_admins: bool = False
) -> tuple[list, int]:
    offset = page * page_size
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            query = "FROM system_logs l LEFT JOIN users u ON l.actor_id = u.user_id WHERE 1=1"
            params = []
            param_idx = 1

            if actor_id:
                query += f" AND l.actor_id = ${param_idx}"
                params.append(actor_id)
                param_idx += 1

            if target_id:
                query += f" AND l.target_id = ${param_idx}"
                params.append(target_id)
                param_idx += 1

            if action_type:
                query += f" AND l.action_type = ${param_idx}"
                params.append(action_type)
                param_idx += 1

            if only_admins:
                query += f" AND l.is_admin_action = TRUE"

            count_query = f"SELECT COUNT(*) {query}"
            total_count = await conn.fetchval(count_query, *params)

            select_query = f"""
                SELECT l.*, u.username as actor_username, u.first_name as actor_name 
                {query} 
                ORDER BY l.created_at DESC 
                LIMIT ${param_idx} OFFSET ${param_idx+1}
            """
            params.extend([page_size, offset])

            rows = await conn.fetch(select_query, *params)

            logs = []
            for row in rows:
                r = dict(row)
                r['created_at'] = str(r['created_at'])
                logs.append(r)

            return logs, total_count
    except Exception as e:
        logging.error(f"Ошибка получения логов: {e}", exc_info=True)
        return [], 0
