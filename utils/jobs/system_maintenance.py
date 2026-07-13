import logging
import asyncio
import zipfile
import os
from datetime import datetime
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile

import database as db
from utils.ssh_runner import run_command_on_server
from config import SERVERS, LOG_CHAT_ID
from ..session_sync import copy_session_from_container
from utils import bot_state
import settings 

DB_BACKUP_TOPIC_KEY = 'db_backup_topic_id'

async def cleanup_notifications_job(bot: Bot):
    """
    Задача для очистки старых уведомлений.
    """
    logging.info("Scheduler: Запущена очистка старых уведомлений...")
    days_to_keep = 14 
    try:
        deleted_count = await db.delete_old_notifications(days_to_keep)
        if deleted_count > 0:
            logging.info(f"Scheduler: Удалено {deleted_count} старых уведомлений (старше {days_to_keep} дней).")
    except Exception as e:
        logging.error(f"Scheduler: Ошибка при очистке уведомлений: {e}")

async def send_db_backup(bot: Bot):
    if not LOG_CHAT_ID:
        logging.warning("Scheduler: LOG_CHAT_ID не задан, бэкап не будет отправлен.")
        return

    logging.info("Scheduler: Запущена задача создания бэкапа БД...")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_filename = f"/tmp/backup_{timestamp}.sql"
    zip_path = f"/tmp/backup_{timestamp}.zip"

    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_user = os.getenv("PG_USER", "postgres")
    pg_pass = os.getenv("PG_PASS", "password")
    pg_name = os.getenv("PG_NAME", "catdock_db")

    topic_id = None
    try:
        topic_id_str = await db.get_bot_setting(DB_BACKUP_TOPIC_KEY)
        if topic_id_str:
            topic_id = int(topic_id_str)

        if not topic_id:
            try:
                new_topic = await bot.create_forum_topic(chat_id=LOG_CHAT_ID, name="DataBase – CatDock")
                topic_id = new_topic.message_thread_id
                await db.set_bot_setting(DB_BACKUP_TOPIC_KEY, str(topic_id))
            except Exception:
                topic_id = None
    except Exception:
        pass

    env = os.environ.copy()
    env["PGPASSWORD"] = pg_pass

    success = False
    error_details = []
    backup_method = "Unknown"

    try:
        with open(backup_filename, 'wb') as f:
            process = await asyncio.create_subprocess_exec(
                'pg_dump', '-h', pg_host, '-p', pg_port, '-U', pg_user, pg_name,
                stdout=f,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            _, stderr = await process.communicate()

        if process.returncode == 0:
            success = True
            backup_method = "System pg_dump"
        else:
            err_str = stderr.decode()
            error_details.append(f"System pg_dump: {err_str}")
            logging.warning(f"Системный pg_dump не справился. Пробую Docker...")

            possible_names = ["catdock_db", "catdock-db-1", "catdock-db"]

            for container_name in possible_names:
                logging.info(f"Попытка бэкапа через контейнер: {container_name}")
                with open(backup_filename, 'wb') as f:
                    process_docker = await asyncio.create_subprocess_exec(
                        'docker', 'exec', container_name, 'pg_dump', '-U', pg_user, pg_name,
                        stdout=f,
                        stderr=asyncio.subprocess.PIPE
                    )
                    _, stderr_docker = await process_docker.communicate()

                if process_docker.returncode == 0:
                    success = True
                    backup_method = f"Docker ({container_name})"
                    logging.info(f"Бэкап через {container_name} прошел успешно.")
                    break
                else:
                    error_details.append(f"Docker {container_name}: {stderr_docker.decode()}")

        if not success:
            full_error = "\n".join(error_details)
            raise Exception(f"Все методы бэкапа провалились.\n{full_error}")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(backup_filename, arcname=os.path.basename(backup_filename))

        document = FSInputFile(zip_path)
        send_kwargs = {
            "chat_id": LOG_CHAT_ID,
            "document": document,
            "caption": f"⚙️ Бэкап PostgreSQL\n<b>Время:</b> <code>{timestamp}</code>\n<i>(Метод: {backup_method})</i>",
            "parse_mode": "HTML"
        }
        if topic_id:
            send_kwargs["message_thread_id"] = topic_id

        try:
            await bot.send_document(**send_kwargs)
            logging.info(f"Бэкап БД отправлен.")
        except TelegramBadRequest as e:
            if "thread not found" in str(e).lower() or "topic not found" in str(e).lower():
                await db.set_bot_setting(DB_BACKUP_TOPIC_KEY, "")
                send_kwargs.pop("message_thread_id", None)
                await bot.send_document(**send_kwargs)
            else:
                raise e

    except Exception as e:
        error_text = f"❌ <b>Ошибка бэкапа:</b>\n<code>{str(e)}</code>"
        logging.error(f"Backup failed: {e}", exc_info=True)
        try:
            await bot.send_message(chat_id=LOG_CHAT_ID, text=error_text, parse_mode="HTML")
        except: pass
    finally:
        if os.path.exists(backup_filename): os.remove(backup_filename)
        if os.path.exists(zip_path): os.remove(zip_path)

async def sync_sessions_to_host(bot: Bot):
    BASE_SESSION_PATH = settings.LOCAL_SESSIONS_DIR 
    if not os.path.exists(BASE_SESSION_PATH):
        os.makedirs(BASE_SESSION_PATH)

    active_containers = await db.get_active_containers()
    if not active_containers:
        return

    for container in active_containers:
        server_id = container['server_id']

        if not bot_state.server_states.get(server_id, True):
            continue

        try:
            find_cmd = f"docker exec {container['container_name']} find /data -name '*.session'"
            result = await run_command_on_server(server_id, find_cmd, check=False)

            if result.exit_status == 0 and result.stdout.strip():
                container_session_path = result.stdout.strip().splitlines()[0]
                user = await bot.get_chat(container['user_id'])
                username = user.username if user.username else str(user.id)
                local_user_dir = os.path.join(BASE_SESSION_PATH, f"{username}Session")
                if not os.path.exists(local_user_dir): os.makedirs(local_user_dir)
                local_session_path = os.path.join(local_user_dir, f"{container['container_name']}.session")

                await copy_session_from_container(
                    server_id=server_id,
                    container_name=container['container_name'],
                    container_session_path=container_session_path,
                    local_destination_path=local_session_path
                )
                await asyncio.sleep(1)
        except Exception:
            pass
