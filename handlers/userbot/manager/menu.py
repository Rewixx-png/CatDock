from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext

import database as db
from handlers.common.menu_utils import show_management_menu, set_loading_state
from roles import UserRole
from .list import send_userbots_menu
from utils.ui_utils import safe_callback_answer

router = Router()

@router.callback_query(F.data.startswith("manage_bot:"))
async def manage_bot_entry(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    
    await safe_callback_answer(callback)
    await set_loading_state(callback, "Управление контейнером")

    try:
        container_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await send_userbots_menu(callback, state)
        return

    success = await show_management_menu(callback, container_id, state, bot, is_admin_view=False)

    if not success:
        await send_userbots_menu(callback, state)

@router.callback_query(F.data == "cancel_change")
async def cancel_change_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    container_id = data.get('container_id')

    if container_id:
        user_role = await db.get_user_role(callback.from_user.id)
        container = await db.get_container_for_actor(container_id, callback.from_user.id)
        if not container:
            await send_userbots_menu(callback, state)
        else:
            is_admin_view = user_role and user_role >= UserRole.ADMIN and callback.from_user.id != container.get('user_id')
            await show_management_menu(callback, container_id, state, callback.bot, is_admin_view=is_admin_view)
    else:
        await send_userbots_menu(callback, state)

    await safe_callback_answer(callback, "Дію скасовано.")
