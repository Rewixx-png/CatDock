import asyncio
import logging
import traceback
import os
import aiofiles
import asyncssh
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import User, FSInputFile

from broker import broker
from config import TOKEN, SERVERS, TARIFFS, IMAGES, WEB_APP_URL, PROJECT_ROOT, DEFAULT_CPU_LIMIT
import utils.docker as dm
from utils.action_logger import log_action

from lexicon import LEXICON
from utils.ssh_runner import _get_ssh_connection, run_command_on_server
from utils.docker.compose_generator import generate_compose_config

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def safe_send_message(chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logging.warning(f"Worker failed to send message to {chat_id}: {e}")

@broker.task
async def task_container_power_action(chat_id: int, user_id: int, first_name: str, username: str, action: str, server_id: str, container_name: str):
    import database as db
    logging.info(f"👷 TASK POWER: {action} {container_name}")

    action_map = {'start': dm.start_container, 'stop': dm.stop_container, 'restart': dm.restart_container}
    ui_map = {'start': '✅ Запущен', 'stop': '🛑 Остановлен', 'restart': '🔄 Перезагружен'}

    try:
        if action not in action_map: raise ValueError(f"Unknown action: {action}")

        container = await db.get_container_by_name(container_name)
        cpu_limit = container.get('cpu_limit', DEFAULT_CPU_LIMIT) if container else DEFAULT_CPU_LIMIT

        if action in ['start', 'restart']:
            try:
                await dm.run_command_on_server(server_id, f"docker update --cpus=\"2.0\" {container_name}", check=False)
            except Exception as e:
                logging.warning(f"Boost pre-update failed: {e}")

        await action_map[action](server_id, container_name)

        if action in ['start', 'restart']:
            await asyncio.sleep(20) 

            try:
                await dm.run_command_on_server(server_id, f"docker update --cpus=\"{cpu_limit}\" {container_name}", check=False)
                logging.info(f"Reverted CPU limit for {container_name} to {cpu_limit}")
            except Exception as e:
                logging.error(f"Failed to revert CPU limit for {container_name}: {e}")

        user_obj = User(id=user_id, is_bot=False, first_name=first_name, username=username)
        await log_action(bot, user_obj, f"выполнил действие '{action}' (через очередь) для '{container_name}'")

        await safe_send_message(chat_id, f"🐳 <b>UserBot {container_name}:</b>\n{ui_map.get(action, 'Готово')} успешно!")

    except Exception as e:
        logging.error(f"👷 POWER FAILED: {e}")
        await safe_send_message(chat_id, f"❌ <b>Ошибка действия {action}:</b>\n<code>{str(e)}</code>")

@broker.task
async def task_create_container(user_id: int, username: str, first_name: str, server_id: str, tariff_id: str, image_id: str, cost: float, days: int, promo_used: str | None = None, promo_code: str | None = None):
    import database as db
    logging.info(f"👷 TASK CREATE: User {user_id}, Server {server_id}, Tariff {tariff_id}")
    try:
        tariff = TARIFFS[tariff_id]
        image = IMAGES[image_id]
        container_name, app_port, login_url = await dm.create_container(user_id, username, server_id, tariff, image)
        if not all([container_name, app_port, login_url]): raise Exception("Docker Manager returned empty data")
        tariff_id_db = 'free' if promo_used == 'free_container' else tariff_id
        await db.add_user_container(user_id, server_id, container_name, image_id, tariff_id_db, app_port, login_url)
        if days != 30:
            container = await db.get_container_by_name(container_name)
            await db.admin_set_container_time(container['id'], days)
        user_obj = User(id=user_id, is_bot=False, first_name=first_name, username=username)
        await log_action(bot, user_obj, f"создал контейнер '{container_name}' (Queue). Списано: {cost:.2f} RUB")
        await safe_send_message(user_id, f"✅ <b>Готово! Ваш UserBot создан.</b>\n\n📦 <b>Имя:</b> <code>{container_name}</code>\n🌍 <b>Сервер:</b> {SERVERS[server_id]['name']}\n\n⏳ <b>Инициализация Web-панели...</b>\nБот уведомит вас, когда панель загрузится (10-30 сек).\nНайти бота можно в меню <b>'Мои UserBot'</b>.")
    except Exception as e:
        error_msg = str(e)
        logging.error(f"👷 CREATE FAILED: {error_msg}", exc_info=True)
        if cost > 0: await db.update_user_balance(user_id, cost)
        if promo_used == 'free_container' and promo_code: await db.set_user_free_container_promo(user_id, True, promo_code)
        await safe_send_message(user_id, f"❌ <b>Ошибка при создании контейнера</b>\n\n<code>{error_msg}</code>\n\n💰 Средства ({cost:.2f} RUB) возвращены на баланс.\nПопробуйте позже или обратитесь в поддержку.")

@broker.task
async def task_reinstall_container(chat_id: int, user_id: int, first_name: str, container_db_id: int, server_id: str, old_container_name: str, tariff_data: dict, image_data: dict, username_for_create: str):
    import database as db
    logging.info(f"👷 TASK REINSTALL: {old_container_name} (ID: {container_db_id})")
    try:
        try: await bot.send_message(chat_id, "⏳ <b>Процесс запущен:</b>\n1. Удаление старого...\n2. Сборка нового...\n<i>Это займет 10-30 секунд.</i>")
        except: pass

        try: await dm.delete_container(server_id, old_container_name)
        except Exception as e: logging.warning(f"Reinstall: Old container delete failed (non-critical): {e}")

        new_name, new_port, login_url = await dm.create_container(user_id, username_for_create, server_id, tariff_data, image_data)
        if not new_name: raise Exception("Docker create failed")

        await db.update_container_server(container_db_id, server_id, new_port, new_name, login_url)
        await db.set_container_frozen_state(container_db_id, False)
        try: await db.set_container_login_pending(container_db_id, False)
        except: pass
        await db.set_container_web_loading(container_db_id, True)

        user_obj = User(id=user_id, is_bot=False, first_name=first_name)
        await log_action(bot, user_obj, f"переустановил контейнер (Queue). Новое имя: {new_name}")
        await safe_send_message(chat_id, f"✅ <b>Переустановка завершена!</b>\n\nНовое имя: <code>{new_name}</code>\nВеб-панель загружается...")
    except Exception as e:
        logging.error(f"Reinstall Task Error: {e}", exc_info=True)
        await safe_send_message(chat_id, f"❌ Ошибка переустановки: {e}")

@broker.task
async def task_delete_container(chat_id: int, user_id: int, first_name: str, container_id: int, server_id: str, container_name: str):
    import database as db
    logging.info(f"👷 TASK DELETE: {container_name}")
    try:
        if server_id in SERVERS:
            try: await dm.delete_container(server_id, container_name)
            except Exception as e: logging.warning(f"Delete Task: Docker removal failed: {e}")
        await db.delete_user_container(container_id)
        user_obj = User(id=user_id, is_bot=False, first_name=first_name)
        await log_action(bot, user_obj, f"удалил контейнер '{container_name}' (Queue)")
        await safe_send_message(chat_id, f"✅ Контейнер <b>{container_name}</b> успешно удален.")
    except Exception as e:
        logging.error(f"Delete Task Error: {e}")
        await safe_send_message(chat_id, f"❌ Ошибка удаления: {e}")

@broker.task
async def task_change_image(chat_id: int, user_id: int, first_name: str, container_id: int, server_id: str, container_name: str, old_image_name: str, new_image_id: str, tariff_id: str, external_port: int):
    import database as db
    logging.info(f"👷 TASK CHANGE IMAGE: {container_name} -> {new_image_id}")
    try:
        tariff = TARIFFS[tariff_id]
        new_image_data = IMAGES[new_image_id]
        ram_mb = tariff.get('ram_mb', 300)

        container_dir = f"/var/lib/catdock/containers/{container_name}"

        from utils.docker.lifecycle import IMAGE_FIXES
        img_name_lower = new_image_data['image_name'].lower()
        fix_config = {}
        for key, conf in IMAGE_FIXES.items():
            if key in img_name_lower:
                fix_config = conf
                break

        new_config = generate_compose_config(
            container_name=container_name,
            image_name=new_image_data['image_name'],
            port=external_port,
            mem_limit=ram_mb,
            cpu_limit="0.2",
            command=fix_config.get('command'),
            working_dir=fix_config.get('working_dir')
        )

        write_cmd = f"cat > {container_dir}/docker-compose.yml << 'EOF'\n{new_config}\nEOF"
        await run_command_on_server(server_id, write_cmd)

        up_cmd = f"cd {container_dir} && docker compose up -d --remove-orphans"
        await run_command_on_server(server_id, up_cmd)

        await db.update_container_image(container_id, new_image_id)

        new_image_display = new_image_data['name']
        user_obj = User(id=user_id, is_bot=False, first_name=first_name)
        await log_action(bot, user_obj, f"сменил образ контейнера на {new_image_display} (Queue)")
        await safe_send_message(chat_id, f"✅ <b>Образ изменен!</b>\n\nКонтейнер: <b>{container_name}</b>\nНовый образ: <b>{new_image_display}</b>\n\nСистема обновлена.")
    except Exception as e:
        logging.error(f"Change Image Error: {e}", exc_info=True)
        await safe_send_message(chat_id, f"❌ Ошибка смены образа: {e}")

@broker.task
async def task_change_server(chat_id: int, user_id: int, username: str, first_name: str, container_id: int, old_server_id: str, old_container_name: str, new_server_id: str, tariff_id: str, image_id: str):
    import database as db
    logging.info(f"👷 TASK MOVE: {old_container_name} -> {new_server_id}")
    try:
        tariff = TARIFFS[tariff_id]
        image = IMAGES[image_id]
        new_name, new_port, login_url = await dm.create_container(user_id, username, new_server_id, tariff, image, forced_name=old_container_name)
        if not new_name: raise Exception("Failed to create container on new server")

        if old_server_id in SERVERS:
            try: await dm.delete_container(old_server_id, old_container_name)
            except Exception as e: logging.warning(f"Move Task: Failed to delete old container: {e}")

        await db.update_container_server(container_id, new_server_id, new_port, new_name, login_url)
        server_name = SERVERS[new_server_id]['name']
        user_obj = User(id=user_id, is_bot=False, first_name=first_name)
        await log_action(bot, user_obj, f"перенес контейнер на сервер {server_name} (Queue)")
        await safe_send_message(chat_id, f"✅ <b>Переезд завершен!</b>\n\nКонтейнер: <b>{new_name}</b>\nНовый сервер: <b>{server_name}</b>\nСтатус: Активен")
    except Exception as e:
        logging.error(f"Move Task Error: {e}", exc_info=True)
        await safe_send_message(chat_id, f"❌ Ошибка переезда: {e}")

@broker.task
async def task_backup_modules(user_id: int, container_id: int, server_id: str, container_name: str, filenames: list[str]):
    import database as db
    logging.info(f"👷 TASK BACKUP MODULES: {len(filenames)} files from {container_name}")
    saved_count = 0
    errors = 0
    try:
        storage_dir = os.path.join(PROJECT_ROOT, 'storage', 'modules', str(user_id))
        os.makedirs(storage_dir, exist_ok=True)
        target_path_in_container = "/data/loaded_modules"
        for fname in filenames:
            safe_fname = os.path.basename(fname)
            if not safe_fname.endswith('.py'): continue
            full_remote_path = f"{target_path_in_container}/{safe_fname}"
            content = await dm.read_file_from_container(server_id, container_name, full_remote_path)
            if content:
                local_path = os.path.join(storage_dir, safe_fname)
                async with aiofiles.open(local_path, 'wb') as f: await f.write(content)
                await db.add_user_module(user_id, safe_fname, local_path, len(content))
                saved_count += 1
            else: errors += 1
        if saved_count > 0: await safe_send_message(user_id, f"💾 <b>Бэкап завершен!</b>\nСохранено модулей: {saved_count}\nОшибок: {errors}\n\nТеперь они доступны в Профиле -> Мои модули.")
        else: await safe_send_message(user_id, "⚠️ Не удалось сохранить выбранные модули (возможно, они були удалены или пусты).")
    except Exception as e:
        logging.error(f"Backup Modules Failed: {e}", exc_info=True)
        await safe_send_message(user_id, f"❌ Ошибка бэкапа: {e}")

@broker.task
async def task_send_modules(user_id: int, module_ids: list[int]):
    import database as db
    logging.info(f"👷 TASK SEND MODULES: {len(module_ids)} files to {user_id}")
    sent_count = 0
    try:
        for mid in module_ids:
            module = await db.get_module_by_id(mid)
            if not module: continue
            path = module['local_path']
            if not os.path.exists(path):
                await safe_send_message(user_id, f"⚠️ Файл {module['filename']} потерян на диске.")
                continue
            input_file = FSInputFile(path, filename=module['filename'])
            caption = f"📂 <b>{module['filename']}</b>\n💾 Сохранен: {module['saved_at'].strftime('%d.%m.%Y')}\n\nℹ️ <b>Как установить:</b>\nНапишите <code>.lm</code> в ответ на этот файл в чате с ботом (или в избранном)."
            try:
                await bot.send_document(user_id, input_file, caption=caption)
                sent_count += 1
                await asyncio.sleep(0.5)
            except Exception as e: logging.error(f"Failed to send module {mid}: {e}")
        if sent_count > 0: await safe_send_message(user_id, f"✅ Отправлено файлов: {sent_count}")
    except Exception as e: logging.error(f"Send Modules Task Failed: {e}")

@broker.task
async def task_create_full_backup(user_id: int, container_id: int, server_id: str, container_name: str, tariff_id: str):
    import database as db
    logging.info(f"👷 TASK FULL BACKUP: {container_name}")

    container_dir = f"/var/lib/catdock/containers/{container_name}"

    try:
        await safe_send_message(user_id, "⏳ <b>Бэкап начат...</b>\nОстанавливаю бота для безопасного копирования...")
        await dm.stop_container(server_id, container_name)

        await run_command_on_server(server_id, f"cd {container_dir} && tar czf /tmp/{container_name}_backup.tar.gz data")

        local_storage_dir = os.path.join(PROJECT_ROOT, 'storage', 'backups', str(user_id))
        os.makedirs(local_storage_dir, exist_ok=True)
        local_path = os.path.join(local_storage_dir, f"{tariff_id}_data.tar.gz")

        async with await _get_ssh_connection(server_id) as conn:
             await asyncssh.scp((conn, f"/tmp/{container_name}_backup.tar.gz"), local_path)

        await run_command_on_server(server_id, f"rm -f /tmp/{container_name}_backup.tar.gz")
        await dm.start_container(server_id, container_name)

        file_size = os.path.getsize(local_path)
        await db.save_backup_record(user_id, tariff_id, local_path, file_size)

        size_mb = file_size / (1024 * 1024)
        await safe_send_message(user_id, f"✅ <b>Полный бэкап создан!</b>\n\nРазмер: {size_mb:.2f} MB\nСохранено: Сессии, Конфиги, Модули, БД.\n\nТеперь вы можете нажать <b>'Восстановить'</b> после переустановки.")
    except Exception as e:
        logging.error(f"Full Backup Failed: {e}", exc_info=True)
        await safe_send_message(user_id, f"❌ Ошибка бэкапа: {e}")
        try: await dm.start_container(server_id, container_name)
        except: pass

@broker.task
async def task_restore_full_backup(user_id: int, container_id: int, server_id: str, container_name: str, backup_path: str):
    import database as db
    logging.info(f"👷 TASK RESTORE BACKUP: {container_name}")
    if not os.path.exists(backup_path):
        await safe_send_message(user_id, "❌ Файл бэкапа не найден на сервере.")
        return

    container_dir = f"/var/lib/catdock/containers/{container_name}"

    try:
        await safe_send_message(user_id, "⏳ <b>Восстановление...</b>\nОстанавливаю бота и загружаю данные...")
        await dm.stop_container(server_id, container_name)
        remote_tar_name = f"{container_name}_restore.tar.gz"

        async with await _get_ssh_connection(server_id) as conn:
             await asyncssh.scp(backup_path, (conn, f"/tmp/{remote_tar_name}"))

        await run_command_on_server(server_id, f"rm -rf {container_dir}/data/*")

        await run_command_on_server(server_id, f"tar xzf /tmp/{remote_tar_name} -C {container_dir}")

        await run_command_on_server(server_id, f"rm -f /tmp/{remote_tar_name}")

        await dm.start_container(server_id, container_name)

        await safe_send_message(user_id, f"✅ <b>Данные восстановлены!</b>\n\nВаш бот (Сессии, Модули, Конфиги) снова в строю.\nМожете проверять.")
    except Exception as e:
        logging.error(f"Restore Failed: {e}", exc_info=True)
        await safe_send_message(user_id, f"❌ Ошибка восстановления: {e}")
        try: await dm.start_container(server_id, container_name)
        except: pass
