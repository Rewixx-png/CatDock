import math
import logging
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder  

import database as db
import utils.docker as dm
from keyboards.admin import (
    get_container_list_keyboard, 
    get_cancel_admin_action_keyboard,
    get_admin_containers_menu_keyboard,
    get_admin_container_list_keyboard,
    get_user_containers_list_keyboard
)
from states.user_states import AdminContainersState, AdminManageContainerState
from ..common.menu_utils import show_management_menu
from .main_menu import send_admin_panel_menu
from utils.filters import IsAdmin
from lexicon import LEXICON
from roles import UserRole
from utils.action_logger import log_action
from config import SERVERS, WEB_APP_URL
from utils.ui_utils import safe_edit_text, safe_edit_caption, safe_delete_message, safe_callback_answer

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

@router.message(Command("cont"), IsAdmin(min_level=UserRole.ADMIN))
async def cmd_cont_action(message: types.Message, command: CommandObject, bot: Bot, state: FSMContext):
    args = command.args

    if args and args.startswith("check"):
        parts = args.split()
        target_id = None

        if len(parts) > 1:
            arg_val = parts[1]
            if arg_val.isdigit():
                 target_id = int(arg_val)
                 container = await db.get_container_by_id(target_id)
            else:
                 container = await db.get_container_by_name(arg_val)

            if container:
                await _open_container_menu(message, container['id'], state, bot)
                return
            else:
                await message.reply(f"❌ Контейнер '{arg_val}' не найден.")
                return

        elif message.reply_to_message and message.reply_to_message.from_user:
            target_user_id = message.reply_to_message.from_user.id
            containers = await db.get_user_containers(target_user_id)

            if not containers:
                await message.reply("❌ У этого пользователя нет контейнеров.")
                return

            if len(containers) == 1:
                await _open_container_menu(message, containers[0]['id'], state, bot)
            else:
                text = f"🐳 <b>Контейнеры пользователя:</b> {message.reply_to_message.from_user.full_name}\n\nВыберите контейнер для инспекции:"
                markup = await get_user_containers_list_keyboard(containers, target_user_id, 0, 'ru')
                await message.reply(text, reply_markup=markup)
            return
        else:
            await message.reply("⚠️ Укажите ID или Имя контейнера, или сделайте реплай.\nПример: <code>/cont check 123</code> или <code>/cont check cat-bot-xxx</code>")
            return

    if not args:
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/cont <action> <ID|Name></code>\n"
            "Доступно: check, logs, start, stop, restart, freeze, unfreeze, block, unblock, delete\n"
            "Пример: <code>/cont logs cat-username-123</code>"
        )
        return

    parts = args.split()
    if len(parts) != 2:
        await message.reply("⚠️ Неверный формат аргументов. Требуется действие и ID/Имя.")
        return

    action, container_arg = parts[0].lower(), parts[1]
    allowed_actions = ['start', 'stop', 'restart', 'freeze', 'unfreeze', 'block', 'unblock', 'delete', 'logs']

    if action not in allowed_actions:
        await message.reply(f"⚠️ Неизвестное действие. Доступно: check, {', '.join(allowed_actions)}")
        return

    if container_arg.isdigit():
        container_id = int(container_arg)
        container = await db.get_container_by_id(container_id)
    else:
        container = await db.get_container_by_name(container_arg)
        if container:
            container_id = container['id']
        else:
            container_id = None

    if not container:
        await message.reply(f"❌ Контейнер '{container_arg}' не найден в базе данных.")
        return

    if container['server_id'] not in SERVERS:
        await message.reply(f"⚠️ Сервер <code>{container['server_id']}</code> не найден в конфигурации бота.")
        return

    status_msg = await message.reply(f"⏳ Выполняю <b>{action}</b> для контейнера <code>{container['container_name']}</code>...")

    try:
        if action == 'logs':
            token = await db.create_log_token(container_id)
            if not token:
                await safe_edit_text(status_msg, "❌ Ошибка при генерации токена логов.")
                return

            base_url = WEB_APP_URL.rstrip('/')
            logs_url = (
                f"{base_url}/terminal.html?token={token}"
                f"&container_id={container_id}"
            )

            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="🖥 Открыть CatDock Terminal", url=logs_url))

            await safe_edit_text(
                status_msg,
                f"📋 <b>Логи контейнера:</b> <code>{container['container_name']}</code>\n"
                f"ID: {container_id} | Server: {container['server_id']}",
                reply_markup=builder.as_markup()
            )
            return

        elif action == 'start':
            await dm.start_container(container['server_id'], container['container_name'])
            if container.get('is_frozen'):
                await db.set_container_frozen_state(container_id, False)

        elif action == 'stop':
            await dm.stop_container(container['server_id'], container['container_name'])

        elif action == 'restart':
            await dm.restart_container(container['server_id'], container['container_name'])

        elif action == 'freeze':
            await dm.stop_container(container['server_id'], container['container_name'])
            await db.set_container_frozen_state(container_id, True)

        elif action in ['unfreeze', 'unblock']:
            await dm.start_container(container['server_id'], container['container_name'])
            await db.set_container_frozen_state(container_id, False)
            if container.get('is_blocked'):
                await db.set_container_blocked_state(container_id, False)

        elif action == 'block':
            await dm.stop_container(container['server_id'], container['container_name'])
            await db.set_container_frozen_state(container_id, True)
            await db.set_container_blocked_state(container_id, True)

        elif action == 'delete':
            await dm.delete_container(container['server_id'], container['container_name'])
            await db.delete_user_container(container_id)

        await safe_edit_text(status_msg, f"✅ Действие <b>{action}</b> успешно выполнено для контейнера #{container_id}.")

        target_user = await bot.get_chat(container['user_id'])
        await log_action(bot, message.from_user, f"выполнил команду /cont {action} для контейнера #{container_id}", target_user)

        try:
            if action == 'block':
                await bot.send_message(
                    container['user_id'],
                    f"⛔️ Ваш контейнер <b>{container['container_name']}</b> был заблокирован администратором. Доступ ограничен."
                )
            elif action in ['unfreeze', 'unblock'] and (container.get('is_blocked') or container.get('is_frozen')):
                await bot.send_message(
                    container['user_id'],
                    f"✅ Ваш контейнер <b>{container['container_name']}</b> был разблокирован/разморожен администратором."
                )
            elif action == 'delete':
                await bot.send_message(
                    container['user_id'],
                    f"🗑️ Ваш контейнер <b>{container['container_name']}</b> был удален администратором."
                )
        except Exception:
            pass

    except Exception as e:
        logging.error(f"Admin /cont error for container {container_id}: {e}", exc_info=True)
        await safe_edit_text(status_msg, f"❌ Ошибка при выполнении на сервере:\n<code>{e}</code>")

