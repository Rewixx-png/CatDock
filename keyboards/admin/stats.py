from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SERVERS

def get_stats_metric_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🧠 RAM", callback_data="stats_metric:ram"),
        types.InlineKeyboardButton(text="🔥 CPU", callback_data="stats_metric:cpu"),
        types.InlineKeyboardButton(text="💾 DISK", callback_data="stats_metric:disk")
    )
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()

def get_stats_server_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(types.InlineKeyboardButton(
        text="🌐 Сравнить все",
        callback_data="stats_server:compare_all"
    ))
    
    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=f"🖥 {server_info['name']}",
            callback_data=f"stats_server:{server_id}"
        ))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="stats_back_to_metric"))
    return builder.as_markup()

def get_stats_period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🕐 Час (60м)", callback_data="stats_period:hour"),
        types.InlineKeyboardButton(text="📅 День (24ч)", callback_data="stats_period:day")
    )
    builder.row(
        types.InlineKeyboardButton(text="🗓 Неделя (7д)", callback_data="stats_period:week"),
        types.InlineKeyboardButton(text="📆 Месяц (30д)", callback_data="stats_period:month")
    )
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="stats_back_to_server"))
    return builder.as_markup()
