import logging
from ..core import get_db

async def save_backup_record(user_id: int, tariff_id: str, path: str, size: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM container_backups WHERE user_id = $1 AND tariff_id = $2", user_id, tariff_id)

            await conn.execute(
                "INSERT INTO container_backups (user_id, tariff_id, backup_path, file_size) VALUES ($1, $2, $3, $4)",
                user_id, tariff_id, path, size
            )
    except Exception as e:
        logging.error(f"DB Error save_backup: {e}")

async def get_user_backup(user_id: int, tariff_id: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM container_backups WHERE user_id = $1 AND tariff_id = $2 ORDER BY created_at DESC LIMIT 1",
                user_id, tariff_id
            )
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"DB Error get_backup: {e}")
        return None

async def delete_backup_record(backup_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM container_backups WHERE id = $1", backup_id)
    except Exception as e:
        logging.error(f"DB Error delete_backup: {e}")
