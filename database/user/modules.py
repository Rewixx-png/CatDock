import logging
from ..core import get_db

async def add_user_module(user_id: int, filename: str, local_path: str, file_size: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM user_modules WHERE user_id = $1 AND filename = $2",
                user_id, filename
            )

            if existing:
                await conn.execute(
                    "UPDATE user_modules SET local_path = $1, file_size = $2, saved_at = NOW() WHERE id = $3",
                    local_path, file_size, existing
                )
            else:
                await conn.execute(
                    "INSERT INTO user_modules (user_id, filename, local_path, file_size) VALUES ($1, $2, $3, $4)",
                    user_id, filename, local_path, file_size
                )
    except Exception as e:
        logging.error(f"DB Error add_user_module: {e}")

async def get_user_saved_modules(user_id: int) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM user_modules WHERE user_id = $1 ORDER BY saved_at DESC", 
                user_id
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"DB Error get_user_saved_modules: {e}")
        return []

async def get_module_by_id(module_id: int) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM user_modules WHERE id = $1", module_id)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"DB Error get_module_by_id: {e}")
        return None

async def delete_user_module(module_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM user_modules WHERE id = $1", module_id)
    except Exception as e:
        logging.error(f"DB Error delete_user_module: {e}")
