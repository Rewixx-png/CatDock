from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from lexicon import LEXICON
from config import SERVERS, TARIFFS, IMAGES
from roles import UserRole
from utils import bot_state
import settings

def get_creation_hub_keyboard(language_code: str, selection_data: dict) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    selected_tariff = selection_data.get('tariff_id')
    selected_image = selection_data.get('image_id')

    tariff_icon = "🔹" if selected_tariff else "💳" 
    tariff_label = TARIFFS[selected_tariff]['name'] if selected_tariff else lex.get('hub_tariff_select', "Тарифы")
    
    image_icon = "🔸" if selected_image else "💿"
    image_label = IMAGES[selected_image]['name'] if selected_image else lex.get('hub_image_select', "Образы")

    builder.row(
        types.InlineKeyboardButton(text=f"{tariff_icon} {tariff_label}", callback_data="create_select:tariff"),
        types.InlineKeyboardButton(text=f"{image_icon} {image_label}", callback_data="create_select:image")
    )

    manual_server = selection_data.get('manual_server_id')
    server_label = SERVERS[manual_server]['name'] if manual_server else lex.get('hub_manual_server', "Сервер")
    
    server_icon = "✅" if manual_server else "🌐"
    
    builder.row(types.InlineKeyboardButton(text=f"{server_icon} {server_label}", callback_data="manual_server_select"))

    if selected_tariff and selected_image:
        builder.row(types.InlineKeyboardButton(text=lex.get('hub_ready_create', "✅ Создать"), callback_data="create_hub:confirm"))
    else:
        builder.row(types.InlineKeyboardButton(text=lex.get('hub_not_ready', "⏳ Выберите параметры"), callback_data="create_hub:incomplete"))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_main_menu_button', 'back_to_main_menu_button'), callback_data="back_to_main_menu"))
    return builder.as_markup()

async def get_tariff_selection_for_hub(language_code: str, user_id: int) -> InlineKeyboardMarkup:
    import database as db 
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    user_has_used_free = await db.check_if_user_used_free_tariff(user_id)
    
    for tariff_id, tariff_info in TARIFFS.items():
        price_text = f"{tariff_info['price_rub']}₽" if tariff_info['price_rub'] > 0 else "Free"
        name = tariff_info['name']
        ram = tariff_info['ram_mb']
        
        if tariff_id == 'free' and user_has_used_free:
            builder.add(types.InlineKeyboardButton(text=f"🔒 {name} (Used)", callback_data="none"))
        else:
            
            builder.add(types.InlineKeyboardButton(text=f"⚡ {name} | {ram}MB | {price_text}", callback_data=f"create_set:tariff:{tariff_id}"))
            
    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="create_hub:back"))
    return builder.as_markup()

def get_image_selection_for_hub(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for image_id, image_info in IMAGES.items():
        
        builder.add(types.InlineKeyboardButton(text=f"{image_info['name']}", callback_data=f"create_set:image:{image_id}"))
    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="create_hub:back"))
    return builder.as_markup()

async def get_manual_server_selection_keyboard(language_code: str, user_id: int) -> InlineKeyboardMarkup:
    import database as db 
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    user_role = await db.get_user_role(user_id)
    is_privileged = (user_id in settings.VIP_USER_IDS) or (user_role and user_role >= UserRole.ADMIN)

    builder.row(types.InlineKeyboardButton(text="🤖 Авто (Auto)", callback_data="set_manual_server:auto"))

    for server_id, server_info in SERVERS.items():
        if not bot_state.server_states.get(server_id, True):
            continue

        is_exclusive = server_info.get('exclusive', False)
        if is_exclusive and not is_privileged:
            continue

        clean_name = server_info['name']
        builder.row(types.InlineKeyboardButton(text=f"{clean_name}", callback_data=f"set_manual_server:{server_id}"))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="create_hub:back"))
    return builder.as_markup()

def get_confirmation_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('confirm_creation_button', '✅ Поехали!'), callback_data="confirm_creation")
    )
    builder.row(
        types.InlineKeyboardButton(text=lex.get('hub_manual_server', '✏️ Изменить'), callback_data="create_hub:back"),
        types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="back_to_main_menu")
    )
    return builder.as_markup()

def get_server_selection_keyboard(language_code: str, ram_usages: dict) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for server_id, server_info in SERVERS.items():
        if not bot_state.server_states.get(server_id, True): continue
        usage = ram_usages.get(server_id)
        status_icon = '🟢' if usage and usage < 90 else '🔴'
        text = f"{status_icon} {server_info['name']} ({usage}%)"
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"select_server:{server_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="admin_panel"))
    return builder.as_markup()

async def get_tariff_selection_keyboard(server_id: str, user_id: int, language_code: str, discount_percent: int = 0) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for tariff_id, tariff_info in TARIFFS.items():
        if tariff_id == 'free': continue
        builder.row(types.InlineKeyboardButton(text=f"{tariff_info['name']}", callback_data=f"select_tariff:{tariff_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="admin_panel"))
    return builder.as_markup()

def get_image_selection_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for image_id, image_info in IMAGES.items():
        builder.row(types.InlineKeyboardButton(text=f"{image_info['name']}", callback_data=f"select_image:{image_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="admin_panel"))
    return builder.as_markup()
