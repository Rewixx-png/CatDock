from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from utils import bot_state

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not bot_state.maintenance_mode:
            return await handler(event, data)

        user: User | None = data.get('event_from_user')
        if not user or user.id not in bot_state.admin_ids_cache:
            if hasattr(event, "answer"):
                await event.answer("🔧 Бот на технических работах. Пожалуйста, зайдите позже.", show_alert=True)
            return

        return await handler(event, data)
