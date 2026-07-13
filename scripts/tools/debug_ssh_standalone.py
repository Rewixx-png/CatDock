from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
import logging
import asyncio
import traceback
import html
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import database as db
from config import TARIFFS, IMAGES
from keyboards import get_simple_confirmation_keyboard
from states.user_states import ReinstallState
import utils.docker as dm
from lexicon import LEXICON
from handlers.common.menu_utils import show_management_menu
from roles import UserRole 
from utils.action_logger import log_action
from utils.ssh_runner import run_command_on_server

router = Router()

@router.callback_query(F.data.startswith("reinstall_bot_start:"))
async def reinstall_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        container_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    
    await state.set_state(ReinstallState.confirming_reinstall)
    await state.update_data(container_id=container_id)
    
    await callback.message.edit_caption(
        caption=LEXICON[language_code]['reinstall_confirm_text'], 
        reply_markup=get_simple_confirmation_keyboard(language_code, "confirm_reinstall", "cancel_change")
    )
    await callback.answer()

@router.callback_query(ReinstallState.confirming_reinstall, F.data == "confirm_reinstall")
async def reinstall_confirm(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    container_id = data.get('container_id')
    
    if not container_id:
        await callback.answer("Ошибка состояния", show_alert=True)
        return

    container = await db.get_container_by_id(container_id)
    if not container:
        await callback.answer("❌ Контейнер не найден в БД.", show_alert=True)
        return

    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await callback.message.edit_caption(caption="⏳ <b>Диагностика SSH...</b>", reply_markup=None)
        await callback.answer()
    except TelegramBadRequest: 
        pass

    try:
        
        await run_command_on_server(container['server_id'], "whoami", timeout=10)

        await callback.message.edit_caption(caption="⏳ <b>Удаление старого контейнера...</b>")

        try:
            await dm.delete_container(container['server_id'], container['container_name'])
        except Exception as e:
            logging.warning(f"Ошибка при удалении старого контейнера (не критично): {e}")

        await asyncio.sleep(2)

        await callback.message.edit_caption(caption="⏳ <b>Создание нового контейнера...</b>")

        tariff = TARIFFS[container['tariff_id']]
        image = IMAGES[container['image_id']]
        user_profile = await db.get_user_profile(callback.from_user.id)
        username_to_use = user_profile.get('username') if user_profile else str(callback.from_user.id)

        new_name, new_port, login_url = await dm.create_container(
            user_id=container['user_id'],
            username=username_to_use,
            server_id=container['server_id'],
            tariff=tariff,
            image=image,
            forced_name=None 
        )

        if not all([new_name, new_port, login_url]):
            raise Exception("Docker API вернул пустые данные после создания.")

        await callback.message.edit_caption(caption="⏳ <b>Обновление базы данных...</b>")

        await db.update_container_server(container_id, container['server_id'], new_port, new_name, login_url)

        if container['is_frozen']:
            await db.set_container_frozen_state(container_id, False)
        if container.get('is_login_pending'):
            await db.set_container_login_pending(container_id, False)

        await db.set_container_web_loading(container_id, True)

        user_role = await db.get_user_role(callback.from_user.id)
        is_admin_action = user_role and user_role >= UserRole.ADMIN and callback.from_user.id != container['user_id']
        target_user = await bot.get_chat(container['user_id']) if is_admin_action else None

        await log_action(bot, callback.from_user, f"переустановил контейнер (старое имя: {container['container_name']}, новое: {new_name})", target_user)

        try:
            await callback.answer("✅ Успешно переустановлено!", show_alert=True)
        except TelegramBadRequest: pass

        if is_admin_action:
            try:
                user_lang = await db.get_user_language(container['user_id']) or 'ru'
                notif = LEXICON[user_lang].get('admin_reinstalled_container_notification').format(container_name=new_name)
                await bot.send_message(container['user_id'], notif)
            except Exception: pass

        await asyncio.sleep(1)

    except Exception as e:
        
        tb = traceback.format_exc()
        error_msg_user = f"❌ <b>ОШИБКА SSH/DOCKER</b>\n\n<pre>{html.escape(str(e))}</pre>"

        logging.error(f"Reinstall CRASH {container_id}: {e}\n{tb}")

        try:
            await callback.message.answer(error_msg_user)
            await callback.answer("Критическая ошибка", show_alert=True)
        except Exception: pass

    is_admin_view = False
    if 'user_role' in locals() and user_role and user_role >= UserRole.ADMIN:
        is_admin_view = True

    await show_management_menu(callback, container_id, state, bot, is_admin_view=is_admin_view)
