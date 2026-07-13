import json
import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext

from utils.filters import IsAdmin
from roles import UserRole
from keyboards.admin import (
    get_server_management_keyboard,
    get_server_delete_keyboard,
    get_server_delete_confirm_keyboard,
    get_cancel_admin_action_keyboard,
    get_server_edit_list_keyboard,
    get_server_edit_details_keyboard
)
from states.user_states import ServerAddState, ServerDeleteState, ServerEditState
from utils import bot_state
from utils.server_loader import load_servers_to_cache
from .main_menu import send_admin_panel_menu
import database as db
from config import SERVERS, SERVER_REPORT_CHAT_ID, SERVER_REPORT_TOPIC_ID
from utils.ui_utils import safe_edit_caption, safe_callback_answer, safe_delete_message, safe_edit_text

router = Router()
router.callback_query.filter(IsAdmin(min_level=UserRole.CO_OWNER)) 
router.message.filter(IsAdmin(min_level=UserRole.CO_OWNER))

async def show_server_management_menu(callback: types.CallbackQuery):
    await send_admin_panel_menu(
        callback,
        "🕹️ <b>Управление серверами</b>\n\nЗдесь можно добавлять, удалять, редактировать и переключать серверы.",
        get_server_management_keyboard()
    )

@router.callback_query(F.data == "manage_servers")
async def manage_servers_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_server_management_menu(callback)
    await safe_callback_answer(callback)

@router.callback_query(F.data.startswith("toggle_server_status:"))
async def toggle_server_status_handler(callback: types.CallbackQuery, bot: Bot):
    server_id = callback.data.split(":")[1]

    current_state = bot_state.server_states.get(server_id, True)
    new_state = not current_state
    bot_state.server_states[server_id] = new_state

    await db.set_bot_setting('server_states', json.dumps(bot_state.server_states))
    await db.update_server_status(server_id, new_state)

    if server_id in bot_state.servers_cache:
        bot_state.servers_cache[server_id]['active'] = new_state

    status_text_log = "ВКЛЮЧЕН 🟢" if new_state else "ВЫКЛЮЧЕН 🔴"
    server_name = SERVERS.get(server_id, {}).get('name', server_id)

    await safe_callback_answer(callback, f"Сервер {server_id} теперь {status_text_log}")

    if SERVER_REPORT_CHAT_ID and SERVER_REPORT_TOPIC_ID:
        try:
            admin_name = callback.from_user.full_name
            log_message = (
                f"🕹 <b>ИЗМЕНЕНИЕ СТАТУСА СЕРВЕРА</b>\n\n"
                f"<b>Сервер:</b> {server_name} (<code>{server_id}</code>)\n"
                f"<b>Новый статус:</b> {status_text_log}\n"
                f"<b>Администратор:</b> {admin_name}"
            )
            await bot.send_message(
                chat_id=SERVER_REPORT_CHAT_ID,
                message_thread_id=SERVER_REPORT_TOPIC_ID,
                text=log_message,
                parse_mode="HTML"
            )
        except Exception: pass

    await show_server_management_menu(callback)

@router.callback_query(F.data == "admin_server_add")
async def server_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ServerAddState.waiting_for_id)
    await safe_edit_caption(
        callback.message,
        caption="<b>Шаг 1/4:</b> Введите ID сервера (латиница, без пробелов).\nПример: <code>de-7</code>",
        reply_markup=get_cancel_admin_action_keyboard("manage_servers")
    )
    await safe_callback_answer(callback)

@router.message(ServerAddState.waiting_for_id)
async def server_add_id(message: types.Message, state: FSMContext):
    server_id = message.text.strip().lower()
    if not server_id or " " in server_id:
        await message.reply("❌ Некорректный ID. Используйте латиницу, цифры и дефис.")
        return

    if server_id in SERVERS:
        await message.reply("❌ Сервер с таким ID уже существует.")
        return

    await state.update_data(server_id=server_id)
    await state.set_state(ServerAddState.waiting_for_name)
    await message.answer("<b>Шаг 2/4:</b> Введите красивое имя сервера (с флагом).\nПример: <code>DE-7 🇩🇪 (Fast)</code>")

