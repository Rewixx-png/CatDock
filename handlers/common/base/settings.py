from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from lexicon import LEXICON
from utils.action_logger import log_action
from states.user_states import SupportState
from keyboards import get_cancel_keyboard, get_language_selection_keyboard 

from .main_flow import send_main_menu

router = Router()

@router.callback_query(F.data == "change_lang")
async def change_lang_menu(callback: types.CallbackQuery):
    text = "🇷🇺 Выберите язык:\n🇺🇦 Оберіть мову:\n🇬🇧 Choose a language:"

    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_language_selection_keyboard()
        )
    except TelegramBadRequest:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_language_selection_keyboard()
            )
        except TelegramBadRequest:
            await callback.message.answer(
                text=text,
                reply_markup=get_language_selection_keyboard()
            )

    await callback.answer()

@router.callback_query(F.data.startswith("set_lang:"))
async def set_user_lang(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    lang_code = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await db.set_user_language(user_id, lang_code)
    await log_action(bot, callback.from_user, f"сменил язык на '{lang_code.upper()}'")

    data = await state.get_data()
    if data.get('next_action') == 'support':
        await state.clear()
        lex = LEXICON.get(lang_code, LEXICON['ru'])
        try:
            await callback.message.delete()
        except TelegramBadRequest: pass
        await callback.message.answer(lex.get('support_welcome_message', "Добро пожаловать в чат с поддержкой!"))
        await callback.message.answer(lex.get('support_prompt_question', "Опишите вашу проблему или вопрос одним сообщением:"), reply_markup=get_cancel_keyboard(lang_code))
        await state.set_state(SupportState.waiting_for_question)
        return

    await send_main_menu(callback, state) 
    await callback.answer()
