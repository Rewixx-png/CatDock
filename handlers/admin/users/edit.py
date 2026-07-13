import logging
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
from utils.filters import IsAdmin
from keyboards.admin import get_cancel_admin_action_keyboard, get_role_selection_keyboard
from states.user_states import AdminUserState
from roles import UserRole, ROLE_NAMES
from lexicon import LEXICON
from utils import bot_state
from utils.action_logger import log_action
from handlers.common.base.main_flow import send_main_menu as send_user_main_menu
from .profile import show_user_profile
from utils.ui_utils import safe_edit_caption

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

@router.callback_query(F.data.startswith("admin_toggle_block:"))
async def toggle_block_user(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    target_user_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    target_role = await db.get_user_role(target_user_id)
    if target_role >= UserRole.JUNIOR_ADMIN:
        await callback.answer(lex.get('error_cannot_block_admin', "❌ Нельзя заблокировать другого администратора."), show_alert=True)
        return

    if target_user_id == callback.from_user.id:
        await callback.answer("Вы не можете заблокировать самого себя.", show_alert=True)
        return

    new_status_is_blocked = await db.toggle_user_block(target_user_id)

    target_user = await bot.get_chat(target_user_id)
    action_text = "заблокировал пользователя" if new_status_is_blocked else "разблокировал пользователя"
    await log_action(bot, callback.from_user, action_text, target_user)

    message_text = lex.get('user_was_blocked_message') if new_status_is_blocked else lex.get('user_was_unblocked_message')
    notification_text = lex.get('user_blocked_notification') if new_status_is_blocked else "Администратор разблокировал ваш аккаунт."

    await callback.answer(message_text, show_alert=True)
    try:
        await bot.send_message(target_user_id, notification_text)
    except Exception as e:
        logging.warning(f"Не удалось отправить уведомление о (раз)блокировке пользователю {target_user_id}: {e}")

    data = await state.get_data()
    from_page = data.get('from_page', 0)
    await show_user_profile(callback, state, target_user_id, from_page=from_page)

@router.callback_query(F.data.startswith("admin_change_role_start:"), IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def admin_change_role_start(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    admin_id = callback.from_user.id
    language_code = await db.get_user_language(admin_id) or 'ru'
    lex = LEXICON[language_code]

    admin_role = await db.get_user_role(admin_id)
    target_role = await db.get_user_role(target_user_id)
    if admin_role <= target_role:
        await callback.answer(lex.get('error_cannot_demote_equal_or_higher'), show_alert=True)
        return

    await state.set_state(AdminUserState.changing_role)
    markup = await get_role_selection_keyboard(target_user_id, admin_role, language_code)
    await safe_edit_caption(
        callback.message,
        caption=lex.get('change_role_prompt'),
        reply_markup=markup
    )
    await callback.answer()

@router.callback_query(AdminUserState.changing_role, F.data.startswith("admin_set_role:"), IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def admin_set_role(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    _, user_id_str, role_name = callback.data.split(":")
    target_user_id = int(user_id_str)
    admin_id = callback.from_user.id
    language_code = await db.get_user_language(admin_id) or 'ru'
    lex = LEXICON[language_code]

    admin_role = await db.get_user_role(admin_id)
    new_role = UserRole[role_name]

    if admin_role <= new_role:
        await callback.answer(lex.get('error_cannot_assign_equal_or_higher'), show_alert=True)
        return
    if admin_role == UserRole.CO_OWNER and new_role > UserRole.SENIOR_ADMIN:
        await callback.answer(lex.get('error_co_owner_permission_denied'), show_alert=True)
        return

    await db.set_user_role(target_user_id, role_name)
    role_display_name = ROLE_NAMES.get(new_role, role_name)

    target_user = await bot.get_chat(target_user_id)
    await log_action(bot, callback.from_user, f"изменил роль на '{role_display_name}' для пользователя", target_user)

    bot_state.admin_ids_cache.clear()
    bot_state.admin_ids_cache.update(await db.get_all_admin_ids())
    logging.info(f"Кэш администраторов обновлен: {len(bot_state.admin_ids_cache)} админов.")

    await callback.answer(lex.get('role_changed_message').format(role_name=role_display_name), show_alert=True)

    user_language_code = await db.get_user_language(target_user_id) or 'ru'

    try:
        user_lex = LEXICON[user_language_code]
        notification_text = user_lex.get('admin_changed_role_notification').format(role_name=role_display_name)
        await bot.send_message(target_user_id, notification_text)
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logging.warning(f"Не удалось отправить уведомление о смене роли пользователю {target_user_id}: {e}")

    if new_role >= UserRole.ADMIN:
        try:
            await send_user_main_menu(callback, state)
        except Exception as e:
            logging.error(f"Не удалось отправить главное меню новому админу {target_user_id}: {e}")

    data = await state.get_data()
    from_page = data.get('from_page', 0)
    await show_user_profile(callback, state, target_user_id, from_page=from_page)

@router.callback_query(F.data.startswith("admin_change_balance:"), IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def change_balance_start(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    await state.set_state(AdminUserState.changing_balance)
    await state.update_data(target_user_id=target_user_id)
    await callback.message.delete()
    await callback.message.answer(
        "Введите сумму для изменения баланса. \nПоложительное число (e.g., `100`) для пополнения, отрицательное (`-50`) для списания.",
        reply_markup=get_cancel_admin_action_keyboard("manage_users", "ru")
    )
    await callback.answer()

@router.message(AdminUserState.changing_balance, IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def process_balance_change(message: types.Message, state: FSMContext, bot: Bot):
    try:
        delta = float(message.text.replace(',', '.'))
    except (ValueError, TypeError):
        await message.answer("❌ Введите корректное число.")
        return

    data = await state.get_data()
    target_user_id = data['target_user_id']
    from_page = data.get('from_page', 0)

    await db.admin_update_user_balance(target_user_id, delta)
    new_balance = await db.get_user_balance(target_user_id)

    target_user = await bot.get_chat(target_user_id)
    await log_action(bot, message.from_user, f"изменил баланс на {delta:+.2f} RUB для пользователя", target_user)

    await message.answer(f"✅ Баланс пользователя <code>{target_user_id}</code> изменен на {delta:.2f} RUB.")

    try:
        user_language_code = await db.get_user_language(target_user_id) or 'ru'
        user_lex = LEXICON[user_language_code]
        notification_text = user_lex.get('admin_changed_balance_notification').format(
            amount=delta,
            new_balance=new_balance
        )
        await bot.send_message(target_user_id, notification_text)
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logging.warning(f"Не удалось отправить уведомление об изменении баланса пользователю {target_user_id}: {e}")

    await show_user_profile(message, state, target_user_id, from_page=from_page)
