from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from utils.action_logger import log_action

class GlobalLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:

        user = data.get('event_from_user')
        bot = data.get('bot')

        if user:
            log_text = None

            if isinstance(event, CallbackQuery):
                if not event.data.startswith(('logs_page', 'users_page')):
                    log_text = f"🔘 Нажал кнопку: <code>{event.data}</code>"

            elif isinstance(event, Message) and event.text:
                log_text = f"⌨️ Написал: «{event.text}»"

            if log_text:
                await log_action(bot, user, log_text, log_type="interaction", db_only=True)

        return await handler(event, data)
