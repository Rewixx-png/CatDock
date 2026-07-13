import html
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

import database as db
from utils.filters import IsAdmin
from keyboards.admin import get_user_management_keyboard
from roles import UserRole, ROLE_NAMES
from lexicon import LEXICON
from ..main_menu import send_admin_panel_menu
from utils.ui_utils import safe_callback_answer

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

async def show_user_profile(message: types.Message | types.CallbackQuery, state: FSMContext, user_id: int, from_page: int = 0):
    user_data = await db.get_user_profile(user_id)
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])

    if not user_data:
        if isinstance(message, types.CallbackQuery):
            await safe_callback_answer(message, "❌ Пользователь не найден.", show_alert=True)
        else:
            await message.reply("❌ Пользователь не найден.")
        return

    await state.set_state("AdminUserState:managing_user") 
    await state.update_data(target_user_id=user_data['user_id'], from_page=from_page)

    user_containers = await db.get_user_containers(user_data['user_id'])

    user_role_enum = await db.get_user_role(user_data['user_id'])
    role_display = ROLE_NAMES.get(user_role_enum, "Неизвестная роль")

    is_blocked = user_data.get('is_blocked', 0)
    block_status_text = lex.get('user_is_blocked_status', "ЗАБЛОКИРОВАН 🚫") if is_blocked else lex.get('user_is_not_blocked_status', "Активен ✅")

    reg_date_raw = str(user_data.get('reg_date', 'N/A'))
    reg_date_display = reg_date_raw.split('.')[0] if '.' in reg_date_raw else reg_date_raw

    safe_first_name = html.escape(user_data.get('first_name', 'Unknown'))
    safe_username = html.escape(user_data.get('username') or 'N/A')

    profile_text = (
        f"<b>Профиль:</b> {safe_first_name} (@{safe_username})\n"
        f"<b>ID:</b> <code>{user_data['user_id']}</code>\n"
        f"<b>Статус:</b> {block_status_text}\n"
        f"<b>Роль:</b> {role_display}\n\n"
        f"<b>Баланс:</b> {user_data.get('balance', 0.0):.2f} RUB\n"
        f"<b>Реф. баланс:</b> {user_data.get('ref_balance', 0.0):.2f} RUB\n"
        f"<b>Дата рег.:</b> {reg_date_display}\n"
        f"<b>Контейнеры:</b> {len(user_containers)}"
    )

    markup = await get_user_management_keyboard(user_data, language_code, from_page=from_page)
    await send_admin_panel_menu(message, profile_text, markup)

@router.callback_query(F.data.startswith("admin_select_user:"))
async def select_user_from_list(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    user_id = int(parts[1])
    from_page = int(parts[2]) if len(parts) > 2 else 0
    await show_user_profile(callback, state, user_id, from_page=from_page)
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("admin_reset_free:"), IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def reset_free_tariff_start(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    await db.admin_reset_free_tariff_usage(target_user_id)
    await safe_callback_answer(callback, "✅ Лимит на бесплатный тариф для этого пользователя сброшен.", show_alert=True)

    data = await state.get_data()
    from_page = data.get('from_page', 0)
    await show_user_profile(callback, state, target_user_id, from_page)
