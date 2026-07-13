import logging
import asyncio
import re
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
import utils.docker as dm
from utils.ssh_runner import run_command_on_server
from config import SERVERS, LOG_CHAT_ID, ALL_ADMIN_IDS
from utils.action_logger import log_action
import settings
from utils import bot_state
from lexicon import LEXICON

async def check_web_loading_status(bot: Bot):
    loading_containers = await db.get_containers_loading_web()
    if not loading_containers:
        return

    target_phrase = "Web mode ready for configuration"
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    for container in loading_containers:
        try:
            logs_raw = await dm.get_container_logs(container['server_id'], container['container_name'], lines=50)
            if not logs_raw: continue

            clean_logs = ansi_escape.sub('', logs_raw)

            if target_phrase in clean_logs:
                await db.set_container_web_loading(container['id'], False)

                try:
                    await bot.send_message(
                        container['user_id'],
                        f"✅ <b>Web-интерфейс загружен!</b>\n\n"
                        f"Ваш бот <b>{container['container_name']}</b> готов к настройке.\n"
                        f"🔗 Переходите по ссылке: {container['login_url']}"
                    )
                except Exception:
                    pass

        except Exception as e:
            logging.error(f"Ошибка проверки веба для {container['container_name']}: {e}")

async def tick_containers(bot: Bot):
    active_containers = await db.get_active_containers()
    if not active_containers:
        return

    container_ids_to_tick = [c['id'] for c in active_containers]
    await db.update_containers_time(container_ids_to_tick, 60)

    for container in active_containers:
        if container['remaining_seconds'] - 60 <= 0:
            logging.warning(f"Scheduler: Время контейнера {container['container_name']} (ID: {container['id']}) истекло. Удаляем.")
            try:
                await dm.delete_container(container['server_id'], container['container_name'])
                await db.delete_user_container(container['id'])
                await bot.send_message(
                    container['user_id'],
                    f"❗️ Срок аренды вашего UserBot'а <b>{container['container_name']}</b> истёк, и он был автоматически удален."
                )
            except Exception as e:
                logging.error(f"Scheduler: Ошибка при удалении истекшего контейнера {container['id']}: {e}")

async def sync_frozen_containers_state(bot: Bot):
    frozen_containers = await db.get_frozen_containers()
    if not frozen_containers:
        return

    for container in frozen_containers:
        try:
            status = await dm.get_container_status(container['server_id'], container['container_name'])
            if status == 'running':
                logging.warning(
                    f"Scheduler: Обнаружен работающий замороженный контейнер "
                    f"{container['container_name']} (ID: {container['id']}). Принудительно останавливаю."
                )
                await dm.stop_container(container['server_id'], container['container_name'])
        except Exception:
            pass

async def cleanup_old_container_logs():
    logging.info("Scheduler: Запущена очистка логов старых контейнеров...")
    for server_id, server_info in SERVERS.items():
        try:
            command = "docker ps -a --filter 'name=cat-*' -q | xargs -r docker inspect --format='{{.LogPath}}' | xargs -r truncate -s 0"
            await run_command_on_server(server_id, command)
        except Exception as e:
            logging.error(f"Scheduler: Не удалось очистить логи на сервере {server_id}. Ошибка: {e}")

async def check_expiring_containers(bot: Bot):
    expiring_soon = await db.get_expiring_containers([1, 3])
    if not expiring_soon:
        return

    for container in expiring_soon:
        user_id = container['user_id']
        remaining_seconds = container['remaining_seconds']
        days = round(remaining_seconds / 86400)

        last_notification_days = container.get('last_notification_days', 0)
        if last_notification_days == days:
            continue

        try:
            await bot.send_message(
                user_id,
                f"🔔 <b>Напоминание</b>\n\nСрок аренды вашего UserBot'а "
                f"<b>{container['container_name']}</b> истекает примерно через <b>{days} дня(дней)</b>.\n\n"
                f"Не забудьте продлить его в меню 'Мои UserBot', чтобы не потерять данные."
            )
            await db.update_container_last_notification(container['id'], days)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        except Exception as e:
            logging.error(f"Непредвиденная ошибка при отправке уведомления пользователю {user_id}: {e}")

async def check_restart_loops(bot: Bot):
    """
    Мониторинг контейнеров, застрявших в цикле перезагрузки (Boot Loop).
    Если контейнер находится в статусе 'restarting' более 5 проверок подряд (5 минут),
    он принудительно останавливается.
    """
    
    RESTART_THRESHOLD = 5

    for server_id, server_info in SERVERS.items():
        if not bot_state.server_states.get(server_id, True):
            continue

        try:
            
            cmd = "docker ps --filter 'status=restarting' --filter 'name=cat-' --format '{{.Names}}'"
            result = await run_command_on_server(server_id, cmd, check=False, timeout=10)
            
            if result.exit_status != 0:
                continue

            current_restarting = set(result.stdout.strip().split()) if result.stdout else set()

            for container_name in current_restarting:
                count = bot_state.container_restart_counters.get(container_name, 0) + 1
                bot_state.container_restart_counters[container_name] = count

                logging.warning(f"⚠️ [BootLoop] Контейнер {container_name} (srv: {server_id}) рестартится ({count}/{RESTART_THRESHOLD})")

                if count >= RESTART_THRESHOLD:
                    logging.error(f"🚨 [BootLoop] Контейнер {container_name} превысил лимит рестартов. Остановка...")

                    await dm.stop_container(server_id, container_name)

                    bot_state.container_restart_counters.pop(container_name, None)

                    container_db = await db.get_container_by_name(container_name)
                    if container_db:
                        
                        await db.set_container_frozen_state(container_db['id'], True)
                        
                        user_id = container_db['user_id']

                        try:
                            lang = await db.get_user_language(user_id) or 'ru'
                            
                            text = (
                                f"⛔️ <b>Ваш UserBot остановлен!</b>\n\n"
                                f"Контейнер <b>{container_name}</b> вошел в бесконечный цикл перезагрузки (Boot Loop).\n"
                                f"Это часто случается из-за ошибок в коде модулей или нехватки памяти.\n\n"
                                f"✅ Бот был остановлен для защиты данных.\n"
                                f"🛠 <b>Решение:</b> Проверьте логи через меню и устраните ошибку перед запуском."
                            )
                            await bot.send_message(user_id, text)
                        except Exception:
                            pass

                        if LOG_CHAT_ID:
                             await bot.send_message(
                                 LOG_CHAT_ID,
                                 f"🚨 <b>AUTO-STOP (BootLoop)</b>\n"
                                 f"Контейнер: <code>{container_name}</code>\n"
                                 f"Сервер: {server_info['name']}\n"
                                 f"User ID: {user_id}\n"
                                 f"Причина: {RESTART_THRESHOLD} минут в статусе Restarting."
                             )

            tracked_containers = list(bot_state.container_restart_counters.keys())
            
            for name in tracked_containers:

                pass

        except Exception as e:
            logging.error(f"Check Restart Loops Error on {server_id}: {e}")
