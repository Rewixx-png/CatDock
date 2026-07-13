import logging
import html
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from datetime import datetime, timedelta

import database as db
from config import SERVERS, TARIFFS, IMAGES
from keyboards.admin import get_give_confirmation_keyboard
from keyboards import get_server_selection_keyboard, get_tariff_selection_keyboard, get_image_selection_keyboard, get_cancel_keyboard
from states.user_states import AdminGiveContainerState
import utils.docker as dm
from utils.filters import IsAdmin
from lexicon import LEXICON
from roles import UserRole
from utils.action_logger import log_action
from handlers.common.menu_utils import format_seconds_to_dhms


router = Router()
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.callback_query(F.data.startswith("admin_give_container_start:"))
async def give_container_start(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await state.set_state(AdminGiveContainerState.choosing_server)
    await state.update_data(target_user_id=target_user_id)
    await callback.message.delete()
    await callback.message.answer(
        f"Выдача контейнера пользователю <code>{target_user_id}</code>.\n\n<b>Шаг 1:</b> Выберите сервер.",
        reply_markup=get_server_selection_keyboard(language_code, {})
    )

@router.callback_query(AdminGiveContainerState.choosing_server, F.data.startswith("select_server:"))
async def give_container_choose_server(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await state.update_data(server_id=server_id)
    await state.set_state(AdminGiveContainerState.choosing_tariff)

    markup = await get_tariff_selection_keyboard(server_id, callback.from_user.id, language_code)

    await callback.message.edit_text(
        "<b>Шаг 2:</b> Выберите тариф.",
        reply_markup=markup
    )

@router.callback_query(AdminGiveContainerState.choosing_tariff, F.data.startswith("select_tariff:"))
async def give_container_choose_tariff(callback: types.CallbackQuery, state: FSMContext):
    tariff_id = callback.data.split(":")[1]
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(AdminGiveContainerState.choosing_image)
    await callback.message.edit_text(
        "<b>Шаг 3:</b> Выберите образ.",
        reply_markup=get_image_selection_keyboard(language_code)
    )

@router.callback_query(AdminGiveContainerState.choosing_image, F.data.startswith("select_image:"))
async def give_container_choose_image(callback: types.CallbackQuery, state: FSMContext):
    image_id = callback.data.split(":")[1]
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await state.update_data(image_id=image_id)

    await state.set_state(AdminGiveContainerState.waiting_for_reason)
    await callback.message.delete()
    msg = await callback.message.answer(
        "<b>Шаг 4:</b> Введите причину выдачи (например, 'победа в конкурсе').",
        reply_markup=get_cancel_keyboard(language_code)
    )
    await state.update_data(prompt_message_id=msg.message_id)

@router.message(AdminGiveContainerState.waiting_for_reason)
async def give_container_process_reason(message: types.Message, state: FSMContext):
    reason = message.text
    
    safe_reason = html.escape(reason)
    
    language_code = await db.get_user_language(message.from_user.id) or 'ru'

    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    if prompt_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_id)
        except TelegramBadRequest: pass
    await message.delete()

    await state.update_data(reason=safe_reason)
    await state.set_state(AdminGiveContainerState.confirming_give)

    data = await state.get_data()
    text = (
        f"<b>Подтвердите выдачу:</b>\n\n"
        f"<b>Пользователь:</b> <code>{data['target_user_id']}</code>\n"
        f"<b>Сервер:</b> {SERVERS[data['server_id']]['name']}\n"
        f"<b>Тариф:</b> {TARIFFS[data['tariff_id']]['name']}\n"
        f"<b>Образ:</b> {IMAGES[data['image_id']]['name']}\n"
        f"<b>Причина:</b> {safe_reason}\n\n"
        "Средства списаны <b>не будут</b>."
    )
    await message.answer(text, reply_markup=get_give_confirmation_keyboard(language_code))

@router.callback_query(AdminGiveContainerState.confirming_give, F.data == "confirm_give_container")
async def give_container_confirm(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data['target_user_id']
    target_user_profile = await db.get_user_profile(target_user_id)

    await callback.message.edit_text("⏳ Создаем и выдаем контейнер...")

    container_name, port, login_url = await dm.create_container(
        user_id=target_user_id,
        username=target_user_profile.get('username'),
        server_id=data['server_id'],
        tariff=TARIFFS[data['tariff_id']],
        image=IMAGES[data['image_id']]
    )

    if container_name and port:
        await db.add_user_container(
            user_id=target_user_id, server_id=data['server_id'], container_name=container_name,
            image_id=data['image_id'], tariff_id=data['tariff_id'], external_port=port, login_url=login_url
        )

        target_user = await bot.get_chat(target_user_id)
        reason = data.get('reason', 'не указана')

        log_text_personal = (
            f"выдал контейнер '{container_name}'.\n"
            f"Сервер: {SERVERS[data['server_id']]['name']}, "
            f"Тариф: {TARIFFS[data['tariff_id']]['name']}, "
            f"Образ: {IMAGES[data['image_id']]['name']}\n"
            f"Причина: {reason}"
        )
        await log_action(bot, callback.from_user, log_text_personal, target_user)

        await callback.message.edit_text(f"✅ UserBot <code>{container_name}</code> выдан пользователю {target_user_id}.")

        try:
            new_container_list = await db.get_user_containers(target_user_id)
            new_container = next((c for c in new_container_list if c['container_name'] == container_name), None)

            if new_container:
                end_time = datetime.now() + timedelta(seconds=new_container['remaining_seconds'])

                safe_target_name = html.escape(target_user.full_name)
                safe_admin_name = html.escape(callback.from_user.full_name)
                
                log_text_topic = (
                    f"👤 <b>[ПОЛЬЗОВАТЕЛЬ: {safe_target_name} (<code>{target_user.id}</code>)]</b>\n"
                    f"Получил контейнер:\n\n"
                    f"<b>От администратора:</b> {safe_admin_name} (<code>{callback.from_user.id}</code>)\n"
                    f"<b>Причина выдачи:</b> {reason}\n\n"
                    f"<b>Дата получения:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"<b>Образ контейнера:</b> {IMAGES[data['image_id']]['name']}\n"
                    f"<b>ID контейнера:</b> <code>{new_container['id']}</code>\n"
                    f"<b>Время окончания аренды:</b> {end_time.strftime('%Y-%m-%d %H:%M:%S')} ({format_seconds_to_dhms(new_container['remaining_seconds'])})\n"
                    f"<b>Сервер контейнера:</b> {SERVERS[data['server_id']]['name']}\n"
                    f"<b>Тариф контейнера:</b> {TARIFFS[data['tariff_id']]['name']}"
                )
                logging.info("Topic log removed")

        except Exception as e:
            logging.error(f"Ошибка при логировании выдачи контейнера в топик: {e}")

        try:
            language_code = await db.get_user_language(target_user_id) or 'ru'
            lex = LEXICON[language_code]
            notification_text = lex.get('admin_gave_container_notification').format(
                container_name=container_name,
                server_name=SERVERS[data['server_id']]['name']
            )
            await bot.send_message(target_user_id, notification_text)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logging.warning(f"Не удалось отправить уведомление о выдаче контейнера пользователю {target_user_id}: {e}")

    else:
        await callback.message.edit_text("❌ Ошибка при создании UserBot'а на сервере.")

    await state.clear()
