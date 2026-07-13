import time
import logging
import difflib
from aiogram import Bot
from config import INFO_CHAT_ID
import settings
import database as db
from utils import bot_state
from aiogram.exceptions import TelegramBadRequest

def get_xp_threshold(level: int) -> int:
    return int(100 * (level ** 1.5))

def is_message_abuse(user_id: int, text: str) -> bool:
    now = time.time()

    if len(text.strip()) < settings.LEVEL_MIN_MSG_LEN:
        return True

    user_cache = bot_state.anti_abuse_cache.get(user_id, {})
    last_time = user_cache.get('last_msg_time', 0)
    last_text = user_cache.get('last_msg_text', "")

    if now - last_time < settings.LEVEL_CHAT_COOLDOWN:
        return True

    if last_text:
        similarity = difflib.SequenceMatcher(None, text.lower(), last_text.lower()).ratio()
        if similarity > 0.8:
            return True

    bot_state.anti_abuse_cache[user_id] = {
        'last_msg_time': now,
        'last_msg_text': text
    }

    return False

async def process_chat_xp(bot: Bot, user_id: int, message_id: int, chat_id: int):
    new_level, new_xp, is_level_up = await db.add_user_xp(user_id, settings.LEVEL_XP_PER_MESSAGE)

    if is_level_up:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"🎉 <b>Level Up!</b>\nПользователь поднял уровень до <b>{new_level}</b>! 🆙\nБольше скидок, больше бонусов!",
                reply_to_message_id=message_id
            )
        except TelegramBadRequest:
            pass

async def process_spending_xp(bot: Bot, user_id: int, amount_rub: float):
    if amount_rub <= 0: return

    xp_amount = int(amount_rub * settings.LEVEL_XP_PER_RUBLE)
    new_level, new_xp, is_level_up = await db.add_user_xp(user_id, xp_amount)

    if is_level_up:
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Поздравляем! Новый уровень: {new_level}</b>\n\n"
                f"Ваша постоянная скидка увеличилась!\n"
                f"Шанс на редкий дроп в ежедневном бонусе повышен."
            )
        except Exception:
            pass
