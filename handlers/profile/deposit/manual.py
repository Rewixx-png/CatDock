import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.markdown import hlink

import database as db
from config import ADMIN_ID, DEV_ID
from keyboards import get_main_menu_keyboard, get_cancel_keyboard
from keyboards.admin.common import get_admin_deposit_actions_keyboard
from states.user_states import DepositState
from lexicon import LEXICON
from utils.action_logger import log_action

router = Router()

@router.callback_query(F.data == "card_payment_confirmed", DepositState.waiting_for_card_payment)
async def card_payment_confirmed(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount")
    card_bank = data.get('card_info', {}).get('bank', 'N/A')
    payment_method = f"Карта ({card_bank})"
    user = callback.from_user

    asyncio.create_task(
        log_action(bot, user, f"создал заявку на пополнение на {amount} RUB через '{payment_method}'")
    )

    details = {'bank_name': 'Unknown (Bot)', 'method_details': card_bank}
    request_id = await db.create_payment_request(user.id, float(amount), 'card', details)
    if request_id is None:
        await callback.message.edit_text("❌ Не удалось создать заявку. Попробуйте позже.")
        await state.clear()
        return

    user_link = hlink(user.full_name, f"tg://user?id={user.id}")
    username = f"@{user.username}" if user.username else "Без юзернейма"

    admin_text = (
        f"💸 <b>ЗАЯВКА НА ПОПОЛНЕНИЕ #{request_id}</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 <b>От:</b> {user_link} ({username})\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💳 <b>Способ:</b> {card_bank}\n"
        f"💰 <b>Сумма:</b> <code>{amount} RUB</code>"
    )

    target_admin_id = ADMIN_ID
    if user.id == DEV_ID:
        target_admin_id = user.id

    keyboard = get_admin_deposit_actions_keyboard(request_id, user.id, float(amount))

    try:
        await bot.send_message(target_admin_id, admin_text, reply_markup=keyboard, disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление админу: {e}")

    await callback.message.edit_text("✅ Ваша заявка принята! Ожидайте зачисления средств.")
    await state.clear()

@router.callback_query(F.data == "payment_confirmed", DepositState.waiting_for_bank_name)
async def sbp_payment_confirmed(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    msg = await callback.message.edit_text(
        LEXICON[language_code]['enter_bank_name'],
        reply_markup=get_cancel_keyboard(language_code)
    )
    await state.set_state(DepositState.waiting_for_bank_name)
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(DepositState.waiting_for_bank_name)
async def process_bank_name(message: types.Message, state: FSMContext, bot: Bot):
    user = message.from_user
    language_code = await db.get_user_language(user.id) or 'ru'
    if not message.text:
        await message.answer("Пожалуйста, введите название банка.", reply_markup=get_cancel_keyboard(language_code))
        return

    bank_name = message.text
    data = await state.get_data()
    amount = data.get("amount")
    prompt_message_id = data.get("prompt_message_id")

    try:
        await message.delete()
        if prompt_message_id: await bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
    except TelegramBadRequest: pass

    details = {'bank_name': bank_name}
    request_id = await db.create_payment_request(user.id, float(amount), 'sbp', details)
    if request_id is None:
        await message.answer("❌ Не удалось создать заявку. Попробуйте позже.")
        await state.clear()
        return

    asyncio.create_task(
        log_action(bot, user, f"создал заявку на пополнение на {amount} RUB через СБП (банк: {bank_name})")
    )

    user_link = hlink(user.full_name, f"tg://user?id={user.id}")
    username = f"@{user.username}" if user.username else "Без юзернейма"

    admin_text = (
        f"🥝 <b>ЗАЯВКА НА ПОПОЛНЕНИЕ (СБП) #{request_id}</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 <b>От:</b> {user_link} ({username})\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"🏦 <b>Банк отправителя:</b> {bank_name}\n"
        f"💰 <b>Сумма:</b> <code>{amount} RUB</code>"
    )

    target_admin_id = ADMIN_ID
    if user.id == DEV_ID:
        target_admin_id = user.id

    keyboard = get_admin_deposit_actions_keyboard(request_id, user.id, float(amount))

    await bot.send_message(target_admin_id, admin_text, reply_markup=keyboard, disable_web_page_preview=True)
    await message.answer(LEXICON[language_code]['deposit_request_accepted'], reply_markup=await get_main_menu_keyboard(language_code, user.id))
    await state.clear()
