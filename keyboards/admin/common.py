from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from lexicon import LEXICON
from config import WEB_APP_URL

def get_cancel_admin_action_keyboard(back_to: str = "admin_panel", language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data=back_to))
    return builder.as_markup()

def get_yes_no_keyboard(language_code: str, yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('yes_button', "Да"), callback_data=yes_callback),
        types.InlineKeyboardButton(text=lex.get('no_button', "Нет"), callback_data=no_callback)
    )
    return builder.as_markup()

def get_admin_deposit_actions_keyboard(request_id: int, user_id: int, amount: float, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    admin_url = f"{WEB_APP_URL}/admin/process-deposit/{request_id}"
    builder.row(types.InlineKeyboardButton(text="⚡️ Web Check", web_app=types.WebAppInfo(url=admin_url)))

    builder.row(
        types.InlineKeyboardButton(
            text=lex.get('admin_approve', '✅ Approve'), 
            callback_data=f"adm_dep_ap:{request_id}"
        ),
        types.InlineKeyboardButton(
            text=lex.get('admin_decline', '❌ Decline'), 
            callback_data=f"adm_dep_dec_start:{request_id}"
        )
    )
    return builder.as_markup()
