from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from keyboards import get_deposit_hub_keyboard
from states.user_states import DepositState
from lexicon import LEXICON


router = Router()

async def show_deposit_hub(event: types.Message | types.CallbackQuery, state: FSMContext):
    user_id = event.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'

    await state.set_state(DepositState.hub_selection)
    selection_data = await state.get_data()

    markup = get_deposit_hub_keyboard(language_code, selection_data)
    caption = "<b>Выберите конфигурацию для пополнения</b>\n\nНажимайте на категории, чтобы выбрать способ и указать сумму."

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(caption, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(caption, reply_markup=markup)

@router.callback_query(F.data == "add_balance")
async def add_balance_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_deposit_hub(callback, state)

@router.callback_query(F.data == "deposit_hub:back")
async def back_to_deposit_hub(callback: types.CallbackQuery, state: FSMContext):
    await show_deposit_hub(callback, state)