@router.message(ServerAddState.waiting_for_name)
async def server_add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(ServerAddState.waiting_for_ip)
    await message.answer("<b>Шаг 3/4:</b> Введите IP-адрес сервера.\nПример: <code>192.168.1.1</code>")

@router.message(ServerAddState.waiting_for_ip)
async def server_add_ip(message: types.Message, state: FSMContext):
    ip = message.text.strip()
    await state.update_data(ip=ip)
    await state.set_state(ServerAddState.waiting_for_password)
    await message.answer(
        "<b>Шаг 4/4:</b> Введите root-пароль сервера.\n"
        "<i>(Сообщение будет удалено после обработки)</i>"
    )

@router.message(ServerAddState.waiting_for_password)
async def server_add_password(message: types.Message, state: FSMContext, bot: Bot):
    password = message.text.strip()
    await safe_delete_message(bot, message.chat.id, message.message_id)

    data = await state.get_data()

    status_msg = await message.answer("⏳ Добавляю сервер в базу и обновляю кэш...")

    try:
        default_limits = {'free': 5, 'basic': 10, 'medium': 10, 'large': 5}

        await db.add_server(
            server_id=data['server_id'],
            name=data['name'],
            ip=data['ip'],
            ssh_user='root',
            password=password,
            check_port=22,
            limits=default_limits
        )

        await load_servers_to_cache()

        await safe_edit_text(
            status_msg,
            f"✅ <b>Сервер {data['name']} успешно добавлен!</b>\n\n"
            f"ID: <code>{data['server_id']}</code>\n"
            f"IP: <code>{data['ip']}</code>\n"
            f"Лимиты установлены по умолчанию."
        )

    except Exception as e:
        await safe_edit_text(status_msg, f"❌ Ошибка при добавлении: {e}")

    await state.clear()

@router.callback_query(F.data == "admin_server_edit_list")
async def server_edit_list(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ServerEditState.choosing_server)
    await safe_edit_caption(
        callback.message,
        caption="✏️ <b>Редактирование сервера</b>\n\nВыберите сервер, параметры которого хотите изменить.",
        reply_markup=get_server_edit_list_keyboard()
    )
    await safe_callback_answer(callback)

@router.callback_query(ServerEditState.choosing_server, F.data.startswith("admin_server_edit_select:"))
async def server_edit_details(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]

    await state.update_data(server_id=server_id)
    await _show_server_details(callback, server_id, state)

async def _show_server_details(callback: types.CallbackQuery, server_id: str, state: FSMContext):
    server_info = SERVERS.get(server_id)
    if not server_info:
        await safe_callback_answer(callback, "Сервер не найден в кэше.", show_alert=True)
        return

    await state.set_state(ServerEditState.viewing_details)

    text = (
        f"🖥 <b>Сервер:</b> {server_info['name']}\n\n"
        f"<b>ID:</b> <code>{server_id}</code>\n"
        f"<b>IP:</b> <code>{server_info['ip']}</code>\n"
        f"<b>SSH Порт:</b> <code>{server_info.get('check_port', 22)}</code>\n"
        f"<b>User:</b> <code>{server_info['user']}</code>\n"
        f"<b>Password:</b> <code>{server_info.get('password', '***')}</code>\n\n"
        f"Выберите параметр для изменения:"
    )

    await safe_edit_caption(
        callback.message,
        caption=text,
        reply_markup=get_server_edit_details_keyboard(server_id)
    )
    await safe_callback_answer(callback)

