import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import get_delete_confirm_step1_keyboard, get_delete_confirm_step2_keyboard
from states.user_states import DeleteContainerState
from lexicon import LEXICON
from .list import send_userbots_menu
from utils.worker_tasks import task_delete_container

router = Router()

@router.callback_query(F.data.startswith("delete_bot_start:"))
async def delete_bot_start(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await state.set_state(DeleteContainerState.confirming_first_step)
    await state.update_data(container_id=container_id)

    await callback.message.edit_caption(
        caption=lex.get('delete_confirm_step1_text'),
        reply_markup=get_delete_confirm_step1_keyboard(language_code, container_id)
    )
    await callback.answer()

@router.callback_query(DeleteContainerState.confirming_first_step, F.data.startswith("delete_confirm_step2:"))
async def delete_bot_second_step(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await state.set_state(DeleteContainerState.confirming_second_step)

    await callback.message.edit_caption(
        caption=lex.get('delete_confirm_step2_text'),
        reply_markup=get_delete_confirm_step2_keyboard(language_code, container_id)
    )
    await callback.answer()

@router.callback_query(DeleteContainerState.confirming_second_step, F.data.startswith("delete_bot_final:"))
async def delete_bot_final(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    container_id = data.get('container_id')

    if not container_id:
        await callback.answer("❌ Ошибка.", show_alert=True)
        await send_userbots_menu(callback, state)
        return

    container = await db.get_container_by_id(container_id)
    if not container:
        await send_userbots_menu(callback, state, send_new=True)
        return

    await task_delete_container.kiq(
        chat_id=callback.from_user.id,
        user_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        container_id=container_id,
        server_id=container['server_id'],
        container_name=container['container_name']
    )

    await callback.message.edit_caption(caption="⏳ <b>Удаление запущено...</b>\nЭто займет пару секунд.")
    await state.clear()
