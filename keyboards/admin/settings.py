"""CatDock admin settings keyboard — stripped of promo functionality."""
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from lexicon import LEXICON


def get_bot_settings_keyboard(maintenance_mode: bool = False, raid_mode: bool = False, language_code: str = 'ru') -> types.InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    maint_text = f"{'✅' if not maintenance_mode else '❌'} {lex.get('toggle_maintenance_button', 'Toggle Maintenance')}"
    raid_text = f"{'✅' if not raid_mode else '❌'} {lex.get('toggle_raid_button', 'Toggle Raid')}"
    builder.row(types.InlineKeyboardButton(text=maint_text, callback_data="toggle_maintenance"))
    builder.row(types.InlineKeyboardButton(text=raid_text, callback_data="toggle_raid_mode"))
    builder.row(types.InlineKeyboardButton(text=lex.get('clear_cache_button', 'Clear Cache'), callback_data="admin_clear_cache"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_admin_panel_button', 'back_to_admin_panel_button'), callback_data="admin_panel"))
    return builder.as_markup()


def get_broadcast_confirmation_keyboard(language_code: str = 'ru') -> types.InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=lex.get('confirm_broadcast_button', 'Confirm Broadcast'),
        callback_data="confirm_send_broadcast"
    ))
    builder.row(types.InlineKeyboardButton(
        text=lex.get('cancel_button', 'Cancel'),
        callback_data="cancel_admin_action:admin_menu_marketing"
    ))
    return builder.as_markup()
