from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

from config import INFO_CHAT_ID, MODERATION_CHAT_ID
from utils.leveling import is_message_abuse, process_chat_xp
import database as db

class LevelingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:

        if event.chat.type in ['group', 'supergroup'] and event.text and not event.text.startswith('/'):

            user_id = event.from_user.id

            if not is_message_abuse(user_id, event.text):
                await process_chat_xp(
                    bot=data['bot'],
                    user_id=user_id,
                    message_id=event.message_id,
                    chat_id=event.chat.id
                )

        return await handler(event, data)
