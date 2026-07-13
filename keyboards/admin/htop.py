from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SERVERS

def get_htop_server_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=f"🖥 {server_info['name']}",
            callback_data=f"htop_select_server:{server_id}"
        ))
    
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()

def get_htop_refresh_keyboard(server_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🔄 Обновить", callback_data=f"htop_refresh:{server_id}"),
        types.InlineKeyboardButton(text="⬅️ Выбор сервера", callback_data="admin_htop_menu") 
    )
    builder.row(types.InlineKeyboardButton(text="❌ Закрыть", callback_data="delete_message"))
    return builder.as_markup()
