import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
import logging
from asyncssh.process import ProcessError

import database as db
from config import TARIFFS, IMAGES, SERVERS
from keyboards import get_simple_confirmation_keyboard
from keyboards import get_change_server_keyboard
from states.user_states import AdminChangeServerState
import utils.docker as dm
from lexicon import LEXICON
from ..common.menu_utils import show_management_menu
from utils.filters import IsAdmin
from roles import UserRole
from utils.action_logger import log_action
from utils.ssh_runner import run_command_on_server
from utils import bot_state
from utils.ui_utils import safe_edit_caption

router = Router()
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

async def _perform_container_move(bot: Bot, admin_user: types.User, container_id: int, new_server_id: str):
    admin_id = admin_user.id
    language_code = await db.get_user_language(admin_id) or 'ru'
    lex = LEXICON[language_code]

    status_message = await bot.send_message(admin_id, f"🚀 Начинаю перенос контейнера #{container_id}...")

    old_container = await db.get_container_by_id(container_id)
    if not old_container:
        await status_message.edit_text("❌ Ошибка: Старый контейнер не найден в базе данных.")
        return

    new_container_name = None
    try:
        await status_message.edit_text("⏳ Создаю копию на новом сервере... (1/3)")
        user_profile = await db.get_user_profile(old_container['user_id'])
        tariff = TARIFFS[old_container['tariff_id']]
        image = IMAGES[old_container['image_id']]

        new_container_name, new_app_port, login_url = await dm.create_container(
            user_id=old_container['user_id'], 
            username=user_profile.get('username'),
            server_id=new_server_id, 
            tariff=tariff, 
            image=image,
            forced_name=old_container['container_name']
        )
        if not all([new_container_name, new_app_port, login_url]):
            raise Exception("Не удалось создать контейнер на новом сервере.")

        old_server_exists = old_container['server_id'] in SERVERS
        is_old_server_active = bot_state.server_states.get(old_container['server_id'], True)

        if old_server_exists and is_old_server_active:
            await status_message.edit_text("⏳ Удаляю старый контейнер... (2/3)")
            try:
                await dm.delete_container(old_container['server_id'], old_container['container_name'])
            except Exception as e:
                logging.warning(f"Не удалось удалить старый контейнер {old_container['container_name']} с сервера {old_container['server_id']}. Ошибка: {e}. Пропускаем шаг.")
                await status_message.edit_text(f"⚠️ Не удалось подключиться к старому серверу для удаления. Пропускаем шаг... (2/3)")
        else:
            logging.warning(f"Старый сервер {old_container['server_id']} недоступен или отключен в админке. Пропускаем шаг удаления старого контейнера.")
            await status_message.edit_text("⏳ Старый сервер недоступен, пропускаем удаление... (2/3)")

        await status_message.edit_text("⏳ Обновляю информацию в БД... (3/3)")
        await db.update_container_server(container_id, new_server_id, new_app_port, new_container_name, login_url)

        target_user = await bot.get_chat(old_container['user_id'])
        old_server_name = SERVERS.get(old_container['server_id'], {}).get('name', 'N/A')
        new_server_name = SERVERS.get(new_server_id, {}).get('name', 'N/A')
        log_text = f"перенес контейнер '{new_container_name}' с сервера '{old_server_name}' на '{new_server_name}'"
        await log_action(bot, admin_user, log_text, target_user)

        await status_message.edit_text(f"✅ Перенос контейнера #{container_id} на сервер «{new_server_name}» успешно завершен!")

        try:
            await bot.send_message(
                old_container['user_id'],
                lex.get('admin_move_success_user_notification').format(container_name=new_container_name)
            )
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logging.warning(f"Не удалось уведомить пользователя {old_container['user_id']} о переносе контейнера: {e}")
            await bot.send_message(admin_id, f"<i>Не удалось уведомить пользователя {old_container['user_id']} о переносе.</i>")

    except Exception as e:
        error_text = f"❌ Ошибка при переносе контейнера #{container_id}! Детали в логах."
        logging.error(f"Админский перенос контейнера {container_id} на {new_server_id} провалился: {e}", exc_info=True)
        await status_message.edit_text(error_text)

        if new_container_name:
            logging.warning(f"Пытаюсь удалить 'осиротевший' контейнер {new_container_name} на {new_server_id}.")
            try:
                await dm.delete_container(new_server_id, new_container_name)
            except Exception as clean_e:
                critical_error_msg = f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось удалить {new_container_name}. Ошибка: {clean_e}"
                logging.critical(critical_error_msg)
                await bot.send_message(admin_id, critical_error_msg)

@router.callback_query(F.data.startswith("admin_change_server_start:"))
async def admin_change_server_start(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    container = await db.get_container_by_id(container_id)

    if not container:
        await callback.answer("❌ Контейнер не найден.", show_alert=True)
        return

    await state.set_state(AdminChangeServerState.choosing_server)
    await state.update_data(container_id=container_id)

    await safe_edit_caption(
        callback.message,
        caption=lex.get('admin_change_server_prompt', "Выберите новый сервер для переноса контейнера."), 
        reply_markup=get_change_server_keyboard(
            language_code, 
            container['server_id'], 
            container['tariff_id'],
            admin_mode=True
        )
    )
    await callback.answer()

@router.callback_query(AdminChangeServerState.choosing_server, F.data.startswith("admin_select_new_server:"))
async def admin_select_new_server(callback: types.CallbackQuery, state: FSMContext):
    new_server_id = callback.data.split(":")[1]
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    data = await state.get_data()
    container_id = data.get('container_id')
    new_server_name = SERVERS.get(new_server_id, {}).get('name', 'N/A')

    caption = lex.get('admin_confirm_server_change_prompt').format(server_name=new_server_name)

    await state.update_data(new_server_id=new_server_id)
    await state.set_state(AdminChangeServerState.confirming_change)

    await safe_edit_caption(
        callback.message,
        caption=caption,
        reply_markup=get_simple_confirmation_keyboard(language_code, "admin_confirm_server_change", "cancel_admin_action")
    )
    await callback.answer()

@router.callback_query(AdminChangeServerState.confirming_change, F.data == "admin_confirm_server_change")
async def admin_confirm_server_change(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await safe_edit_caption(
        callback.message,
        caption="✅ Задача на перенос контейнера запущена в фоновом режиме. Вы получите уведомление о прогрессе.",
    )
    await callback.answer("✅ Задача запущена!")

    data = await state.get_data()
    container_id = data.get('container_id')
    new_server_id = data.get('new_server_id')

    asyncio.create_task(_perform_container_move(
        bot=bot,
        admin_user=callback.from_user,
        container_id=container_id,
        new_server_id=new_server_id
    ))

    await state.clear()
