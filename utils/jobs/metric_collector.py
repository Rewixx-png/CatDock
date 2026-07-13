import logging
import asyncio
import re
from aiogram import Bot

from config import SERVERS
from utils import bot_state
from utils.network_checker import get_server_full_stats
import database as db

async def collect_server_metrics(bot: Bot):
    """
    Задача для сбора метрик со всех активных серверов.
    Запускается планировщиком каждые N минут.
    """

    tasks = []
    
    for server_id, server_info in SERVERS.items():
        
        if not bot_state.server_states.get(server_id, True):
            continue
            
        tasks.append(_process_single_server(server_id))
        
    await asyncio.gather(*tasks)

async def _process_single_server(server_id: str):
    try:
        stats = await get_server_full_stats(server_id)

        cpu = _parse_val(stats.get('cpu', '0'))
        ram = _parse_val(stats.get('ram', '0'))
        disk = _parse_val(stats.get('disk', '0'))

        if stats.get('cpu') == 'Н/Д':
            return

        await db.add_server_metric(server_id, cpu, ram, disk)
        
    except Exception as e:
        logging.warning(f"Collector: Failed to collect/save metrics for {server_id}: {e}")

def _parse_val(val_str: str) -> float:
    try:
        
        clean = re.sub(r'[^\d.]', '', val_str)
        return float(clean)
    except ValueError:
        return 0.0
