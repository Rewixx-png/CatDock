import asyncio
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from config import ALL_ADMIN_IDS, ADMIN_LEVELS
from roles import UserRole
import database as db
from utils import bot_state

class IsAdmin(BaseFilter):
    def __init__(self, min_level: UserRole):
        self.min_level = min_level

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id

        if user_id not in bot_state.admin_ids_cache:
            return False

        user_role_from_db = await db.get_user_role(user_id)
        if user_role_from_db and user_role_from_db >= self.min_level:
            return True

        for role_from_config, id_list in ADMIN_LEVELS.items():
            if user_id in id_list:
                if role_from_config >= self.min_level:
                    return True

        return False
