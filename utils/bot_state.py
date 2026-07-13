from aiogram import Bot
from typing import Optional, List, Dict, Any

_bot_instance: Optional[Bot] = None

def get_bot_instance() -> Bot:
    if _bot_instance is None:
        raise RuntimeError("Bot instance has not been set yet. Call set_bot_instance() first.")
    return _bot_instance

def set_bot_instance(bot: Bot):
    global _bot_instance
    _bot_instance = bot

maintenance_mode = False
raid_mode = False

admin_ids_cache = set()
bot_info_cache = None
bot_start_time = None

servers_cache: Dict[str, Dict[str, Any]] = {}
server_states = {} 

server_failure_counters: Dict[str, int] = {}

slot_notification_timestamps = {}

server_statuses_cache: List[Dict[str, Any]] = []
server_status_last_update: float = 0.0

user_profile_cache: Dict[int, Dict[str, Any]] = {}
user_role_cache: Dict[int, Any] = {}
user_language_cache: Dict[int, str] = {}
user_block_cache: Dict[int, bool] = {}

anti_abuse_cache: Dict[int, Dict[str, Any]] = {}

container_restart_counters: Dict[str, int] = {}
