import logging
import html
from aiogram import F, Router, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timedelta

import database as db
import utils.docker as dm
from config import TARIFFS, SERVERS, IMAGES
from states.user_states import AdminChatGiveContainerState
from utils.filters import IsAdmin
from roles import UserRole
from lexicon import LEXICON
from keyboards.admin import (
    get_chat_give_tariff_keyboard,
    get_chat_give_server_keyboard,
    get_chat_give_image_keyboard
)
from keyboards import get_cancel_keyboard

from handlers.common.menu_utils import format_seconds_to_dhms

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.message(
    F.text.lower().regexp(r"^[/!](get|give)[\s_]+(cont|host|userbot)"),
    F.reply_to_message
)
async def cmd_get_container_start(message: types.Message, state: FSMContext):
    if not message.reply_to_message.from_user or message.reply_to_message.from_user.is_bot:
        await message.reply("Не могу определить пользователя из реплая или это бот.")
        return

    target_user = message.reply_to_message.from_user
    admin = message.from_user
    language_code = await db.get_user_language(admin.id) or 'ru'

    await state.set_state(AdminChatGiveContainerState.choosing_tariff)
    await state.update_data(
        target_user_id=target_user.id,
        target_user_name=target_user.full_name,
        target_user_username=target_user.username,
        admin_id=admin.id
    )

    safe_name = html.escape(target_user.full_name)

    sent_message = await message.answer(
        f"Выдача контейнера для <b>{safe_name}</b>.\n\n<b>Шаг 1:</b> Выберите тариф.",
        reply_markup=get_chat_give_tariff_keyboard(language_code)
    )
    await state.update_data(prompt_message_id=sent_message.message_id)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

@router.message(F.text.lower().regexp(r"^[/!](get|give)[\s_]+(cont|host|userbot)"))
async def cmd_get_container_no_reply(message: types.Message):
    await message.reply("<b>Ошибка.</b> Используйте эту команду в ответ на сообщение пользователя, которому хотите выдать контейнер.")

@router.callback_query(AdminChatGiveContainerState.choosing_tariff, F.data.startswith("chat_give_tariff:"))
async def process_tariff_choice(callback: types.CallbackQuery, state: FSMContext):
    tariff_id = callback.data.split(":")[1]
    await state.update_data(tariff_id=tariff_id)

    await callback.message.edit_text("<b>Шаг 2:</b> Введите срок жизни контейнера в днях (например, `30`).")
    await state.set_state(AdminChatGiveContainerState.waiting_for_days)
    await callback.answer()

@router.message(AdminChatGiveContainerState.waiting_for_days)
async def process_days_input(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        if not (1 <= days <= 3650): raise ValueError
    except (ValueError, TypeError):
        await message.reply("Неверный формат. Введите число от 1 до 3650.")
        return

    await state.update_data(days=days)

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    language_code = await db.get_user_language(message.from_user.id) or 'ru'

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            text="<b>Шаг 3:</b> Выберите сервер для размещения.",
            reply_markup=get_chat_give_server_keyboard(language_code)
        )
        await state.set_state(AdminChatGiveContainerState.choosing_server)
    except TelegramBadRequest as e:
        logging.error(f"Ошибка редактирования сообщения: {e}")
    finally:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

@router.callback_query(AdminChatGiveContainerState.choosing_server, F.data.startswith("chat_give_server:"))
async def process_server_choice(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]
    await state.update_data(server_id=server_id)

    language_code = await db.get_user_language(callback.from_user.id) or 'ru'

    await callback.message.edit_text(
        "<b>Шаг 4:</b> Выберите образ контейнера.",
        reply_markup=get_chat_give_image_keyboard(language_code)
    )
    await state.set_state(AdminChatGiveContainerState.choosing_image)
    await callback.answer()

@router.callback_query(AdminChatGiveContainerState.choosing_image, F.data.startswith("chat_give_image:"))
async def process_image_choice(callback: types.CallbackQuery, state: FSMContext):
    image_id = callback.data.split(":")[1]
    await state.update_data(image_id=image_id)

    await callback.message.edit_text("<b>Шаг 5:</b> Введите причину выдачи (например, 'подарок').")
    await state.set_state(AdminChatGiveContainerState.waiting_for_reason)
    await callback.answer()

