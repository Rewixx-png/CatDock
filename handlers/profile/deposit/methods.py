from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import CARD_PAYMENT_DETAILS
from keyboards import get_payment_methods_keyboard, get_country_selection_keyboard, get_card_selection_keyboard, get_cancel_keyboard
from states.user_states import DepositState
from lexicon import LEXICON
from .hub import show_deposit_hub

router = Router()

@router.callback_query(DepositState.hub_selection, F.data.startswith("deposit_select:"))
async def select_deposit_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    data = await state.get_data()
    prompt_text = ""
    next_state = None

    if category == "method":
        await state.set_state(DepositState.choosing_method)
        await callback.message.edit_caption("<b>Шаг 1: Выбор способа оплаты</b>", reply_markup=get_payment_methods_keyboard(language_code))

    elif category == "amount":
        selected_method = data.get('method_id')

        if not selected_method:
            await callback.answer("Сначала выберите способ оплаты!", show_alert=True)
            return

        if selected_method == 'stars':
            prompt_text = lex.get('enter_star_amount_prompt')
            next_state = DepositState.waiting_for_star_amount
        elif selected_method == 'crypto':
            prompt_text = lex.get('enter_crypto_amount_prompt')
            next_state = DepositState.waiting_for_amount 
        else: 
            prompt_text = "Введите сумму для пополнения в рублях (например, 100):"
            next_state = DepositState.waiting_for_amount

        await callback.message.delete()
        msg = await callback.message.answer(prompt_text, reply_markup=get_cancel_keyboard(language_code))
        await state.set_state(next_state)
        await state.update_data(prompt_message_id=msg.message_id)

    elif category == "country_bank":
        await state.set_state(DepositState.choosing_country)
        await callback.message.edit_caption(lex['choose_country_prompt'], reply_markup=get_country_selection_keyboard(language_code))

    await callback.answer()

@router.callback_query(DepositState.choosing_method, F.data.startswith("deposit_set_method:"))
async def set_method_and_return_to_hub(callback: types.CallbackQuery, state: FSMContext):
    method_id = callback.data.split(":")[1]
    await state.update_data(method_id=method_id, amount=None, card_info=None, star_amount=None)
    await show_deposit_hub(callback, state)

@router.callback_query(DepositState.choosing_country, F.data.startswith("select_country:"))
async def select_country(callback: types.CallbackQuery, state: FSMContext):
    country_code = callback.data.split(":")[1]
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await state.set_state(DepositState.choosing_bank)
    await callback.message.edit_caption(
        caption=LEXICON[language_code]['choose_bank_prompt'],
        reply_markup=get_card_selection_keyboard(country_code, language_code)
    )

@router.callback_query(DepositState.choosing_bank, F.data.startswith("select_card:"))
async def select_card_and_return_to_hub(callback: types.CallbackQuery, state: FSMContext):
    _, country_code, card_idx_str = callback.data.split(":")
    card_idx = int(card_idx_str)
    card_info = CARD_PAYMENT_DETAILS[country_code][card_idx]
    await state.update_data(card_info=card_info)
    await show_deposit_hub(callback, state)

@router.callback_query(DepositState.choosing_bank, F.data == "deposit_select:country_bank")
async def back_to_country_selection(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]
    await state.set_state(DepositState.choosing_country)
    await callback.message.edit_caption(
        lex['choose_country_prompt'], 
        reply_markup=get_country_selection_keyboard(language_code)
    )
    await callback.answer()
