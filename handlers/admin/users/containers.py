from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

import database as db
from utils.filters import IsAdmin
from keyboards.admin import get_user_containers_list_keyboard
from states.user_states import AdminUserState, UserBotManageState
from roles import UserRole
from utils.action_logger import log_action
from ..main_menu import send_admin_panel_menu

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

@router.callback_query(StateFilter(AdminUserState.managing_user, UserBotManageState.managing), F.data.startswith("admin_view_user_containers:"))
async def view_user_containers(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(AdminUserState.managing_user)

    parts = callback.data.split(":")
    target_user_id = int(parts[1])
    from_page = int(parts[2]) if len(parts) > 2 else 0

    await state.update_data(from_page=from_page)

    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    user_profile = await db.get_user_profile(target_user_id)
    containers = await db.get_user_containers(target_user_id)

    if not user_profile:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    target_user = await bot.get_chat(target_user_id)
    await log_action(bot, callback.from_user, "просматривает контейнеры пользователя", target_user)

    text = f"🐳 <b>Контейнеры пользователя:</b> {user_profile['first_name']}\n\nВыберите контейнер для управления:"

    markup = await get_user_containers_list_keyboard(containers, target_user_id, from_page, language_code)

    await send_admin_panel_menu(callback, text, markup)
    await callback.answer()
