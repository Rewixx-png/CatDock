from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

import database as db
from utils import bot_state 
from lexicon import LEXICON

class BlockMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User | None = data.get('event_from_user')

        if not user or user.id in bot_state.admin_ids_cache:
            return await handler(event, data)

        if await db.is_user_blocked(user.id):
            language_code = await db.get_user_language(user.id) or 'ru'
            lex = LEXICON[language_code]

            if hasattr(event, 'answer'):
                await event.answer(
                    lex.get('user_blocked_notification', "Вы были заблокированы администратором."),
                    show_alert=True
                )
            elif hasattr(event, 'reply'):
                 await event.reply(
                    lex.get('user_blocked_notification', "Вы были заблокированы администратором.")
                )
            return
        return await handler(event, data)
