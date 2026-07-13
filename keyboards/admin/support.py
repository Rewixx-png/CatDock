from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from lexicon import LEXICON

def get_admin_ticket_keyboard(ticket_id: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=lex.get('admin_take_ticket', "✍️ Взять в работу"),
        callback_data=f"support_take:{ticket_id}"
    ))
    return builder.as_markup()

def get_admin_answer_confirm_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('admin_send_answer', "✅ Отправить"), callback_data="support_send_answer"),
        types.InlineKeyboardButton(text=lex.get('admin_edit_answer', "✏️ Изменить"), callback_data="support_edit_answer")
    )
    return builder.as_markup()
