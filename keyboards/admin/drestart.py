from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SERVERS

def get_drestart_server_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=f"🔄 {server_info['name']}",
            callback_data=f"drestart_select:{server_id}"
        ))
    
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()
