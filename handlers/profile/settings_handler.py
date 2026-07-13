import asyncio
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import URLInputFile
from aiogram.exceptions import TelegramBadRequest

import database as db
from keyboards.profile_keyboards import get_settings_menu_keyboard, get_profile_settings_keyboard
from states.user_states import ProfileSettingsState
from lexicon import LEXICON
from roles import ROLE_NAMES


router = Router()

async def show_profile_settings_menu(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(ProfileSettingsState.viewing)
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    user_profile, settings, containers = await asyncio.gather(
        db.get_user_profile(user_id),
        db.get_user_settings(user_id),
        db.get_user_containers(user_id)
    )

    if user_profile:
        lines = ["👤 <b>Превью вашего профиля:</b>\n"]

        line1 = []
        if settings.get('show_id'): line1.append(f"ID  –  <code>{user_id}</code>")
        if settings.get('show_name'): line1.append(f"Имя  –  {callback.from_user.full_name}")
        if line1: lines.append("  || ".join(line1))

        line2 = []
        if settings.get('show_username'): line2.append(f"Username  –  @{callback.from_user.username or 'не указан'}")
        if settings.get('show_role'):
            user_role_enum = await db.get_user_role(user_id)
            role_name = ROLE_NAMES.get(user_role_enum, "Неизвестная роль")
            line2.append(f"Роль  –  {role_name}")
        if line2: lines.append("  ||  ".join(line2))

        if settings.get('show_userbots'): lines.append(f"\nUserBots – {len(containers)}")
        lines.append("") 

        if settings.get('show_main_balance'): lines.append(f"💰 Основной баланс – {user_profile.get('balance', 0):.2f} RUB")
        if settings.get('show_ref_balance'): lines.append(f"🎁 Реферальный баланс  –  {user_profile.get('ref_balance', 0):.2f} RUB")

        preview_text = "\n".join(lines)
    else:
        preview_text = lex.get('error_profile_not_found')

    markup = get_profile_settings_keyboard(settings, language_code)
    await callback.message.edit_text(preview_text, reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data == "settings_menu")
async def show_settings_menu_handler(callback: types.CallbackQuery):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await callback.message.edit_caption(
        caption="⚙️ <b>Настройки</b>",
        reply_markup=get_settings_menu_keyboard(language_code)
    )
    await callback.answer()

@router.callback_query(F.data == "profile_settings")
async def profile_settings_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await show_profile_settings_menu(callback, state, bot)

@router.callback_query(ProfileSettingsState.viewing, F.data.startswith("toggle_profile_setting:"))
async def toggle_profile_setting_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    setting_key = callback.data.split(":")[1]

    await db.toggle_user_setting(callback.from_user.id, setting_key)

    await show_profile_settings_menu(callback, state, bot)
