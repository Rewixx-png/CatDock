import logging
from datetime import datetime, timedelta
from typing import List, Dict
from .core import get_db

async def add_server_metric(server_id: str, cpu: float, ram: float, disk: float):
    """Сохраняет метрики сервера в БД."""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO server_metrics (server_id, cpu_usage, ram_usage, disk_usage, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                """,
                server_id, cpu, ram, disk
            )
    except Exception as e:
        logging.error(f"DB Error saving metrics for {server_id}: {e}")

async def get_server_metrics_history(server_id: str, metric_type: str, hours: int) -> List[float]:
    """
    Получает историю метрик за последние N часов.
    metric_type: 'cpu', 'ram', 'disk'
    """
    column_map = {
        'cpu': 'cpu_usage',
        'ram': 'ram_usage',
        'disk': 'disk_usage'
    }
    col = column_map.get(metric_type, 'cpu_usage')
    
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            
            rows = await conn.fetch(
                f"""
                SELECT {col} as val 
                FROM server_metrics 
                WHERE server_id = $1 
                  AND created_at > NOW() - INTERVAL '{hours} hours'
                ORDER BY created_at ASC
                """,
                server_id
            )
            return [float(r['val']) for r in rows]
    except Exception as e:
        logging.error(f"DB Error fetching history for {server_id}: {e}")
        return []

async def cleanup_old_metrics(days: int = 30):
    """Удаляет метрики старше N дней."""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM server_metrics WHERE created_at < NOW() - INTERVAL '$1 days'",
                days
            )
    except Exception as e:
        logging.error(f"DB Error cleaning metrics: {e}")
