import logging
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext

import database as db
from utils.filters import IsAdmin
from keyboards.admin import get_delete_user_confirmation_keyboard
from states.user_states import AdminUserState
from lexicon import LEXICON
from roles import UserRole
from utils.action_logger import log_action
import utils.docker as dm
from .list import get_users_page
from ..main_menu import admin_dashboard as admin_main_menu 

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.callback_query(F.data.startswith("admin_delete_user_start:"))
async def admin_delete_user_start(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    admin_user_id = callback.from_user.id
    language_code = await db.get_user_language(admin_user_id) or 'ru'
    lex = LEXICON[language_code]

    if target_user_id == admin_user_id:
        await callback.answer("Нельзя удалить самого себя!", show_alert=True)
        return

    target_role = await db.get_user_role(target_user_id)
    admin_role = await db.get_user_role(admin_user_id)

    if target_role >= admin_role:
        await callback.answer(lex.get('error_cannot_demote_equal_or_higher', "Нельзя удалить равного или старшего по званию!"), show_alert=True)
        return

    user_profile = await db.get_user_profile(target_user_id)
    user_name = user_profile.get('first_name', 'Unknown')

    await state.set_state(AdminUserState.confirming_deletion)
    await state.update_data(target_user_id=target_user_id)

    confirm_text = lex.get('delete_user_confirm_text', "Вы уверены?").format(name=user_name, id=target_user_id)

    await callback.message.edit_caption(
        caption=confirm_text,
        reply_markup=get_delete_user_confirmation_keyboard(language_code, target_user_id)
    )
    await callback.answer()

@router.callback_query(AdminUserState.confirming_deletion, F.data == "admin_confirm_delete_user")
async def admin_confirm_delete_user(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data.get('target_user_id')

    if not target_user_id:
        await callback.answer("Ошибка состояния. Повторите попытку.", show_alert=True)
        return

    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await callback.message.edit_caption(caption="⏳ Выполняется удаление контейнеров и данных пользователя...")

    try:
        containers = await db.get_user_containers(target_user_id)
        for c in containers:
            try:
                await dm.delete_container(c['server_id'], c['container_name'])
                logging.info(f"Удален контейнер {c['container_name']} пользователя {target_user_id} перед удалением аккаунта.")
            except Exception as e:
                logging.error(f"Ошибка при удалении контейнера {c['container_name']} пользователя {target_user_id}: {e}")

        await db.delete_user_fully(target_user_id)

        target_user_obj = types.User(id=target_user_id, is_bot=False, first_name="Deleted User")
        await log_action(bot, callback.from_user, f"ПОЛНОСТЬЮ удалил пользователя {target_user_id} и его контейнеры через бота", target_user_obj)

        await callback.answer(lex.get('user_deleted_success').format(user_id=target_user_id), show_alert=True)

        await get_users_page(0, callback, state)

    except Exception as e:
        logging.critical(f"Ошибка при полном удалении пользователя {target_user_id} через бота: {e}", exc_info=True)
        await callback.message.edit_caption(caption=f"❌ Произошла ошибка при удалении: {e}")

@router.callback_query(AdminUserState.confirming_deletion, F.data.startswith("admin_select_user:"))
async def cancel_delete_user(callback: types.CallbackQuery, state: FSMContext):
    
    from .profile import show_user_profile
    parts = callback.data.split(":")
    user_id = int(parts[1])
    
    await state.clear()
    await show_user_profile(callback, state, user_id)
