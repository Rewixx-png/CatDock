from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SERVERS, TARIFFS, IMAGES
from lexicon import LEXICON

def get_container_list_keyboard(containers: list, page: int, total_pages: int, sort_by: str, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    sort_buttons = [
        types.InlineKeyboardButton(text=lex.get('sort_by_time_button', "По времени ⏳"), callback_data=f"sort_containers:time"),
        types.InlineKeyboardButton(text=lex.get('sort_by_ram_button', "По RAM 🧠"), callback_data=f"sort_containers:ram"),
        types.InlineKeyboardButton(text=lex.get('sort_by_price_button', "По цене 💰"), callback_data=f"sort_containers:price")
    ]
    builder.row(*sort_buttons)

    builder.row(
        types.InlineKeyboardButton(
            text=lex.get('search_container_by_id_button', "🔍 Найти по ID"), 
            callback_data="admin_search_container_by_id"
        ),
        types.InlineKeyboardButton(
            text=lex.get('search_by_name', "📝 Найти по имени"),
            callback_data="admin_search_container_by_name"
        )
    )

    builder.row(types.InlineKeyboardButton(text="⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯", callback_data="none"))

    for container in containers:
        server_name = SERVERS.get(container['server_id'], {}).get('name', 'N/A')
        tariff_info = TARIFFS.get(container['tariff_id'], {})
        ram_mb = tariff_info.get('ram_mb', '???')

        frozen_icon = "❄️ " if container.get('is_frozen') else ""
        text = f"{frozen_icon}ID: {container['id']} | {ram_mb}MB | {server_name} | User: {container['user_id']}"
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"manage_bot:{container['id']}:{page}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text=lex.get('prev_page_button', "⬅️ Пред."), callback_data=f"containers_page:{page-1}:{sort_by}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text=lex.get('next_page_button', "След. ➡️"), callback_data=f"containers_page:{page+1}:{sort_by}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(types.InlineKeyboardButton(text=lex['back_to_admin_panel_button'], callback_data="admin_panel"))
    return builder.as_markup()

async def get_user_containers_list_keyboard(containers: list, target_user_id: int, from_page: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    for container in containers:
        server_name = SERVERS.get(container['server_id'], {}).get('name', 'N/A')
        image_name = IMAGES.get(container['image_id'], {}).get('name', 'N/A')
        frozen_icon = "❄️ " if container.get('is_frozen') else ""
        text = f"{frozen_icon}{container['container_name']} ({server_name} | {image_name})"
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"manage_bot:{container['id']}:user:{target_user_id}:{from_page}"))

    builder.row(types.InlineKeyboardButton(text=lex['back_button'], callback_data=f"admin_select_user:{target_user_id}:{from_page}"))
    return builder.as_markup()

def get_orphaned_containers_keyboard(count: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=lex.get('orphans_delete_button', "🗑️ Удалить все ({count})").format(count=count),
        callback_data="admin_delete_orphans"
    ))
    builder.row(types.InlineKeyboardButton(
        text=lex['cancel_button'],
        callback_data="cancel_admin_action:admin_panel"
    ))
    return builder.as_markup()

def get_checkcont_keyboard(count: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=f"🗑️ Удалить все ({count})",
        callback_data="admin_delete_checkcont"
    ))
    builder.row(types.InlineKeyboardButton(
        text=lex['back_to_admin_panel_button'],
        callback_data="admin_panel"
    ))
    return builder.as_markup()

def get_fixloop_list_keyboard(containers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in containers:
        builder.row(types.InlineKeyboardButton(
            text=f"🗑️ {c['name']} ({c['server_name']})",
            callback_data=f"fixloop_delete_start:{c['db_id']}"
        ))
    return builder.as_markup()

async def get_admin_container_list_keyboard(containers: list, language_code: str = 'ru') -> InlineKeyboardMarkup:
    import database as db 
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    for container in containers:
        user_info = await db.get_user_profile(container['user_id'])
        owner_name = user_info['first_name'] if user_info else f"ID: {container['user_id']}"
        text = f"👑 {container['container_name']} (Владелец: {owner_name})"
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"manage_bot:{container['id']}:admin_list"))

    builder.row(types.InlineKeyboardButton(text=lex['back_button'], callback_data="admin_containers_menu"))
    return builder.as_markup()

async def get_admin_containers_menu_keyboard(language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('give_admin_container_button', "➕ Выдать админ-контейнер"), callback_data="give_admin_container_start"))
    builder.row(types.InlineKeyboardButton(text=lex.get('admin_container_list_button', "📋 Список админ-контейнеров"), callback_data="admin_container_list"))
    builder.row(types.InlineKeyboardButton(text=lex['back_to_admin_panel_button'], callback_data="admin_panel"))
    return builder.as_markup()