@router.callback_query(ServerEditState.viewing_details, F.data.startswith("edit_srv:"))
async def server_edit_field_start(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    field_name = parts[2]

    await state.update_data(editing_field=field_name)
    await state.set_state(ServerEditState.waiting_for_new_value)

    field_display = {
        'name': 'Имя сервера',
        'ip': 'IP адрес',
        'password': 'Пароль (root)',
        'check_port': 'SSH Порт'
    }.get(field_name, field_name)

    await safe_edit_caption(
        callback.message,
        caption=f"📝 Введите новое значение для <b>{field_display}</b>:",
        reply_markup=get_cancel_admin_action_keyboard("admin_server_edit_list") 
    )
    await safe_callback_answer(callback)

@router.message(ServerEditState.waiting_for_new_value)
async def server_edit_field_finish(message: types.Message, state: FSMContext, bot: Bot):
    new_value = message.text.strip()

    await safe_delete_message(bot, message.chat.id, message.message_id)

    data = await state.get_data()
    server_id = data.get('server_id')
    field = data.get('editing_field')

    if field == 'check_port':
        if not new_value.isdigit():
            await message.answer("❌ Порт должен быть числом.")
            return
        new_value = int(new_value)

    status_msg = await message.answer(f"⏳ Обновляю {field}...")

    try:
        await db.update_server_field(server_id, field, new_value)

        await load_servers_to_cache()

        await safe_edit_text(status_msg, "✅ Успешно обновлено!")
        await asyncio.sleep(1)
        await safe_delete_message(bot, message.chat.id, status_msg.message_id)


        server_info = SERVERS.get(server_id)
        if server_info:
            text = (
                f"🖥 <b>Сервер:</b> {server_info['name']}\n\n"
                f"<b>ID:</b> <code>{server_id}</code>\n"
                f"<b>IP:</b> <code>{server_info['ip']}</code>\n"
                f"<b>SSH Порт:</b> <code>{server_info.get('check_port', 22)}</code>\n"
                f"<b>User:</b> <code>{server_info['user']}</code>\n"
                f"<b>Password:</b> <code>{server_info.get('password', '***')}</code>\n\n"
                f"Выберите параметр для изменения:"
            )
            markup = get_server_edit_details_keyboard(server_id)

            await bot.send_message(message.chat.id, text=text, reply_markup=markup)

            await state.set_state(ServerEditState.viewing_details)
        else:
            await message.answer("Ошибка: Сервер не найден после обновления.")

    except Exception as e:
        await safe_edit_text(status_msg, f"❌ Ошибка обновления: {e}")

@router.callback_query(F.data == "admin_server_delete_menu")
async def server_delete_menu(callback: types.CallbackQuery, state: FSMContext):
    await safe_edit_caption(
        callback.message,
        caption="🗑 <b>Удаление сервера</b>\n\nВыберите сервер, который хотите удалить из бота.",
        reply_markup=get_server_delete_keyboard()
    )
    await state.set_state(ServerDeleteState.choosing_server)
    await safe_callback_answer(callback)

@router.callback_query(ServerDeleteState.choosing_server, F.data.startswith("admin_server_delete_select:"))
async def server_delete_confirm(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]
    server_info = SERVERS.get(server_id)

    if not server_info:
        await safe_callback_answer(callback, "Сервер не найден.", show_alert=True)
        return

    await safe_edit_caption(
        callback.message,
        caption=f"‼️ <b>Ви впевнені, що хочете видалити {server_info['name']}?</b>\n\n"
                f"Це видалить запис з бази бота. Контейнери на цьому сервері стануть 'осиротілими'.",
        reply_markup=get_server_delete_confirm_keyboard(server_id)
    )
    await state.set_state(ServerDeleteState.confirming_deletion)
    await safe_callback_answer(callback)

@router.callback_query(ServerDeleteState.confirming_deletion, F.data.startswith("admin_server_delete_confirm:"))
async def server_delete_process(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]

    try:
        await db.delete_server(server_id)
        await load_servers_to_cache() 

        await safe_edit_caption(
            callback.message,
            caption=f"✅ Сервер {server_id} успішно видалено з конфігурації.",
            reply_markup=get_cancel_admin_action_keyboard("manage_servers")
        )
    except Exception as e:
        await safe_edit_caption(
            callback.message,
            caption=f"❌ Помилка при видаленні: {e}",
            reply_markup=get_cancel_admin_action_keyboard("manage_servers")
        )

    await state.clear()
