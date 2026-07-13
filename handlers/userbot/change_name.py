from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
import logging
import re

import database as db
import utils.docker as dm
from lexicon import LEXICON
from ..common.menu_utils import show_management_menu
from utils.action_logger import log_action
from states.user_states import ChangeNameState
from keyboards import get_cancel_keyboard

router = Router()

@router.callback_query(F.data.startswith("change_name_start:"))
async def change_name_start_handler(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    container = await db.get_container_by_id(container_id)
    if not container: return

    await state.set_state(ChangeNameState.waiting_for_name)
    await state.update_data(container_id=container_id)

    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        LEXICON[language_code]['change_name_prompt'], 
        reply_markup=get_cancel_keyboard(language_code)
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(ChangeNameState.waiting_for_name)
async def process_name_change(message: types.Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    new_name = message.text.strip()

    if not (4 <= len(new_name) <= 29):
        await message.answer(lex.get('change_name_error_length'))
        return

    if not re.match(r'^[a-zA-Z0-9_.-]+$', new_name):
        await message.answer(lex.get('change_name_error_chars'))
        return

    data = await state.get_data()
    container_id = data['container_id']

    try:
        await message.delete()
        prompt_id = data.get('prompt_message_id')
        if prompt_id:
            await bot.delete_message(user_id, prompt_id)
    except:
        pass

    container = await db.get_container_by_id(container_id)
    if not container:
        await message.answer("Контейнер не найден.")
        await state.clear()
        return

    status_msg = await message.answer("⏳ Применяем новое имя...")

    try:
        await dm.rename_container(container['server_id'], container['container_name'], new_name)

        await db.update_container_name(container_id, new_name)

        await log_action(bot, message.from_user, f"переименовал контейнер с '{container['container_name']}' на '{new_name}'")

        await status_msg.edit_text(lex.get('change_name_success'))

    except Exception as e:
        error_text = str(e)
        if "is already in use" in error_text or "Conflict" in error_text:
            await status_msg.edit_text(lex.get('change_name_error_taken'))
        else:
            logging.error(f"Ошибка переименования контейнера {container_id}: {e}", exc_info=True)
            await status_msg.edit_text(lex.get('change_name_error_generic'))

    await state.clear()

    import asyncio
    await asyncio.sleep(1.5)
    try:
        await status_msg.delete()
    except:
        pass

    fake_callback = message
    from ..common.menu_utils import show_management_menu
    menu_msg = await message.answer("Загрузка меню...")
    await show_management_menu(menu_msg, container_id, state, bot)
