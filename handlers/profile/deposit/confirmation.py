import time
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice

import database as db
from config import PAYMENT_PHONE
from states.user_states import DepositState
from lexicon import LEXICON
from keyboards import get_card_payment_confirmation_keyboard, get_card_selection_keyboard


async def create_crypto_invoice(amount, user_id):
    return None

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

    if not method_id or not amount:
        await callback.answer("❌ Ошибка данных. Попробуйте заново.", show_alert=True)
        return

    await callback.message.delete()

    if method_id == 'sbp':
        await state.set_state(DepositState.waiting_for_bank_name)
        payment_instructions = lex['sbp_payment_instruction'].format(amount=amount, phone_number=PAYMENT_PHONE, paid_button_text=lex['i_paid_button'])
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text=lex['i_paid_button'], callback_data="payment_confirmed"))
        builder.row(types.InlineKeyboardButton(text=lex['cancel_button'], callback_data="cancel_payment"))
        await callback.message.answer(payment_instructions, reply_markup=builder.as_markup())

    elif method_id == 'cards':
        card_info = data.get('card_info')

        if not card_info:
            await state.set_state(DepositState.choosing_country)
            await callback.message.answer(
                "⚠️ Не выбран банк или карта. Пожалуйста, выберите метод оплаты заново.",
                reply_markup=get_card_selection_keyboard('ru', language_code) 
            )
            return

        payment_instructions = lex['card_payment_instruction'].format(
            amount=amount,
            bank_name=card_info['bank'],
            card_number=card_info['number'],
            paid_button_text=lex['i_paid_button']
        )
        await callback.message.answer(payment_instructions, reply_markup=get_card_payment_confirmation_keyboard(language_code))
        await state.set_state(DepositState.waiting_for_card_payment)

    elif method_id == 'crypto':
        status_msg = await callback.message.answer("⏳ Создаем счет...")
        invoice_data = await create_crypto_invoice(amount, user_id)
        if invoice_data and invoice_data.get('bot_invoice_url'):
            invoice_id = invoice_data['invoice_id']
            await state.set_state(DepositState.waiting_for_crypto_payment_confirmation)
            await state.update_data(invoice_id=invoice_id, rub_amount=amount)
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text=lex.get('go_to_payment_button'), url=invoice_data['bot_invoice_url']))
            builder.row(types.InlineKeyboardButton(text=lex.get('check_payment_button'), callback_data=f"check_crypto:{invoice_id}"))
            builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button'), callback_data="cancel_payment"))
            await status_msg.edit_text(lex.get('crypto_invoice_created'), reply_markup=builder.as_markup())
        else:
            await status_msg.edit_text(lex.get('crypto_api_error'))
            await state.clear()

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
