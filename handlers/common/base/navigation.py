from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest

import database as db
from keyboards import get_misc_menu_keyboard
from ..menu_utils import set_loading_state

router = Router()

@router.callback_query(F.data == "none")
async def handle_none_callback(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "misc_menu")
async def show_misc_menu(callback: types.CallbackQuery):
    await callback.answer()
    await set_loading_state(callback, "Меню") 

    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    markup = await get_misc_menu_keyboard(language_code, user_id)

    try:
        await callback.message.edit_text(
            text="🗂️ Здесь собраны дополнительные функции и полезные ссылки.",
            reply_markup=markup
        )
    except TelegramBadRequest:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(
            text="🗂️ Здесь собраны дополнительные функции и полезные ссылки.",
            reply_markup=markup
        )
