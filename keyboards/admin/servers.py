from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SERVERS
from lexicon import LEXICON
from utils import bot_state

def get_server_management_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex.get('server_add', "➕ Добавить"), callback_data="admin_server_add"),
        types.InlineKeyboardButton(text=lex.get('server_edit', "✏️ Редактировать"), callback_data="admin_server_edit_list"),
        types.InlineKeyboardButton(text=lex.get('server_delete', "🗑 Удалить"), callback_data="admin_server_delete_menu")
    )

    for server_id, server_info in SERVERS.items():
        is_active = bot_state.server_states.get(server_id, True)
        status_icon = "🟢" if is_active else "🔴"
        action_text = "OFF" if is_active else "ON" 

        button_text = f"{status_icon} {server_info['name']} [{action_text}]"
        builder.row(types.InlineKeyboardButton(
            text=button_text,
            callback_data=f"toggle_server_status:{server_id}"
        ))

    builder.row(types.InlineKeyboardButton(text=lex['back_to_admin_panel_button'], callback_data="admin_panel"))
    return builder.as_markup()

def get_server_edit_list_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=f"📝 {server_info['name']}",
            callback_data=f"admin_server_edit_select:{server_id}"
        ))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', "⬅️ Назад"), callback_data="manage_servers"))
    return builder.as_markup()

def get_server_edit_details_keyboard(server_id: str, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex.get('server_edit_name', "Имя"), callback_data=f"edit_srv:{server_id}:name"),
        types.InlineKeyboardButton(text=lex.get('server_edit_ip', "IP адрес"), callback_data=f"edit_srv:{server_id}:ip")
    )
    builder.row(
        types.InlineKeyboardButton(text=lex.get('server_edit_pass', "Пароль (Root)"), callback_data=f"edit_srv:{server_id}:password"),
        types.InlineKeyboardButton(text=lex.get('server_edit_port', "SSH Порт"), callback_data=f"edit_srv:{server_id}:check_port")
    )

    builder.row(types.InlineKeyboardButton(text=lex.get('server_back_select', "⬅️ Назад к выбору"), callback_data="admin_server_edit_list"))
    return builder.as_markup()

def get_server_delete_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=f"❌ {lex.get('server_delete', 'Удалить')} {server_info['name']}",
            callback_data=f"admin_server_delete_select:{server_id}"
        ))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', "⬅️ Назад"), callback_data="manage_servers"))
    return builder.as_markup()

def get_server_delete_confirm_keyboard(server_id: str, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('server_delete_confirm', "🔥 Да, удалить навсегда"), callback_data=f"admin_server_delete_confirm:{server_id}"),
        types.InlineKeyboardButton(text=lex['cancel_button'], callback_data="manage_servers")
    )
    return builder.as_markup()

def get_server_for_update_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=f"🖥️ {server_info['name']}",
            callback_data=f"select_server_for_update:{server_id}"
        ))
    builder.row(types.InlineKeyboardButton(
        text=lex['back_to_admin_panel_button'],
        callback_data="admin_panel"
    ))
    return builder.as_markup()

def get_terminal_exit_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=lex.get('terminal_exit_button', "Выйти из терминала"),
        callback_data="cancel_terminal"
    ))
    return builder.as_markup()
