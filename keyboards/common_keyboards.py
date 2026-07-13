from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from lexicon import LEXICON
import database as db
from roles import UserRole
from config import SUPPORT_URL, SUPPORT_CHAT_URL

async def get_main_menu_keyboard(language_code: str, user_id: int) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex.get('my_userbots_button', '🤖 Мои UserBot'), callback_data="my_userbots"),
        types.InlineKeyboardButton(text=lex.get('tariffs_button', '📦 Тарифы'), callback_data="tariffs")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('profile_button', '👤 Профиль'), callback_data="profile"),
        types.InlineKeyboardButton(text=lex.get('deposit_button', '💰 Пополнить'), callback_data="add_balance")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('misc_menu_button', '🗂️ Меню'), callback_data="misc_menu")
    )

    return builder.as_markup()

async def get_misc_menu_keyboard(language_code: str, user_id: int) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(
            text=lex.get('server_status_button', 'server_status_button'),
            callback_data="show_server_status",
        )
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('settings_button', '⚙️ Настройки'), callback_data="settings_menu")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('support_chat_button', 'support_chat_button'), url=SUPPORT_CHAT_URL),
        
        types.InlineKeyboardButton(text=lex.get('support_account_button', '👨‍💻 Агент'), url=SUPPORT_URL)
    )

    user_role = await db.get_user_role(user_id)
    if user_role and user_role >= UserRole.ADMIN:
        builder.row(types.InlineKeyboardButton(text=lex.get('admin_panel_button', '👑 Админка'), callback_data="admin_panel"))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_main_menu_button', 'back_to_main_menu_button'), callback_data="back_to_main_menu"))

    return builder.as_markup()

def get_initial_start_keyboard(language_code: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔥 Let's Go!", callback_data="initial_start_done"))
    return builder.as_markup()

def get_language_selection_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"))
    builder.row(types.InlineKeyboardButton(text="🇺🇦 Українська", callback_data="set_lang:uk"))
    builder.row(types.InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang:en"))
    return builder.as_markup()

def get_simple_confirmation_keyboard(language_code: str, yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex.get('confirm_button', 'confirm_button'), callback_data=yes_callback),
        types.InlineKeyboardButton(text=lex.get('no_back_button', '❌ Нет'), callback_data=no_callback)
    )
    return builder.as_markup()

def get_cancel_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="cancel_payment"))
    return builder.as_markup()
