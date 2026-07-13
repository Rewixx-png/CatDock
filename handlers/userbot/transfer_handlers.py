import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from keyboards import get_transfer_confirmation_keyboard
from states.user_states import UserBotManageState
from lexicon import LEXICON
from ..common.menu_utils import show_management_menu
from utils import bot_state
from utils.action_logger import log_action

router = Router()

@router.callback_query(F.data.startswith("transfer_bot_start:"))
async def start_transfer(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    container = await db.get_container_by_id(container_id)
    if not container or container.get('tariff_id') == 'free':
        try:
            await callback.answer(lex.get('transfer_free_error', "❌ Эту услугу нельзя передать."), show_alert=True)
        except TelegramBadRequest:
            pass
        return

    await state.set_state(UserBotManageState.confirming_transfer)
    await state.update_data(container_id=container_id)

    try:
        await callback.message.edit_caption(
            caption=lex.get('transfer_confirm_text'),
            reply_markup=get_transfer_confirmation_keyboard(language_code, container_id)
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            logging.warning(f"Ошибка при редактировании сообщения (transfer): {e}")

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

@router.callback_query(UserBotManageState.confirming_transfer, F.data.startswith("confirm_transfer:"))
async def confirm_transfer(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    token = await db.create_transfer_token(container_id, user_id)

    if not token:
        try:
            await callback.answer("❌ Ошибка создания ссылки.", show_alert=True)
        except TelegramBadRequest:
            pass
        return

    bot_info = bot_state.bot_info_cache
    transfer_link = f"https://t.me/{bot_info.username}?start={token}"

    asyncio.create_task(
        log_action(bot, callback.from_user, f"создал ссылку для передачи контейнера #{container_id}")
    )

    try:
        await callback.answer("✅ Ссылка создана!", show_alert=True)
    except TelegramBadRequest:
        pass

    await callback.message.answer(
        lex.get('transfer_link_message') + f"\n\n<code>{transfer_link}</code>"
    )

    await show_management_menu(callback, container_id, state, bot)

@router.callback_query(F.data.startswith("cancel_transfer:"))
async def cancel_transfer(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await db.delete_token_for_container(container_id)

    asyncio.create_task(
        log_action(bot, callback.from_user, f"отменил передачу контейнера #{container_id}")
    )

    try:
        await callback.answer(lex.get('transfer_canceled'), show_alert=True)
    except TelegramBadRequest:
        pass

    await show_management_menu(callback, container_id, state, bot)
