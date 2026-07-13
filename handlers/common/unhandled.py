import logging
import html
import json
from aiogram import Router, Bot, types
from aiogram.exceptions import TelegramBadRequest

from utils import bot_state
from config import LOG_CHAT_ID

router = Router()

async def report_unhandled(event_type: str, user: types.User | None, chat: types.Chat | None, raw_data: str | None, bot: Bot):
    if user and user.is_bot:
        return

    user_info = f"{html.escape(user.full_name)} (@{user.username or 'N/A'}) [<code>{user.id}</code>]" if user else "Неизвестно"
    chat_info = f"{html.escape(chat.title or 'ЛС')} [<code>{chat.id}</code>]" if chat else "Неизвестно"

    safe_data = html.escape(str(raw_data))

    text = (
        f"⚠️ <b>UNHANDLED UPDATE</b>\n\n"
        f"<b>Событие:</b> <code>{event_type}</code>\n"
        f"<b>Юзер:</b> {user_info}\n"
        f"<b>Чат:</b> {chat_info}\n"
        f"<b>Содержимое:</b>\n<pre>{safe_data}</pre>\n"
    )

    targets = []
    if LOG_CHAT_ID:
        targets.append(LOG_CHAT_ID)
    else:
        targets = list(bot_state.admin_ids_cache)

    for target in targets:
        try:
            await bot.send_message(target, text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"CRITICAL: Не удалось отправить отчет об UNHANDLED событии админу {target}. Ошибка: {e}")

@router.callback_query()
async def unhandled_callback(callback: types.CallbackQuery, bot: Bot):
    try:
        await callback.answer("⚠️ Действие устарело или недоступно.", show_alert=True)
    except TelegramBadRequest:
        pass
    except Exception:
        pass

    await report_unhandled(
        "CallbackQuery", 
        callback.from_user, 
        callback.message.chat if callback.message else None, 
        callback.data, 
        bot
    )

@router.message()
async def unhandled_message(message: types.Message, bot: Bot):
    if message.chat.type in ['group', 'supergroup']:
        return

    if message.text and message.text.startswith('/'):
        return

    await report_unhandled(
        "Message", 
        message.from_user, 
        message.chat, 
        message.text or message.caption or "[Media]", 
        bot
    )
