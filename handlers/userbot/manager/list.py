import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from keyboards import get_my_userbots_keyboard
from lexicon import LEXICON
from handlers.common.menu_utils import set_loading_state


router = Router()

async def send_userbots_menu(callback: types.CallbackQuery, state: FSMContext, send_new: bool = False):
    await state.clear()
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]
    containers = await db.get_user_containers(user_id)
    text = lex.get('my_userbots_title', 'my_userbots_title') + "\n\n" + (lex.get('my_userbots_no_bots', 'my_userbots_no_bots') if not containers else lex.get('my_userbots_select_bot', 'my_userbots_select_bot'))

    markup = await get_my_userbots_keyboard(containers, language_code)

    if send_new:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(text, reply_markup=markup)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logging.warning(f"Не удалось отредактировать меню my_userbots: {e}. Отправляем новое сообщение.")
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                pass
            await callback.message.answer(text, reply_markup=markup)

@router.callback_query(F.data == "my_userbots")
async def my_userbots_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await set_loading_state(callback, "Мои UserBot")
    await send_userbots_menu(callback, state)
