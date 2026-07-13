import asyncio
import logging
from datetime import datetime
from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from database.admin_queries import get_dashboard_stats
from keyboards.admin.main import (
    get_admin_main_menu, 
    get_admin_management_menu, 
    get_admin_system_menu, 
    get_admin_marketing_menu
)
from keyboards.admin import get_bot_settings_keyboard, get_cancel_admin_action_keyboard
from keyboards import get_simple_confirmation_keyboard

from lexicon import LEXICON
from utils import bot_state

from utils.filters import IsAdmin
from roles import UserRole
from utils.action_logger import log_action
from utils.ui_utils import safe_edit_caption

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

async def send_admin_panel_menu(message: types.Message | types.CallbackQuery, text: str, markup):
    bot = message.bot if isinstance(message, types.Message) else message.message.bot
    target_chat = message.chat.id if isinstance(message, types.Message) else message.message.chat.id
    await bot.send_message(chat_id=target_chat, text=text, reply_markup=markup)

@router.callback_query(F.data == "admin_panel")
@router.message(Command("admin"), F.text.regexp(r"^/admin(@[a-zA-Z0-9_]+)?\s*$"))
async def admin_dashboard(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'

    stats, error = await get_dashboard_stats()

    dt_now = datetime.now().strftime("%d.%m %H:%M")

    status_emoji = "🟢" if not bot_state.maintenance_mode else "🟠 TECH"
    raid_emoji = "🛡️" if bot_state.raid_mode else ""

    dashboard_text = (
        f"👑 <b>ADMIN CONSOLE</b> <code>v4.1.0</code>\n"
        f"🕒 {dt_now} | {status_emoji} {raid_emoji}\n\n"

        f"📊 <b>Живая статистика:</b>\n"
        f"👥 Пользователей: <b>{stats.get('total_users', 0)}</b>\n"
        f"🐳 Контейнеров: <b>{stats.get('active_containers', 0)}</b> (активных)\n"
        f"💰 Оборот (24ч): <b>{stats.get('revenue_24h', 0):.2f} RUB</b>\n"
        f"🎫 Тикеты: <b>{stats.get('open_tickets', 0)}</b> ожидает\n"
    )

    if error:
        dashboard_text += f"\n⚠️ <i>DB Warning: {error}</i>"

    dashboard_text += "\n👇 <b>Выберите модуль управления:</b>"

    markup = await get_admin_main_menu(user_id, language_code)

    if isinstance(event, types.CallbackQuery):
        try:
            await event.answer("Дашборд обновлен")
        except: pass

    await send_admin_panel_menu(event, dashboard_text, markup)

@router.callback_query(F.data == "admin_menu_management")
async def show_management_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'

    text = (
        "👥 <b>Управление ресурсами</b>\n\n"
        "Здесь вы можете управлять пользователями, контейнерами и их подписками.\n"
        "Используйте поиск для быстрых действий."
    )
    markup = await get_admin_management_menu(user_id, language_code)
    await send_admin_panel_menu(callback, text, markup)
    await callback.answer()

@router.callback_query(F.data == "admin_menu_system")
async def show_system_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'

    text = (
        "⚙️ <b>Системные настройки</b>\n\n"
        "Управление серверами (нодами), глобальные настройки бота, логи и диагностика."
    )
    markup = await get_admin_system_menu(user_id, language_code)
    await send_admin_panel_menu(callback, text, markup)
    await callback.answer()

@router.callback_query(F.data == "admin_menu_marketing")
async def show_marketing_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'

    text = (
        "📢 <b>Рассылки</b>\n\n"
        "Отправка служебных сообщений всем пользователям CatDock."
    )
    markup = await get_admin_marketing_menu(user_id, language_code)
    await send_admin_panel_menu(callback, text, markup)
    await callback.answer()

@router.callback_query(F.data == "admin_support_menu")
async def open_support_web(callback: types.CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))

    await send_admin_panel_menu(
        callback,
        "📨 <b>Поддержка</b>\n\nВеб-панель тикетов удалена из CatDock. "
        "Для связи используются настроенные Telegram-каналы поддержки.",
        builder.as_markup(),
    )
    await callback.answer()