@router.message(AdminChatGiveContainerState.waiting_for_reason)
async def process_reason_and_create(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()

    if not data or 'target_user_id' not in data:
        return

    reason = message.text
    
    safe_reason = html.escape(reason)
    
    prompt_id = data.get('prompt_message_id')

    await state.clear()

    try:
        await message.delete()
        if prompt_id:
            await bot.edit_message_text("⏳ <b>Финальный шаг:</b> Создаю контейнер, это может занять до минуты...", chat_id=message.chat.id, message_id=prompt_id, reply_markup=None)
    except TelegramBadRequest:
        await message.answer("⏳ <b>Финальный шаг:</b> Создаю контейнер, это может занять до минуты...")

    target_user_id = data['target_user_id']
    target_user_name = data['target_user_name']
    target_user_username = data.get('target_user_username')

    safe_target_name = html.escape(target_user_name)
    
    tariff_id = data['tariff_id']
    days = data['days']
    server_id = data['server_id']
    image_id = data['image_id']

    target_user_profile = await db.get_user_profile(target_user_id)
    if not target_user_profile:
        await db.add_user(target_user_id, target_user_username, target_user_name)
        target_user_profile = await db.get_user_profile(target_user_id) 

    try:
        container_name, port, login_url = await dm.create_container(
            user_id=target_user_id,
            username=target_user_profile.get('username'),
            server_id=server_id,
            tariff=TARIFFS[tariff_id],
            image=IMAGES[image_id]
        )

        if not all([container_name, port, login_url]):
            raise Exception("Ошибка на стороне Docker Manager, контейнер не создан.")

        await db.add_user_container(
            user_id=target_user_id, server_id=server_id, container_name=container_name,
            image_id=image_id, tariff_id=tariff_id, external_port=port, login_url=login_url
        )

        all_containers = await db.get_user_containers(target_user_id)
        new_container = next((c for c in all_containers if c['container_name'] == container_name), None)

        safe_admin_name = html.escape(message.from_user.full_name)

        if new_container:
            await db.admin_set_container_time(new_container['id'], days)

            try:
                end_time = datetime.now() + timedelta(days=days)
                
                log_text_topic = (
                    f"👤 <b>[ПОЛЬЗОВАТЕЛЬ: {safe_target_name} (<code>{target_user_id}</code>)]</b>\n"
                    f"Получил контейнер:\n\n"
                    f"<b>От администратора:</b> {safe_admin_name} (<code>{message.from_user.id}</code>)\n"
                    f"<b>Причина выдачи:</b> {safe_reason}\n\n"
                    f"<b>Дата получения:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"<b>Образ контейнера:</b> {IMAGES[image_id]['name']}\n"
                    f"<b>ID контейнера:</b> <code>{new_container['id']}</code>\n"
                    f"<b>Время окончания аренды:</b> {end_time.strftime('%Y-%m-%d %H:%M:%S')} ({days} д.)\n"
                    f"<b>Сервер контейнера:</b> {SERVERS[server_id]['name']}\n"
                    f"<b>Тариф контейнера:</b> {TARIFFS[tariff_id]['name']}"
                )
                logging.info("Topic log removed")
            except Exception as e:
                logging.error(f"Ошибка при логировании выдачи контейнера через чат в топик: {e}")
        else:
            raise Exception("Не удалось найти свежесозданный контейнер в БД для установки времени.")

        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_id,
                text=f"✅ <b>Успех!</b>\n\nКонтейнер <code>{container_name}</code> выдан пользователю <b>{safe_target_name}</b> на <b>{days} дней</b>."
            )
        except TelegramBadRequest:
            await message.answer(f"✅ <b>Успех!</b>\n\nКонтейнер <code>{container_name}</code> выдан.")

        await bot.send_message(
            target_user_id,
            f"🎉 Администратор <b>{safe_admin_name}</b> выдал вам новый UserBot!\n\n"
            f"<b>Имя:</b> <code>{container_name}</code>\n"
            f"<b>Срок:</b> {days} дней.\n\n"
            f"Вы можете найти его в разделе 'Мои UserBot'."
        )

    except Exception as e:
        logging.error(f"Ошибка при выдаче контейнера через чат: {e}", exc_info=True)
        try:
            safe_error = html.escape(str(e))
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_id,
                text=f"❌ <b>Критическая ошибка!</b>\n\nНе удалось создать контейнер. Детали в логах.\n<code>{safe_error}</code>"
            )
        except TelegramBadRequest:
            pass
