from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import logging

import database as db
from config import MIN_WITHDRAWAL_AMOUNT
from keyboards import get_cancel_keyboard
from states.user_states import WithdrawalState
from utils.action_logger import log_action

router = Router()

@router.callback_query(F.data == "withdraw")
async def start_withdrawal(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    ref_balance = await db.get_user_ref_balance(user_id)

    if ref_balance < MIN_WITHDRAWAL_AMOUNT:
        await callback.answer(
            f"❌ Минимальная сумма для перевода: {MIN_WITHDRAWAL_AMOUNT:.2f} RUB.\n"
            f"У вас на реферальном балансе: {ref_balance:.2f} RUB.",
            show_alert=True
        )
        return

    language_code = await db.get_user_language(user_id) or 'ru'
    msg = await callback.message.edit_caption(
        caption=f"💸 <b>Перевод средств</b>\n\n"
                f"Вы можете перевести средства с <b>реферального</b> баланса на <b>основной</b>.\n"
                f"Доступно: <b>{ref_balance:.2f} RUB</b>\n\n"
                f"Введите сумму для перевода (минимум {MIN_WITHDRAWAL_AMOUNT:.2f} RUB):",
        reply_markup=get_cancel_keyboard(language_code)
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await state.set_state(WithdrawalState.waiting_for_amount)
    await callback.answer()

@router.message(WithdrawalState.waiting_for_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext, bot: Bot):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    try:
        amount = float(message.text.replace(',', '.'))
    except (ValueError, TypeError):
        await message.answer("❌ Пожалуйста, введите корректное число.", reply_markup=get_cancel_keyboard(language_code))
        return

    user_id = message.from_user.id
    ref_balance = await db.get_user_ref_balance(user_id)

    if amount < MIN_WITHDRAWAL_AMOUNT:
        await message.answer(f"❌ Минимальная сумма: {MIN_WITHDRAWAL_AMOUNT:.2f} RUB.", reply_markup=get_cancel_keyboard(language_code))
        return
    if amount > ref_balance:
        await message.answer(f"❌ Недостаточно средств на реферальном балансе ({ref_balance:.2f} RUB).", reply_markup=get_cancel_keyboard(language_code))
        return

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    try:
        await message.delete()
        if prompt_message_id:
            await bot.delete_message(chat_id=user_id, message_id=prompt_message_id)
    except TelegramBadRequest:
        pass

    try:
        await db.debit_referral_balance(user_id, amount)
        await db.update_user_balance(user_id, amount)

        new_main_balance = await db.get_user_balance(user_id)

        await log_action(bot, message.from_user, f"перевел {amount:.2f} RUB с реферального на основной счет")

        await message.answer(
            f"✅ <b>Успешно!</b>\n\n"
            f"Средства в размере <b>{amount:.2f} RUB</b> переведены на основной баланс.\n"
            f"Текущий основной баланс: <b>{new_main_balance:.2f} RUB</b>"
        )

        from handlers.profile.profile_handlers import show_profile_menu

    except Exception as e:
        logging.error(f"Ошибка при переводе средств (Withdrawal): {e}")
        await message.answer("❌ Произошла ошибка при выполнении перевода. Свяжитесь с поддержкой.")

    await state.clear()
