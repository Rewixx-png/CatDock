from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from lexicon import LEXICON
from config import SERVERS, IMAGES, TARIFFS, DEFAULT_CPU_LIMIT
from utils import bot_state

async def get_my_userbots_keyboard(containers: list, language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    if containers:
        for container in containers:
            icon = container.get('cosmetic_icon', '')
            icon_prefix = f"{icon} " if icon else ""
            if container.get('is_blocked'):
                icon_prefix += "⛔ " 
            server_name = SERVERS.get(container['server_id'], {}).get('name', container['server_id'])
            image_name = IMAGES.get(container['image_id'], {}).get('name', 'N/A')
            text = f"{icon_prefix}{server_name} - {image_name} ({container['container_name']})"
            builder.row(types.InlineKeyboardButton(text=text, callback_data=f"manage_bot:{container['id']}"))
    builder.row(types.InlineKeyboardButton(text=lex['back_to_main_menu_button'], callback_data="back_to_main_menu"))
    return builder.as_markup()

def get_orphaned_container_management_keyboard(
    container_info: dict, language_code: str, is_admin_view: bool, admin_back_callback: str | None, from_page: int
) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    container_id = container_info['id']

    builder.row(types.InlineKeyboardButton(text=lex.get('delete_button', '🗑️ Удалить'), callback_data=f"delete_bot_start:{container_id}"))

    if is_admin_view:
        builder.row(types.InlineKeyboardButton(text=lex.get('admin_change_server_button', "⇄ Сменить сервер (Админ)"), callback_data=f"admin_change_server_start:{container_id}"))
        builder.row(types.InlineKeyboardButton(text=lex.get('change_time_button', '⏳ Изменить время'), callback_data=f"admin_change_time_start:{container_id}"))
    else:
        builder.row(types.InlineKeyboardButton(text=lex['change_server_button'], callback_data=f"change_server_start:{container_id}"))

    if is_admin_view:
        if admin_back_callback:
            back_text = lex.get('back_button', "⬅️ Назад")
            back_data = admin_back_callback
        else:
            back_text = lex.get('back_to_containers_list_button', "⬅️ Назад к списку")
            back_data = f"containers_page:{from_page}"
        builder.row(types.InlineKeyboardButton(text=back_text, callback_data=back_data))
    else:
        builder.row(types.InlineKeyboardButton(text=lex.get('back_to_my_userbots_button', "⬅️ Назад к списку"), callback_data="my_userbots"))

    return builder.as_markup()

async def get_container_management_keyboard(
    container_info: dict, status: str, language_code: str, is_admin_view: bool = False, admin_back_callback: str | None = None, from_page: int = 0
) -> InlineKeyboardMarkup:
    import database as db 
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    container_id = container_info['id']
    is_frozen = bool(container_info.get('is_frozen', 0))
    is_blocked = bool(container_info.get('is_blocked', 0)) 

    pending_transfer_token = await db.get_active_token_for_container(container_id)
    if pending_transfer_token:
        bot_info = bot_state.bot_info_cache
        transfer_link = f"https://t.me/{bot_info.username}?start={pending_transfer_token}"

        builder.row(types.InlineKeyboardButton(text=lex.get('transfer_link_btn', "➡️ Ссылка на передачу"), url=transfer_link))
        builder.row(types.InlineKeyboardButton(text=lex.get('transfer_cancel_btn', "❌ Отменить передачу"), callback_data=f"cancel_transfer:{container_id}"))

        if is_admin_view:
            back_text = lex.get('back_to_containers_list_button', "⬅️ Назад")
            back_data = f"containers_page:{from_page}" if not admin_back_callback else admin_back_callback
            builder.row(types.InlineKeyboardButton(text=back_text, callback_data=back_data))
        else:
             builder.row(types.InlineKeyboardButton(text=lex.get('back_to_my_userbots_button', "⬅️ Назад"), callback_data="my_userbots"))

        return builder.as_markup()

    if is_blocked:
        builder.row(types.InlineKeyboardButton(text=lex.get('status_blocked', "⛔ ЗАБЛОКИРОВАНО"), callback_data="none"))

    elif is_frozen:
        builder.row(types.InlineKeyboardButton(text=lex.get('unfreeze_button', '☀️ Разморозить'), callback_data=f"unfreeze_bot:{container_id}"))

    else:
        if status == 'running':
            builder.add(types.InlineKeyboardButton(text=lex.get('turn_off_button', '⏹️ Выключить'), callback_data=f"stop_bot:{container_id}"))
        else:
            builder.add(types.InlineKeyboardButton(text=lex.get('turn_on_button', '▶️ Включить'), callback_data=f"start_bot:{container_id}"))
        builder.add(types.InlineKeyboardButton(text=lex.get('freeze_button', '❄️ Заморозить'), callback_data=f"freeze_bot:{container_id}"))

    if not is_frozen and not is_blocked:
        builder.row(
            types.InlineKeyboardButton(text=lex.get('restart_button', '🔄 Рестарт'), callback_data=f"restart_bot:{container_id}"),
            types.InlineKeyboardButton(text=lex.get('delete_button', '🗑️ Удалить'), callback_data=f"delete_bot_start:{container_id}")
        )
    else:
        builder.row(types.InlineKeyboardButton(text=lex.get('delete_button', '🗑️ Удалить'), callback_data=f"delete_bot_start:{container_id}"))

    builder.row(types.InlineKeyboardButton(text=lex.get('get_logs_button', "📋 Логи"), callback_data=f"get_logs_start:{container_id}"))

    if not is_frozen and not is_blocked and container_info.get('tariff_id') != 'free':
         builder.row(
             types.InlineKeyboardButton(text=lex.get('extend_button', '⏳ Продлить'), callback_data=f"extend_bot_start:{container_id}"),
         )
         builder.row(
             types.InlineKeyboardButton(text=lex.get('upgrade_cpu_button', '⚡️ Увеличить CPU'), callback_data=f"upgrade_cpu_start:{container_id}"),
             types.InlineKeyboardButton(text=lex.get('upgrade_ram_button', '🧠 Увеличить RAM'), callback_data=f"upgrade_ram_start:{container_id}")
         )

    if is_admin_view:
        builder.row(types.InlineKeyboardButton(text=lex.get('change_time_button', '⏳ Изменить время'), callback_data=f"admin_change_time_start:{container_id}"))
        builder.row(types.InlineKeyboardButton(text=lex.get('admin_change_server_button', "⇄ Сменить сервер"), callback_data=f"admin_change_server_start:{container_id}"))

    login_buttons = []
    login_url = container_info.get('login_url')
    if not login_url:
        host = SERVERS.get(container_info['server_id'], {}).get('ip', 'N/A')
        login_url = f"http://{host}:{container_info['external_port']}"
    
    login_buttons.append(types.InlineKeyboardButton(text=lex.get('login_button', '🚪 Войти'), url=login_url))

    image_id = container_info.get('image_id')
    if image_id in ['heroku', 'legacy']:
        login_buttons.append(types.InlineKeyboardButton(text=lex.get('interactive_login_button', '💬 Интерактивный вход'), callback_data=f"interactive_login:{container_id}"))

    builder.row(*login_buttons)

    builder.row(
        types.InlineKeyboardButton(text=lex.get('change_name_button', "📝 Сменить имя"), callback_data=f"change_name_start:{container_id}"),
        types.InlineKeyboardButton(text=lex['change_image_button'], callback_data=f"change_image_start:{container_id}")
    )

    if not is_admin_view:
        builder.row(types.InlineKeyboardButton(text=lex['change_server_button'], callback_data=f"change_server_start:{container_id}"))

    builder.row(types.InlineKeyboardButton(text=lex['reinstall_button'], callback_data=f"reinstall_bot_start:{container_id}"))

    if not is_frozen and not is_blocked and container_info.get('tariff_id') != 'free':
        builder.row(types.InlineKeyboardButton(text=lex.get('transfer_bot_button', "🎁 Передать контейнер"), callback_data=f"transfer_bot_start:{container_id}"))

    if is_admin_view:
        back_text = lex.get('back_to_containers_list_button', "⬅️ Назад")
        back_data = f"containers_page:{from_page}" if not admin_back_callback else admin_back_callback
        builder.row(types.InlineKeyboardButton(text=back_text, callback_data=back_data))
    else:
        builder.row(types.InlineKeyboardButton(text=lex.get('back_to_my_userbots_button', "⬅️ Назад к списку"), callback_data="my_userbots"))

    return builder.as_markup()
