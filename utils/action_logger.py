import logging
import asyncio
import html
from datetime import datetime
from aiogram import Bot
from aiogram.types import User
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

import database as db
from config import LOG_CHAT_ID

topic_cache = {}

async def log_action(
    bot: Bot, 
    actor: User, 
    action: str, 
    target_user: User | None = None,
    log_type: str = "general",
    db_only: bool = False  
):
    effective_user = target_user if target_user else actor

    actor_id = actor.id
    target_id = target_user.id if target_user else None

    is_admin_action = (target_id is not None and actor_id != target_id)

    asyncio.create_task(db.add_system_log(
        actor_id=actor_id,
        target_id=target_id,
        action_type=log_type,
        message=action,
        is_admin_action=is_admin_action
    ))

    if db_only:
        return

    if not LOG_CHAT_ID:
        return

    user_id = effective_user.id
    
    raw_username = effective_user.username or ""

    first_name = effective_user.full_name

    topic_id = topic_cache.get(user_id)
    if not topic_id:
        topic_id = await db.get_log_topic_id(user_id)
        if topic_id:
            topic_cache[user_id] = topic_id

    try:
        
        if not topic_id:
            topic_name = f"@{raw_username}" if raw_username else str(user_id)

            for _ in range(3): 
                try:
                    new_topic = await bot.create_forum_topic(chat_id=LOG_CHAT_ID, name=topic_name)
                    topic_id = new_topic.message_thread_id
                    await db.set_log_topic_id(user_id, topic_id)
                    topic_cache[user_id] = topic_id

                    safe_first_name = html.escape(first_name)
                    safe_username = html.escape(raw_username) if raw_username else 'N/A'

                    profile_info = (
                        f"<b>Пользователь:</b> {safe_first_name}\n"
                        f"<b>ID:</b> <code>{user_id}</code>\n"
                        f"<b>Username:</b> @{safe_username}\n"
                        f"<b>Дата регистрации:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    )
                    await bot.send_message(
                        chat_id=LOG_CHAT_ID,
                        message_thread_id=topic_id,
                        text=f"✅ Создан лог-топик для пользователя.\n\n{profile_info}"
                    )
                    break
                except TelegramRetryAfter as e:
                    logging.warning(f"⏳ FloodWait при создании топика: {e.retry_after}s")
                    await asyncio.sleep(e.retry_after + 1)
                except Exception as e:
                    logging.error(f"Не удалось создать топик: {e}")
                    break

        if not topic_id:
            return

        timestamp = datetime.now().strftime('%H:%M:%S')

        safe_actor_name = html.escape(actor.username or str(actor.id))

        if is_admin_action:
            log_message = (
                f"👑 <b>[АДМИН]</b> {timestamp}\n"
                f"<b>Администратор:</b> @{safe_actor_name}\n"
                f"<b>Действие:</b> {action}"
            )
        else:
            log_message = f"👤 <b>[USER]</b> {timestamp}\n{action}"

        for attempt in range(5):
            try:
                await bot.send_message(
                    chat_id=LOG_CHAT_ID,
                    message_thread_id=topic_id,
                    text=log_message,
                    parse_mode="HTML"
                )
                break 
            except TelegramRetryAfter as e:
                wait_time = e.retry_after + 1
                if wait_time > 30: 
                    logging.error(f"Log skip: FloodWait too long ({wait_time}s)")
                    break
                logging.warning(f"⏳ Log FloodWait: sleep {wait_time}s")
                await asyncio.sleep(wait_time)
            except TelegramBadRequest as e:
                
                if "forum topic not found" in str(e).lower() or "thread not found" in str(e).lower():
                    logging.warning(f"Топик {topic_id} не найден. Сброс.")
                    topic_cache.pop(user_id, None)
                    await db.set_log_topic_id(user_id, None)
                else:
                    logging.error(f"TelegramBadRequest при отправке лога: {e} | Text: {log_message}")
                break
            except Exception as e:
                logging.error(f"Ошибка отправки лога: {e}")
                break

    except Exception as e:
        logging.error(f"Критическая ошибка в логгере: {e}", exc_info=True)
