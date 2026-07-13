import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Awaitable, List
from collections import defaultdict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, ChatPermissions
from aiogram.utils.markdown import hlink
from aiogram.exceptions import TelegramBadRequest

from config import MODERATION_CHAT_ID
from lexicon import LEXICON
import database as db

user_requests: Dict[int, List[float]] = defaultdict(list)

TIME_WINDOW = 5  
MESSAGE_LIMIT = 5  

class AntiFloodMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:

        if not isinstance(event, Message) or event.chat.id != MODERATION_CHAT_ID:
            return await handler(event, data)

        logging.info(f"ANTIFLOOD: Получено сообщение от {event.from_user.id} в чате {event.chat.id}")

        user_id = event.from_user.id
        bot: Bot = data['bot']

        admin_ids = db.get_admin_ids()
        if user_id in admin_ids:
            logging.info(f"ANTIFLOOD: Пользователь {user_id} является админом, пропускаем проверку.")
            return await handler(event, data)

        current_time = time.time()

        user_requests[user_id] = [t for t in user_requests[user_id] if current_time - t < TIME_WINDOW]

        user_requests[user_id].append(current_time)

        logging.info(f"ANTIFLOOD: Пользователь {user_id} отправил {len(user_requests[user_id])}/{MESSAGE_LIMIT} сообщений.")

        if len(user_requests[user_id]) > MESSAGE_LIMIT:
            user_requests[user_id] = []
            logging.warning(f"ANTIFLOOD: Обнаружен флуд от пользователя {user_id}. Пытаюсь выдать мут.")

            mute_duration = timedelta(minutes=10)
            until_date = datetime.now() + mute_duration

            try:
                await bot.restrict_chat_member(
                    chat_id=MODERATION_CHAT_ID,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until_date
                )

                language_code = db.get_user_language(user_id) or 'ru'
                lex = LEXICON[language_code]

                user_link = hlink(event.from_user.full_name, f"tg://user?id={user_id}")

                flood_message = lex.get('flood_mute_message', 
                                        "<b>{user_link}</b> получил(а) мут на <b>10 минут</b>.\n"
                                        "<b>Причина:</b> Флуд.\n\n"
                                        "<i>Выдано автоматически ботом.</i>").format(user_link=user_link)

                await event.answer(flood_message, disable_web_page_preview=True)
                logging.info(f"ANTIFLOOD: Пользователь {user_id} успешно замучен за флуд.")

            except TelegramBadRequest as e:
                logging.error(f"ANTIFLOOD: Не удалось замутить пользователя {user_id} за флуд: {e}")
            return

        return await handler(event, data)
