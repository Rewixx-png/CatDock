from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from lexicon import LEXICON
from roles import UserRole, ROLE_NAMES
import database as db

async def get_user_management_keyboard(user_data: dict, language_code: str = 'ru', from_page: int = 0) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    target_user_id = user_data['user_id']

    user_containers = await db.get_user_containers(target_user_id)
    if user_containers:
        builder.row(types.InlineKeyboardButton(
            text=f"🐳 Контейнеры пользователя ({len(user_containers)})", 
            callback_data=f"admin_view_user_containers:{target_user_id}:{from_page}"
        ))

    is_blocked = user_data.get('is_blocked', 0)
    block_button_text = lex.get('unblock_user_button', "🔓 Разблокировать") if is_blocked else lex.get('block_user_button', "🚫 Заблокировать")

    builder.row(types.InlineKeyboardButton(text=lex.get('change_balance_button', "💰 Изменить баланс"), callback_data=f"admin_change_balance:{target_user_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('give_container_button', "🐳 Выдать контейнер"), callback_data=f"admin_give_container_start:{target_user_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('change_role_button', "👑 Изменить роль"), callback_data=f"admin_change_role_start:{target_user_id}"))

    builder.row(
        types.InlineKeyboardButton(text=block_button_text, callback_data=f"admin_toggle_block:{target_user_id}"),
        types.InlineKeyboardButton(text="🔄 Сбросить фри-тариф", callback_data=f"admin_reset_free:{target_user_id}")
    )

    builder.row(types.InlineKeyboardButton(
        text=lex.get('delete_user_fully_button', "🗑️ Удалить (Full Wipe)"), 
        callback_data=f"admin_delete_user_start:{target_user_id}"
    ))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_user_search_button', "⬅️ К поиску/списку"), callback_data=f"users_page:{from_page}"))
    return builder.as_markup()

def get_delete_user_confirmation_keyboard(language_code: str = 'ru', target_user_id: int = 0) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=lex.get('delete_user_confirm_button', "🔥 Да, удалить навсегда"),
        callback_data="admin_confirm_delete_user"
    ))
    builder.row(types.InlineKeyboardButton(
        text=lex.get('cancel_button', 'cancel_button'), 
        callback_data=f"admin_select_user:{target_user_id}"
    ))
    return builder.as_markup()

async def get_role_selection_keyboard(target_user_id: int, admin_role: UserRole, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    for role in UserRole:
        if admin_role.value <= role.value:
            continue
        if admin_role == UserRole.CO_OWNER and role.value > UserRole.SENIOR_ADMIN.value:
            continue

        builder.row(
            types.InlineKeyboardButton(
                text=ROLE_NAMES[role],
                callback_data=f"admin_set_role:{target_user_id}:{role.name}"
            )
        )

    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data=f"admin_select_user:{target_user_id}"))
    return builder.as_markup()

def get_user_list_keyboard(users: list, page: int, total_pages: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for user in users:
        text = f"{user['first_name']} (@{user.get('username', 'N/A')}) - ID: {user['user_id']}"
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"admin_select_user:{user['user_id']}:{page}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text=lex.get('prev_page_button', "⬅️ Пред."), callback_data=f"users_page:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text=lex.get('next_page_button', "След. ➡️"), callback_data=f"users_page:{page+1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(types.InlineKeyboardButton(text=lex.get('search_by_id_button', "🔍 Найти по ID/Username"), callback_data="admin_search_user"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_admin_panel_button', 'back_to_admin_panel_button'), callback_data="admin_panel"))
    return builder.as_markup()

def get_rinfo_main_keyboard(target_user_id: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=lex.get('show_userbots_button', "🐳 Юзерботы"),
        callback_data=f"rinfo_bots:{target_user_id}"
    ))
    return builder.as_markup()

def get_rinfo_userbots_keyboard(target_user_id: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('back_to_rinfo_button', "⬅️ Назад к информации"), callback_data=f"rinfo_main:{target_user_id}")
    )
    return builder.as_markup()
