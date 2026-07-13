import logging
import database as db
from utils import bot_state
import json

async def load_servers_to_cache():
    try:
        servers = await db.get_all_servers_from_db()
        bot_state.servers_cache = servers

        bot_state.server_states = {sid: sdata.get('active', True) for sid, sdata in servers.items()}

        logging.info(f"📥 Загружено {len(servers)} серверов из БД в кэш.")
        return servers
    except Exception as e:
        logging.critical(f"Ошибка загрузки серверов из БД: {e}", exc_info=True)
        return {}