@router.message(Command("restart"), IsAdmin(min_level=UserRole.CO_OWNER))
async def cmd_restart(message: types.Message):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    confirmation_text = lex.get('restart_confirmation_text', "⚠️ Вы уверены, что хотите перезапустить бота?")

    await message.answer(
        text=confirmation_text,
        reply_markup=get_simple_confirmation_keyboard(language_code, "admin_restart_do", "admin_cancel_restart")
    )
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "admin_cancel_restart", IsAdmin(min_level=UserRole.CO_OWNER))
async def cancel_restart(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.answer("Перезапуск отменен.")

@router.callback_query(F.data == "admin_restart_bot_confirm", IsAdmin(min_level=UserRole.CO_OWNER))
async def confirm_restart_bot(callback: types.CallbackQuery):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    confirmation_text = lex.get('restart_confirmation_text', "⚠️ Вы уверены, что хотите перезапустить бота? Текущее соединение будет разорвано.")
    await safe_edit_caption(
        callback.message,
        caption=confirmation_text,
        reply_markup=get_simple_confirmation_keyboard(language_code, "admin_restart_do", "bot_settings")
    )
    await callback.answer()

@router.callback_query(F.data == "admin_restart_do", IsAdmin(min_level=UserRole.CO_OWNER))
async def do_restart_bot(callback: types.CallbackQuery, bot: Bot):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    alert_text = lex.get('restart_initiated_alert', "✅ Команда на перезапуск отправлена.")
    await callback.answer(alert_text, show_alert=True)
    try:
        await callback.message.delete()
    except TelegramBadRequest: pass
    logging.info(f"Администратор {callback.from_user.id} инициировал перезапуск бота.")
    await log_action(bot, callback.from_user, "инициировал перезапуск бота")
    command = "pm2 restart CatDock"
    try:
        asyncio.create_task(asyncio.create_subprocess_shell(command))
    except Exception: pass

@router.callback_query(F.data == "admin_roles_info")
async def admin_roles_info(callback: types.CallbackQuery):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    info_text = lex.get('roles_info_text', "Информация о ролях.")
    markup = get_cancel_admin_action_keyboard("admin_menu_system", language_code) 
    try:
        await callback.message.delete()
    except TelegramBadRequest: pass
    await callback.message.answer(text=info_text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "bot_settings")
async def bot_settings_menu(callback: types.CallbackQuery):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    await send_admin_panel_menu(
        callback,
        lex.get('bot_settings_title', 'bot_settings_title'),
        get_bot_settings_keyboard(bot_state.maintenance_mode, bot_state.raid_mode, language_code)
    )

@router.callback_query(F.data == "admin_clear_cache")
async def admin_clear_bot_cache(callback: types.CallbackQuery, bot: Bot):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])
    logging.info(f"Администратор {callback.from_user.id} запросил очистку кэша.")
    bot_state.user_profile_cache.clear()
    bot_state.user_role_cache.clear()
    bot_state.user_language_cache.clear()
    bot_state.user_block_cache.clear()
    bot_state.server_statuses_cache = []
    bot_state.server_status_last_update = 0.0
    bot_state.admin_ids_cache.clear()
    bot_state.admin_ids_cache.update(await db.get_all_admin_ids())
    await log_action(bot, callback.from_user, "выполнил полную очистку кэша бота")
    await callback.answer(lex.get('cache_cleared_notification', "Кэш очищен."), show_alert=True)
    await bot_settings_menu(callback)

@router.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance_mode(callback: types.CallbackQuery, bot: Bot):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    bot_state.maintenance_mode = not bot_state.maintenance_mode
    status = "включил" if bot_state.maintenance_mode else "выключил"
    await log_action(bot, callback.from_user, f"{status} режим технических работ")
    await callback.message.edit_reply_markup(
        reply_markup=get_bot_settings_keyboard(bot_state.maintenance_mode, bot_state.raid_mode, language_code)
    )
    status_text = LEXICON[language_code]['maintenance_mode_on'] if bot_state.maintenance_mode else LEXICON[language_code]['maintenance_mode_off']
    await callback.answer(f"Режим технических работ: {status_text}")

@router.callback_query(F.data == "toggle_raid_mode")
async def toggle_raid_mode(callback: types.CallbackQuery, bot: Bot):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    bot_state.raid_mode = not bot_state.raid_mode
    status = "включил" if bot_state.raid_mode else "выключил"
    await log_action(bot, callback.from_user, f"{status} рейд-контроль в чате")
    await callback.message.edit_reply_markup(
        reply_markup=get_bot_settings_keyboard(bot_state.maintenance_mode, bot_state.raid_mode, language_code)
    )
    status_text = LEXICON[language_code]['raid_mode_on'] if bot_state.raid_mode else LEXICON[language_code]['raid_mode_off']
    await callback.answer(f"Рейд-контроль: {status_text}")

@router.callback_query(F.data.startswith("cancel_admin_action"))
async def cancel_admin_action(callback: types.CallbackQuery, state: FSMContext):
    back_target = callback.data.split(":")[1] if ":" in callback.data else "admin_panel"
    await callback.answer("Действие отменено.")

    if back_target == "admin_panel":
        await admin_dashboard(callback, state)
    elif back_target == "manage_servers":
        await show_system_menu(callback)
    elif back_target == "manage_users":
        await show_management_menu(callback)
    elif back_target == "admin_menu_system":
        await show_system_menu(callback)
    elif back_target == "admin_menu_management":
        await show_management_menu(callback)
    else:
        await admin_dashboard(callback, state)

admin_main_menu = admin_dashboard