async def _open_container_menu(message: types.Message, container_id: int, state: FSMContext, bot: Bot):
    container = await db.get_container_by_id(container_id)
    if not container:
        await message.reply(f"❌ Контейнер #{container_id} не найден.")
        return

    await show_management_menu(
        event=message,
        container_id=container_id,
        state=state,
        bot=bot,
        is_admin_view=True,
        admin_back_callback="admin_container_list" 
    )

async def _get_admin_containers_page(callback: types.CallbackQuery):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    containers = await db.get_all_admin_containers()

    text = lex.get('admin_container_list_title', "📋 <b>Список админ-контейнеров</b>\n\n")
    if not containers:
        text += lex.get('admin_containers_not_found', "Админ-контейнеры еще не созданы.")

    await send_admin_panel_menu(
        callback, text, await get_admin_container_list_keyboard(containers, language_code)
    )

@router.callback_query(F.data == "admin_containers_menu", IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def admin_containers_menu(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    await send_admin_panel_menu(
        callback,
        lex.get('admin_containers_menu_title', "👑 <b>Управление админ-контейнерами</b>"),
        await get_admin_containers_menu_keyboard(language_code)
    )

@router.callback_query(F.data == "admin_container_list", IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def admin_container_list_handler(callback: types.CallbackQuery):
    await _get_admin_containers_page(callback)
    await safe_callback_answer(callback)

async def manage_containers_menu(message: types.Message | types.CallbackQuery, state: FSMContext, bot: Bot):
    await _get_containers_page(0, message, state, bot, sort_by='time')

async def _get_containers_page(page: int, message: types.Message | types.CallbackQuery, state: FSMContext, bot: Bot, sort_by: str = 'time'):
    await state.set_state(AdminContainersState.viewing_list)
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    containers, total_count = await db.get_all_containers_paginated(page, page_size=5, sort_by=sort_by)
    total_pages = math.ceil(total_count / 5)

    text = f"🐳 <b>Список всех контейнеров</b> (Стр. {page + 1}/{total_pages})\n\n"
    if not containers:
        text += "Контейнеры в системе отсутствуют."

    await send_admin_panel_menu(
        message, text, get_container_list_keyboard(containers, page, total_pages, sort_by, language_code)
    )

@router.callback_query(F.data.startswith("containers_page:"))
async def containers_page_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(AdminContainersState.viewing_list)

    parts = callback.data.split(":")
    page = int(parts[1])
    sort_by = parts[2] if len(parts) > 2 else 'time'
    await _get_containers_page(page, callback, state, bot, sort_by=sort_by)
    await safe_callback_answer(callback)

@router.callback_query(AdminContainersState.viewing_list, F.data.startswith("sort_containers:"))
async def containers_sort_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    sort_by = callback.data.split(":")[1]
    await _get_containers_page(0, callback, state, bot, sort_by=sort_by)
    await safe_callback_answer(callback, f"Отсортировано по: {sort_by}")

@router.callback_query(F.data == "admin_search_container_by_id")
async def search_container_start(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await state.set_state(AdminContainersState.waiting_for_id)

    await safe_edit_caption(
        callback.message,
        caption=lex.get('admin_prompt_container_id', "Введите ID контейнера для поиска:"),
        reply_markup=get_cancel_admin_action_keyboard("manage_containers", language_code)
    )
    await safe_callback_answer(callback)

@router.message(AdminContainersState.waiting_for_id)
async def process_container_search(message: types.Message, state: FSMContext, bot: Bot):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        container_id_to_find = int(message.text)
    except (ValueError, TypeError):
        await message.reply("❌ Введите корректный ID (только цифры).")
        return

    data = await state.get_data()
    prompt_id = data.get('prompt_message_id')

    await safe_delete_message(bot, message.chat.id, message.message_id)
    if prompt_id:
        await safe_delete_message(bot, message.chat.id, prompt_id)

    container = await db.get_container_by_id(container_id_to_find)

    if container:
        await log_action(bot, message.from_user, f"нашел контейнер по ID {container_id_to_find}")
        await state.clear()
        await show_management_menu(
            event=message, 
            container_id=container_id_to_find, 
            state=state,
            bot=bot,
            is_admin_view=True
        )
    else:
        await message.answer(
            lex.get('admin_container_not_found').format(container_id=container_id_to_find)
        )
        await manage_containers_menu(message, state, bot)

@router.callback_query(F.data == "admin_search_container_by_name")
async def search_container_by_name_start(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await state.set_state(AdminContainersState.waiting_for_name)

    await safe_edit_caption(
        callback.message,
        caption="Введите точное имя контейнера для поиска (например, `cat-user-abcdef`):",
        reply_markup=get_cancel_admin_action_keyboard("manage_containers", language_code)
    )
    await safe_callback_answer(callback)

@router.message(AdminContainersState.waiting_for_name)
async def process_container_name_search(message: types.Message, state: FSMContext, bot: Bot):
    container_name_to_find = message.text.strip()

    data = await state.get_data()
    prompt_id = data.get('prompt_message_id')

    await safe_delete_message(bot, message.chat.id, message.message_id)
    if prompt_id:
        await safe_delete_message(bot, message.chat.id, prompt_id)

    container = await db.get_container_by_name(container_name_to_find)

    if container:
        await log_action(bot, message.from_user, f"нашел контейнер по имени '{container_name_to_find}'")
        await state.clear()
        await show_management_menu(
            event=message, 
            container_id=container['id'], 
            state=state,
            bot=bot,
            is_admin_view=True
        )
    else:
        await message.answer(f"❌ Контейнер с именем <code>{container_name_to_find}</code> не найден.")
        await manage_containers_menu(message, state, bot)

@router.callback_query(F.data.startswith("manage_bot:"))
async def admin_manage_bot_entry(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await safe_callback_answer(callback, "⏳ Загружаю меню управления...")
    parts = callback.data.split(":")
    container_id = int(parts[1])
    container = await db.get_container_by_id(container_id)
    if not container: return

    admin_id = callback.from_user.id
    is_admin_view = True
    if admin_id == container['user_id']:
        is_admin_view = False
    else:
        target_user = await bot.get_chat(container['user_id'])
        await log_action(bot, callback.from_user, f"вошел в меню управления контейнером '{container['container_name']}' (ID: {container_id})", target_user)

    from_page = 0
    admin_back_callback = None
    if len(parts) > 2:
        context = parts[2]
        if context == 'user':
            target_user_id = int(parts[3])
            from_page = int(parts[4]) if len(parts) > 4 else 0
            admin_back_callback = f"admin_view_user_containers:{target_user_id}:{from_page}"
        elif context == 'admin_list':
             admin_back_callback = "admin_container_list"
        else:
            from_page = int(context)

    await show_management_menu(
        callback, container_id, state, bot,
        is_admin_view=is_admin_view, from_page=from_page, admin_back_callback=admin_back_callback
    )

@router.callback_query(F.data.startswith("admin_change_time_start:"), IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def admin_change_time_start(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await state.set_state(AdminManageContainerState.changing_time)
    await safe_delete_message(callback.bot, callback.message.chat.id, callback.message.message_id)
    sent_message = await callback.message.answer(
        f"Введите количество дней для контейнера #{container_id}.\n`30` (добавить 30 дн.) или `-7` (отнять 7 дн.).",
        reply_markup=get_cancel_admin_action_keyboard("admin_panel", language_code)
    )
    await state.update_data(target_container_id=container_id, prompt_message_id=sent_message.message_id)
    await safe_callback_answer(callback)

@router.message(AdminManageContainerState.changing_time, IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def process_time_change(message: types.Message, state: FSMContext, bot: Bot):
    try:
        days_to_add = int(message.text)
    except (ValueError, TypeError):
        await message.answer("❌ Введите корректное целое число.")
        return

    data = await state.get_data()
    target_container_id = data['target_container_id']
    prompt_message_id = data.get('prompt_message_id')

    if prompt_message_id:
        await safe_delete_message(bot, message.chat.id, prompt_message_id)
    await safe_delete_message(bot, message.chat.id, message.message_id)

    await db.admin_update_container_time(target_container_id, days_to_add)
    await message.answer(f"✅ Время для контейнера #{target_container_id} изменено на {days_to_add} дней.")

    container = await db.get_container_by_id(target_container_id)
    if container:
        target_user = await bot.get_chat(container['user_id'])
        await log_action(bot, message.from_user, f"изменил время контейнера '{container['container_name']}' на {days_to_add} дней", target_user)
        try:
            language_code = await db.get_user_language(container['user_id']) or 'ru'
            lex = LEXICON[language_code]
            notification_text = lex.get('admin_changed_container_time_notification').format(
                container_name=container['container_name'],
                days=days_to_add
            )
            await bot.send_message(container['user_id'], notification_text)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logging.warning(f"Не удалось отправить уведомление об изменении времени пользователю {container['user_id']}: {e}")

    await state.clear()

@router.callback_query(F.data == "manage_containers")
async def manage_containers_menu_entry(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await manage_containers_menu(callback, state, bot)
