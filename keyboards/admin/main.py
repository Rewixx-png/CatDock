from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from lexicon import LEXICON
from roles import UserRole
import database as db
from config import WEB_APP_URL

async def get_admin_main_menu(user_id: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    user_role = await db.get_user_role(user_id)

    open_tickets = await db.get_all_tickets_by_status('open')
    ticket_badge = f" ({len(open_tickets)})" if open_tickets else ""

    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text="👥 Управление", callback_data="admin_menu_management"),
        types.InlineKeyboardButton(text="⚙️ Система", callback_data="admin_menu_system")
    )

    builder.row(
        types.InlineKeyboardButton(text="📢 Маркетинг", callback_data="admin_menu_marketing"),
        types.InlineKeyboardButton(text=f"📨 Тикеты{ticket_badge}", callback_data="admin_support_menu") 
    )

    builder.row(
        types.InlineKeyboardButton(text="🔄 Обновить дашборд", callback_data="admin_panel"),
        types.InlineKeyboardButton(text="🚪 Выход", callback_data="back_to_main_menu")
    )

    return builder.as_markup()

async def get_admin_management_menu(user_id: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    user_role = await db.get_user_role(user_id)
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex.get('manage_users_button', 'manage_users_button'), callback_data="manage_users"),
        types.InlineKeyboardButton(text="🔍 Поиск юзера", callback_data="admin_search_user")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('manage_containers_button', 'manage_containers_button'), callback_data="manage_containers"),
        types.InlineKeyboardButton(text="🔍 Поиск контейнера", callback_data="admin_search_container_by_id")
    )

    if user_role >= UserRole.SENIOR_ADMIN:
        builder.row(
            types.InlineKeyboardButton(text="🎁 Выдать контейнер", callback_data="give_admin_container_start"), 
            types.InlineKeyboardButton(text="👑 Админ-контейнеры", callback_data="admin_containers_menu")
        )

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_admin_panel_button', 'back_to_admin_panel_button'), callback_data="admin_panel"))
    return builder.as_markup()

async def get_admin_system_menu(user_id: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    user_role = await db.get_user_role(user_id)
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text="📊 Диагностика", callback_data="admin_diagnostics"),
        types.InlineKeyboardButton(text=lex.get('bot_settings_button', 'bot_settings_button'), callback_data="bot_settings")
    )

    if user_role >= UserRole.CO_OWNER:
        builder.row(
            types.InlineKeyboardButton(text="🕹️ Серверы", callback_data="manage_servers"),
            types.InlineKeyboardButton(text="⌨️ Терминал", callback_data="terminal_menu")
        )
        builder.row(
            types.InlineKeyboardButton(text="🔄 Обновить образы", callback_data="admin_update_images"),
            types.InlineKeyboardButton(text="💾 Бэкап БД", callback_data="/backup") 
        )

    if user_role >= UserRole.SENIOR_ADMIN:
        builder.row(
            types.InlineKeyboardButton(text="🧹 Очистка сессий", callback_data="/session"), 
            types.InlineKeyboardButton(text="💀 Зомби клинер", callback_data="/zombie")    
        )

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_admin_panel_button', 'back_to_admin_panel_button'), callback_data="admin_panel"))
    return builder.as_markup()

async def get_admin_marketing_menu(user_id: int, language_code: str = 'ru') -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(types.InlineKeyboardButton(text=lex.get('news_button_title', "📢 Новость"), callback_data="admin_send_news"))
    builder.row(types.InlineKeyboardButton(text=lex.get('mailing_button', "📬 Рассылка"), callback_data="start_broadcast"))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_admin_panel_button', 'back_to_admin_panel_button'), callback_data="admin_panel"))
    return builder.as_markup()
