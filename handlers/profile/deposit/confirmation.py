import time
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice

import database as db
from config import PAYMENT_PHONE, STAR_TO_RUB_RATE, CARD_PAYMENT_DETAILS
from states.user_states import DepositState
from lexicon import LEXICON
from keyboards import get_card_payment_confirmation_keyboard, get_country_selection_keyboard

router = Router()

@router.callback_query(DepositState.hub_selection, F.data == "deposit_hub:incomplete")
async def incomplete_deposit_selection(callback: types.CallbackQuery):
    await callback.answer("❌ Пожалуйста, выберите все необходимые опции.", show_alert=True)

@router.callback_query(DepositState.hub_selection, F.data == "deposit_hub:confirm")
async def show_final_deposit_confirmation(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    method_id = data.get('method_id')
    amount = data.get('amount')
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0

    allowed_methods = {'stars'}
    if PAYMENT_PHONE:
        allowed_methods.add('sbp')
    if any(CARD_PAYMENT_DETAILS.values()):
        allowed_methods.add('cards')

    if method_id not in allowed_methods or amount <= 0:
        await callback.answer("❌ Ошибка данных. Попробуйте заново.", show_alert=True)
        await state.clear()
        return

    await callback.message.delete()

    if method_id == 'sbp':
        await state.set_state(DepositState.waiting_for_bank_name)
        payment_instructions = lex.get('sbp_payment_instruction', 'sbp_payment_instruction').format(amount=amount, phone_number=PAYMENT_PHONE, paid_button_text=lex.get('i_paid_button', 'i_paid_button'))
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text=lex.get('i_paid_button', 'i_paid_button'), callback_data="payment_confirmed"))
        builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="cancel_payment"))
        await callback.message.answer(payment_instructions, reply_markup=builder.as_markup())

    elif method_id == 'cards':
        card_info = data.get('card_info')

        if not card_info:
            await state.set_state(DepositState.choosing_country)
            await callback.message.answer(
                lex.get('choose_country_prompt', 'Выберите страну карты:'),
                reply_markup=get_country_selection_keyboard(language_code),
            )
            return

        payment_instructions = lex.get('card_payment_instruction', 'card_payment_instruction').format(
            amount=amount,
            bank_name=card_info['bank'],
            card_number=card_info['number'],
            paid_button_text=lex.get('i_paid_button', 'i_paid_button')
        )
        await callback.message.answer(payment_instructions, reply_markup=get_card_payment_confirmation_keyboard(language_code))
        await state.set_state(DepositState.waiting_for_card_payment)

    elif method_id == 'stars':
        star_amount = data.get('star_amount')
        if not star_amount:
             await callback.answer("Ошибка суммы звезд.", show_alert=True)
             return

        await bot.send_invoice(
            chat_id=user_id,
            title=lex.get('star_invoice_title'),
            description=lex.get('star_invoice_description').format(star_amount=star_amount, rub_equivalent=amount),
            payload=f"star-payment-{user_id}-{int(time.time())}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{star_amount} Telegram Stars", amount=star_amount)]
        )
        await state.clear()

    await callback.answer()


@router.pre_checkout_query()
async def approve_stars_pre_checkout(query: types.PreCheckoutQuery):
    if query.currency != 'XTR' or not query.invoice_payload.startswith('star-payment-'):
        await query.answer(ok=False, error_message="Некорректный счёт CatDock.")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_stars_payment(message: types.Message):
    payment = message.successful_payment
    if payment.currency != 'XTR' or not payment.invoice_payload.startswith('star-payment-'):
        return

    star_amount = payment.total_amount
    rub_amount = star_amount * STAR_TO_RUB_RATE
    credited = await db.credit_star_payment(
        charge_id=payment.telegram_payment_charge_id,
        user_id=message.from_user.id,
        star_amount=star_amount,
        rub_amount=rub_amount,
    )
    if not credited:
        await message.answer("ℹ️ Этот платёж уже был зачислен.")
        return

    await message.answer(
        f"✅ Оплата получена: <b>{star_amount} Stars</b>. "
        f"Баланс пополнен на <b>{rub_amount:.2f} RUB</b>."
    )
