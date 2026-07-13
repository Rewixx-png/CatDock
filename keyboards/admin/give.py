from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SERVERS, TARIFFS, IMAGES
from lexicon import LEXICON

def get_give_confirmation_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('confirm_give_button', "✅ Да, выдать"), callback_data="confirm_give_container"),
        types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="cancel_admin_action")
    )
    return builder.as_markup()

def get_chat_give_tariff_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tariff_id, tariff_info in TARIFFS.items():
        if tariff_id == 'free': continue
        text = f"{tariff_info['name']} ({tariff_info['price_rub']}₽)"
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"chat_give_tariff:{tariff_id}"))
    return builder.as_markup()

def get_chat_give_server_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(text=server_info['name'], callback_data=f"chat_give_server:{server_id}"))
    return builder.as_markup()

def get_chat_give_image_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for image_id, image_info in IMAGES.items():
        builder.row(types.InlineKeyboardButton(text=image_info['name'], callback_data=f"chat_give_image:{image_id}"))
    return builder.as_markup()

def get_give_admin_server_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=server_info['name'], 
            callback_data=f"give_admin_server:{server_id}"
        ))
    builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="admin_containers_menu"))
    return builder.as_markup()

def get_give_admin_image_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for image_id, image_info in IMAGES.items():
        builder.row(types.InlineKeyboardButton(
            text=image_info['name'], 
            callback_data=f"give_admin_image:{image_id}"
        ))
    builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="admin_containers_menu"))
    return builder.as_markup()

def get_give_admin_confirmation_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('confirm_give_button', "✅ Да, выдать"), callback_data="confirm_give_admin_container"),
        types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="admin_containers_menu")
    )
    return builder.as_markup()
