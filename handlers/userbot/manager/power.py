import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext

import database as db
import utils.docker as dm
from lexicon import LEXICON
from roles import UserRole
from utils.action_logger import log_action
from handlers.common.menu_utils import show_management_menu
from .list import send_userbots_menu

from utils.worker_tasks import task_container_power_action

router = Router()

async def handle_simple_action(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    action_key: str, 
    log_action_ru: str,  
    ui_action_key: str,  
    bot: Bot
):

    user_lang = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[user_lang]

    ui_action_name = lex.get(ui_action_key, log_action_ru)

    await callback.answer(f"⏳ Задача принята: {ui_action_name}", show_alert=False)

    data = await state.get_data()
    try:
        container_id = data.get('container_id') or int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    container = await db.get_container_by_id(container_id)
    if not container:
        await send_userbots_menu(callback, state, send_new=True)
        return

    if container.get('is_blocked'):
        await callback.answer("❌ Контейнер заблокирован администратором.", show_alert=True)
        return

    if container.get('is_frozen', 0) and action_key not in ["stop"]: 
        await callback.answer("❌ Недоступно: UserBot заморожен.", show_alert=True)
        return

    await task_container_power_action.kiq(
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        username=callback.from_user.username,
        action=action_key,
        server_id=container['server_id'],
        container_name=container['container_name']
    )

    user_role = await db.get_user_role(callback.from_user.id)
    is_admin_view = user_role and user_role >= UserRole.ADMIN and callback.from_user.id != container['user_id']

    await show_management_menu(callback, container_id, state, bot, is_admin_view=is_admin_view)

@router.callback_query(F.data.startswith("start_bot:"))
async def start_bot_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await handle_simple_action(callback, state, "start", "запуск", "turn_on_button", bot)

@router.callback_query(F.data.startswith("stop_bot:"))
async def stop_bot_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await handle_simple_action(callback, state, "stop", "остановка", "turn_off_button", bot)

@router.callback_query(F.data.startswith("restart_bot:"))
async def restart_bot_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await handle_simple_action(callback, state, "restart", "перезагрузка", "restart_button", bot)

@router.callback_query(F.data.startswith("freeze_bot:"))
async def freeze_bot_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    try:
        container_id = data.get('container_id') or int(callback.data.split(":")[1])
    except (IndexError, ValueError): return

    container = await db.get_container_by_id(container_id)
    if container and container.get('is_blocked'): return

    await db.set_container_frozen_state(container_id, True)
    if container:
        try: await dm.stop_container(container['server_id'], container['container_name'])
        except: pass

    await callback.answer("❄️ Заморожено")

    user_role = await db.get_user_role(callback.from_user.id)
    is_admin_view = user_role and user_role >= UserRole.ADMIN and callback.from_user.id != container['user_id']
    await show_management_menu(callback, container_id, state, bot, is_admin_view=is_admin_view)

@router.callback_query(F.data.startswith("unfreeze_bot:"))
async def unfreeze_bot_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    try:
        container_id = data.get('container_id') or int(callback.data.split(":")[1])
    except (IndexError, ValueError): return

    container = await db.get_container_by_id(container_id)
    if not container or container.get('is_blocked'): return

    await db.set_container_frozen_state(container_id, False)

    await task_container_power_action.kiq(
        chat_id=callback.message.chat.id, user_id=callback.from_user.id,
        first_name=callback.from_user.first_name, username=callback.from_user.username,
        action='start', server_id=container['server_id'], container_name=container['container_name']
    )

    await callback.answer("🔥 Разморожено. Запускаем...")

    user_role = await db.get_user_role(callback.from_user.id)
    is_admin_view = user_role and user_role >= UserRole.ADMIN and callback.from_user.id != container['user_id']
    await show_management_menu(callback, container_id, state, bot, is_admin_view=is_admin_view)
