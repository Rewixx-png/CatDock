from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from lexicon import LEXICON
import database as db
from roles import UserRole
from config import SUPPORT_URL

async def get_main_menu_keyboard(language_code: str, user_id: int) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex['my_userbots_button'], callback_data="my_userbots"),
        types.InlineKeyboardButton(text=lex['tariffs_button'], callback_data="tariffs")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex['profile_button'], callback_data="profile"),
        types.InlineKeyboardButton(text=lex['deposit_button'], callback_data="add_balance")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('misc_menu_button', '🗂️ Меню'), callback_data="misc_menu")
    )

    return builder.as_markup()

async def get_misc_menu_keyboard(language_code: str, user_id: int) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex['server_status_button'], url="https://catdock.catdock.io/status")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('settings_button', '⚙️ Настройки'), callback_data="settings_menu")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex['support_chat_button'], url="https://t.me/catdock_chat"),
        
        types.InlineKeyboardButton(text=lex.get('support_account_button', '👨‍💻 Агент'), url=SUPPORT_URL)
    )

    user_role = await db.get_user_role(user_id)
    if user_role and user_role >= UserRole.ADMIN:
        builder.row(types.InlineKeyboardButton(text=lex.get('admin_panel_button', '👑 Админка'), callback_data="admin_panel"))

    builder.row(types.InlineKeyboardButton(text=lex['back_to_main_menu_button'], callback_data="back_to_main_menu"))

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
        types.InlineKeyboardButton(text=lex['confirm_button'], callback_data=yes_callback),
        types.InlineKeyboardButton(text=lex.get('no_back_button', '❌ Нет'), callback_data=no_callback)
    )
    return builder.as_markup()

def get_server_status_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex['refresh_button'], callback_data="server_status"))
    builder.row(types.InlineKeyboardButton(text=lex['back_to_main_menu_button'], callback_data="back_to_main_menu"))
    return builder.as_markup()

def get_cancel_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text=lex['cancel_button'], callback_data="cancel_payment"))
    return builder.as_markup()

def get_admin_deposit_keyboard(user_id: int, amount: float, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('admin_approve', '✅ Одобрить'), callback_data=f"admin_approve:{user_id}:{amount}"),
        types.InlineKeyboardButton(text=lex.get('admin_decline', '❌ Отклонить'), callback_data=f"admin_decline:{user_id}:{amount}")
    )
    return builder.as_markup()

def get_admin_withdrawal_keyboard(request_id: int, user_id: int, amount: float, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('admin_approve_withdrawal', '✅ Одобрить'), callback_data=f"admin_w_approve:{request_id}:{user_id}:{amount}"),
        types.InlineKeyboardButton(text=lex.get('admin_decline_withdrawal', '❌ Отклонить'), callback_data=f"admin_w_decline:{request_id}:{user_id}:{amount}")
    )
    return builder.as_markup()
