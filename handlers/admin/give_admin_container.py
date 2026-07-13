import logging
import html
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
from config import SERVERS, IMAGES, TARIFFS
from states.user_states import AdminGiveAdminContainerState
from keyboards.admin import (
    get_cancel_admin_action_keyboard,
    get_give_admin_server_keyboard,
    get_give_admin_image_keyboard,
    get_give_admin_confirmation_keyboard
)
from lexicon import LEXICON
from roles import UserRole
from utils.filters import IsAdmin
import utils.docker as dm
from utils.action_logger import log_action
from utils.ui_utils import safe_edit_caption

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.callback_query(F.data == "give_admin_container_start")
async def start_give_admin_container(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    await state.set_state(AdminGiveAdminContainerState.waiting_for_user_id)
    await safe_edit_caption(
        callback.message,
        caption=lex.get('give_admin_container_prompt_user'),
        reply_markup=get_cancel_admin_action_keyboard("admin_containers_menu", language_code)
    )
    await callback.answer()

@router.message(AdminGiveAdminContainerState.waiting_for_user_id)
async def process_user_id_for_admin_container(message: types.Message, state: FSMContext, bot: Bot):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    try:
        target_user_id = int(message.text)
        user_profile = await db.get_user_profile(target_user_id)
        if not user_profile:
            await message.reply(lex.get('give_admin_container_user_not_found'))
            return
    except (ValueError, TypeError):
        await message.reply("Введите корректный ID пользователя (только цифры).")
        return

    safe_name = html.escape(user_profile.get('first_name', 'N/A'))
    
    await state.update_data(
        target_user_id=target_user_id,
        target_user_name=safe_name,
        target_user_username=user_profile.get('username')
    )
    await state.set_state(AdminGiveAdminContainerState.choosing_server)

    try:
        await bot.delete_message(message.chat.id, message.message_id - 1)
        await message.delete()
    except TelegramBadRequest:
        pass

    await message.answer(
        lex.get('give_admin_container_prompt_server'),
        reply_markup=get_give_admin_server_keyboard(language_code)
    )

@router.callback_query(AdminGiveAdminContainerState.choosing_server, F.data.startswith("give_admin_server:"))
async def process_server_for_admin_container(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]
    await state.update_data(server_id=server_id)
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    await state.set_state(AdminGiveAdminContainerState.choosing_image)
    await callback.message.edit_text(
        lex.get('give_admin_container_prompt_image'),
        reply_markup=get_give_admin_image_keyboard(language_code)
    )

@router.callback_query(AdminGiveAdminContainerState.choosing_image, F.data.startswith("give_admin_image:"))
async def process_image_for_admin_container(callback: types.CallbackQuery, state: FSMContext):
    image_id = callback.data.split(":")[1]
    await state.update_data(image_id=image_id)
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    data = await state.get_data()
    
    confirmation_text = lex.get('give_admin_container_confirm_text').format(
        user_name=data['target_user_name'],
        user_id=data['target_user_id'],
        server_name=SERVERS[data['server_id']]['name'],
        image_name=IMAGES[image_id]['name']
    )

    await state.set_state(AdminGiveAdminContainerState.confirming_give)
    await callback.message.edit_text(confirmation_text, reply_markup=get_give_admin_confirmation_keyboard(language_code))

@router.callback_query(AdminGiveAdminContainerState.confirming_give, F.data == "confirm_give_admin_container")
async def confirm_and_give_admin_container(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text("⏳ Создаю контейнер...")
    data = await state.get_data()

    try:
        container_name, app_port, login_url = await dm.create_container(
            user_id=data['target_user_id'],
            username=data.get('target_user_username'),
            server_id=data['server_id'],
            tariff=TARIFFS['basic'],
            image=IMAGES[data['image_id']]
        )
        if not all([container_name, app_port, login_url]):
            raise Exception("Docker manager не смог создать контейнер.")

        await db.add_user_container(
            user_id=data['target_user_id'],
            server_id=data['server_id'],
            container_name=container_name,
            image_id=data['image_id'],
            tariff_id='admin',
            external_port=app_port,
            login_url=login_url
        )

        language_code = await db.get_user_language(callback.from_user.id) or 'ru'
        lex = LEXICON[language_code]
        await callback.message.edit_text(
            lex.get('admin_container_issued_success').format(
                container_name=container_name,
                user_id=data['target_user_id']
            )
        )

        target_user = await bot.get_chat(data['target_user_id'])
        await log_action(bot, callback.from_user, f"выдал админ-контейнер '{container_name}'", target_user)

        try:
            await bot.send_message(
                data['target_user_id'],
                lex.get('admin_container_issued_notification').format(container_name=container_name)
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            await callback.message.answer("<i>Не удалось уведомить пользователя в ЛС.</i>")

    except Exception as e:
        logging.error(f"Не удалось выдать админ-контейнер: {e}", exc_info=True)
        
        safe_error = html.escape(str(e))
        await callback.message.edit_text(f"❌ Произошла ошибка: {safe_error}")
    finally:
        await state.clear()
