from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import STAR_TO_RUB_RATE
from states.user_states import DepositState
from .hub import show_deposit_hub

router = Router()

@router.message(DepositState.waiting_for_amount)
async def process_rub_amount(message: types.Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text.replace(',', '.'))
        if not (10 <= amount <= 100000): raise ValueError
    except (ValueError, TypeError):
        await message.reply("❌ Введите корректную сумму (от 10 до 100 000).")
        return

    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    try:
        await message.delete()
        if prompt_id: await bot.delete_message(message.chat.id, prompt_id)
    except TelegramBadRequest: pass

    await state.update_data(amount=amount)
    await show_deposit_hub(message, state)

@router.message(DepositState.waiting_for_star_amount)
async def process_star_amount_and_return(message: types.Message, state: FSMContext, bot: Bot):
    try:
        star_amount = int(message.text)
        if star_amount <= 0: raise ValueError
    except (ValueError, TypeError):
        await message.reply("❌ Пожалуйста, введите корректное количество звёзд (целое положительное число).")
        return

    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    try:
        await message.delete()
        if prompt_id: await bot.delete_message(message.chat.id, prompt_id)
    except TelegramBadRequest: pass

    rub_equivalent = star_amount * STAR_TO_RUB_RATE
    await state.update_data(amount=rub_equivalent, star_amount=star_amount)

    await show_deposit_hub(message, state)
