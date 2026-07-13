import logging
import asyncio
import time
import json
import re
from datetime import datetime
from aiogram import Bot
from aiogram.types import BufferedInputFile

import database as db
from config import SERVERS, SERVER_REPORT_CHAT_ID, SERVER_REPORT_TOPIC_ID, ALL_ADMIN_IDS
from utils import bot_state
from utils.network_checker import check_server_status, get_server_full_stats, check_node_internet

from utils.server_status_graph import generate_server_status_image

FAILURE_THRESHOLD = 3
RESOURCE_WARNING_THRESHOLD = 90.0 
LAST_ALERT_TIME = {}

async def update_server_statuses_cache(bot: Bot = None):
    server_tasks = []
    for server_id, server_info in SERVERS.items():
        task = asyncio.create_task(
            _get_single_server_status(server_id, server_info, bot)
        )
        server_tasks.append(task)

    results = await asyncio.gather(*server_tasks)
    statuses = [res for res in results if res]

    bot_state.server_statuses_cache = statuses
    bot_state.server_status_last_update = time.time()

async def _get_single_server_status(server_id, server_info, bot: Bot = None):
    is_active_in_settings = bot_state.server_states.get(server_id, True)

    try:
        
        status, ping = await check_server_status(server_info['ip'], server_info.get('check_port', 22))

        if status == 'online':
            if not is_active_in_settings:
                return {
                    "id": server_id, "name": server_info['name'], "status": "online",
                    "cpu": "N/A", "ram": "N/A", "disk": "N/A", "uptime": "N/A", "top_load": "—",
                    "ping": ping, "net": False
                }

            stats, has_net = await asyncio.gather(
                get_server_full_stats(server_id),
                check_node_internet(server_id)
            )

            try:
                cpu_val = float(re.sub(r'[^\d.]', '', stats.get('cpu', '0')))
                if cpu_val > RESOURCE_WARNING_THRESHOLD:
                    await asyncio.sleep(3)
                    stats_retry = await get_server_full_stats(server_id)
                    if stats_retry.get('cpu') != 'Н/Д':
                        stats = stats_retry
            except Exception: pass

            if stats.get('cpu') == 'Н/Д' or stats.get('uptime') == 'Н/Д':
                 await _handle_server_failure(server_id, server_info, is_active_in_settings, bot)
                 return {
                    "id": server_id, "name": server_info['name'], "status": "error",
                    "cpu": "N/A", "ram": "N/A", "disk": "N/A", "uptime": "N/A", "top_load": "Auth Error",
                    "ping": ping, "net": False
                 }

            if bot_state.server_failure_counters.get(server_id, 0) > 0:
                bot_state.server_failure_counters[server_id] = 0

            if bot:
                await _check_resources_and_alert(bot, server_id, server_info['name'], stats)

            return {
                "id": server_id, 
                "name": server_info['name'], 
                "status": status,
                "cpu": stats['cpu'], 
                "ram": stats['ram'], 
                "disk": stats['disk'], 
                "uptime": stats['uptime'],
                "top_load": stats['top_load'],
                "ping": ping,
                "net": has_net
            }
        else:
            if is_active_in_settings:
                await _handle_server_failure(server_id, server_info, is_active_in_settings, bot)

            return {
                "id": server_id, "name": server_info['name'], "status": "offline",
                "cpu": "N/A", "ram": "N/A", "disk": "N/A", "uptime": "N/A",
                "top_load": "—", "ping": "Timeout", "net": False
            }

    except Exception as e:
        if is_active_in_settings:
            await _handle_server_failure(server_id, server_info, is_active_in_settings, bot)
        return {
            "id": server_id, "name": server_info['name'], "status": "error",
            "cpu": "N/A", "ram": "N/A", "disk": "N/A", "uptime": "N/A", "top_load": "—",
            "ping": "Err", "net": False
        }

