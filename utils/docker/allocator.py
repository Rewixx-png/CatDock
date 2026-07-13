import asyncio
import logging
import time
from config import SERVERS, TARIFFS
import database as db
from utils import bot_state
from utils.network_checker import get_server_available_ram_mb
from roles import UserRole
import settings 

async def _notify_admins_on_no_slots(tariff_id: str, reason: str):
    try:
        bot = bot_state.get_bot_instance()
        tariff_name = TARIFFS.get(tariff_id, {}).get('name', tariff_id)
        message = f"🚨 <b>Внимание! Закончились места для тарифа «{tariff_name}»</b>\n\nПричина: {reason}"
        for admin_id in bot_state.admin_ids_cache:
            try:
                await bot.send_message(admin_id, message)
            except Exception as e:
                logging.warning(f"Не удалось отправить уведомление админу {admin_id}: {e}")
    except Exception as e:
        logging.error(f"Ошибка уведомления админов: {e}", exc_info=True)

async def find_optimal_server(tariff_id: str, user_id: int) -> str | None:
    user_role = await db.get_user_role(user_id)

    is_privileged_user = (user_id in settings.VIP_USER_IDS) or (user_role and user_role >= UserRole.ADMIN)

    available_servers = []
    for server_id, server_info in SERVERS.items():
        is_active = bot_state.server_states.get(server_id, True)
        is_exclusive = server_info.get('exclusive', False)
        if not is_active: continue
        if is_exclusive and not is_privileged_user: continue
        if is_exclusive and tariff_id == 'free': continue
        available_servers.append(server_id)

    if not available_servers: return None

    ram_needed_for_tariff = TARIFFS.get(tariff_id, {}).get('ram_mb', 300)
    eligible_servers = []
    tasks = {server_id: get_server_available_ram_mb(server_id) for server_id in available_servers}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    server_ram_map = dict(zip(tasks.keys(), results))

    for server_id, available_ram in server_ram_map.items():
        if isinstance(available_ram, Exception) or available_ram is None: continue

        if available_ram < settings.ALLOCATOR_MIN_RAM_MB: continue
        if available_ram < (ram_needed_for_tariff + settings.ALLOCATOR_RAM_BUFFER_MB): continue

        eligible_servers.append({'server_id': server_id, 'available_ram': available_ram})

    if not eligible_servers:
        current_time = time.time()
        last_notification_time = bot_state.slot_notification_timestamps.get(tariff_id, 0)
        if current_time - last_notification_time > settings.SLOT_NOTIFICATION_COOLDOWN:
            bot_state.slot_notification_timestamps[tariff_id] = current_time
            asyncio.create_task(_notify_admins_on_no_slots(tariff_id, "Недостаточно RAM."))
        return None

    return max(eligible_servers, key=lambda s: s['available_ram'])['server_id']