async def _check_resources_and_alert(bot: Bot, server_id: str, server_name: str, stats: dict):
    global LAST_ALERT_TIME
    try:
        cpu = float(re.sub(r'[^\d.]', '', stats['cpu']))
        ram = float(re.sub(r'[^\d.]', '', stats['ram']))
        disk = float(re.sub(r'[^\d.]', '', stats['disk']))
    except ValueError:
        return

    alerts = []
    if cpu > RESOURCE_WARNING_THRESHOLD: alerts.append(f"🔥 CPU: <b>{cpu}%</b>")
    if ram > RESOURCE_WARNING_THRESHOLD: alerts.append(f"🧠 RAM: <b>{ram}%</b>")
    if disk > 95.0: alerts.append(f"💾 DISK: <b>{disk}%</b>") 

    if not alerts: return

    now = time.time()
    last_alert = LAST_ALERT_TIME.get(server_id, 0)
    if now - last_alert < 1800: return

    LAST_ALERT_TIME[server_id] = now
    alerts_str = "\n".join(alerts)

    alert_text = (
        f"🚨 <b>CRITICAL LOAD WARNING</b>\n\n"
        f"<b>Сервер:</b> {server_name}\n"
        f"{alerts_str}\n\n"
        f"⚠️ <b>Риск падения!</b> Top Load: <code>{stats.get('top_load', 'Unknown')}</code>"
    )

    for admin_id in ALL_ADMIN_IDS:
        try: await bot.send_message(admin_id, alert_text)
        except Exception: pass

    if SERVER_REPORT_CHAT_ID:
        try: await bot.send_message(SERVER_REPORT_CHAT_ID, alert_text, message_thread_id=SERVER_REPORT_TOPIC_ID)
        except Exception: pass

async def _handle_server_failure(server_id: str, server_info: dict, is_active: bool, bot: Bot = None):
    current_fails = bot_state.server_failure_counters.get(server_id, 0) + 1
    bot_state.server_failure_counters[server_id] = current_fails

    if current_fails >= FAILURE_THRESHOLD:
        bot_state.server_states[server_id] = False
        await db.set_bot_setting('server_states', json.dumps(bot_state.server_states))
        await db.update_server_status(server_id, False)

        if server_id in bot_state.servers_cache:
            bot_state.servers_cache[server_id]['active'] = False

        if bot:
            message = (
                f"🚨 <b>СЕРВЕР ОТКЛЮЧЕН (AUTO-BAN)</b>\n\n"
                f"<b>Сервер:</b> {server_info['name']} (<code>{server_id}</code>)\n"
                f"<b>Причина:</b> Недоступен {FAILURE_THRESHOLD} раз подряд."
            )
            for admin_id in ALL_ADMIN_IDS:
                try: await bot.send_message(admin_id, message)
                except Exception: pass

def get_server_report_text(statuses: list) -> str:
    report_lines = [f"📊 <b>Отчет по серверам</b>"]
    report_lines.append(f"🕒 <code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n")

    for server in statuses:
        status_icon = "🟢" if server['status'] == 'online' else "🔴"
        is_active = bot_state.server_states.get(server['id'], True)

        ping_val = server.get('ping', 'N/A')
        ping_text = f"{ping_val}ms" if isinstance(ping_val, int) else ping_val

        net_icon = "🌐 OK" if server.get('net') else "🌐 FAIL"

        if server['status'] == 'online':
            if is_active:
                report_lines.append(f"{status_icon} <b>{server['name']}</b> ({ping_text})")
                report_lines.append(f"├ CPU: {server['cpu']} | RAM: {server['ram']}")
                report_lines.append(f"├ DISK: {server['disk']} | {net_icon}")
                report_lines.append(f"└ Top Load: <code>{server['top_load']}</code>\n")
            else:
                report_lines.append(f"🟠 <b>{server['name']}</b> — DISABLED (Ping: {ping_text})\n")
        else:
            state_mark = "" if is_active else " (DISABLED)"
            fail_count = bot_state.server_failure_counters.get(server['id'], 0)
            fail_text = f"└ Страйков: {fail_count}/{FAILURE_THRESHOLD}\n" if is_active else ""

            report_lines.append(f"{status_icon} <b>{server['name']}</b> — OFFLINE {state_mark}")
            if fail_text: report_lines.append(fail_text)
            else: report_lines.append("\n")

    return "\n".join(report_lines)

async def send_hourly_server_report(bot: Bot):
    if not SERVER_REPORT_CHAT_ID or not SERVER_REPORT_TOPIC_ID:
        return
        
    await update_server_statuses_cache(bot)
    statuses = bot_state.server_statuses_cache
    if not statuses: return

    try:
        
        image_bytes = await asyncio.to_thread(generate_server_status_image, statuses)
        photo_file = BufferedInputFile(image_bytes.read(), filename="server_status.png")
        
        caption = f"📊 <b>Отчет по состоянию системы</b>\n🕒 <code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>"

        await bot.send_photo(
            chat_id=SERVER_REPORT_CHAT_ID,
            message_thread_id=SERVER_REPORT_TOPIC_ID,
            photo=photo_file,
            caption=caption,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить графический отчет по серверам: {e}", exc_info=True)

        try:
            report_text = get_server_report_text(statuses)
            await bot.send_message(
                chat_id=SERVER_REPORT_CHAT_ID,
                message_thread_id=SERVER_REPORT_TOPIC_ID,
                text=report_text,
                parse_mode="HTML"
            )
        except Exception: pass
