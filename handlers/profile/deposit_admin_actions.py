from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import logging
import asyncio

import database as db
from utils.filters import IsAdmin
from states.user_states import AdminDeclineState
from roles import UserRole
from utils.action_logger import log_action 
from keyboards.admin import get_cancel_admin_action_keyboard

router = Router()

router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.callback_query(F.data.startswith("adm_dep_ap:"))
async def admin_approve_deposit_callback(callback: types.CallbackQuery, bot: Bot):
    
    try:
        request_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    req = await db.get_payment_request_by_id(request_id)
    if not req:
        await callback.answer("Заявка не найдена в БД.", show_alert=True)
        return

    if req['status'] != 'pending':
        await callback.answer(f"Заявка уже обработана (Статус: {req['status']})", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    user_id = req['user_id']
    amount = req['amount']

    user_profile = await db.get_user_profile(user_id)
    final_amount = amount
    notification_text = f"✅ Ваша заявка на пополнение одобрена!\nБаланс пополнен на <b>{amount:.2f} RUB</b>."

    if user_profile:
        bonus_percent = user_profile.get('active_deposit_bonus_percent', 0)
        if bonus_percent > 0:
            bonus_amount = amount * (bonus_percent / 100)
            final_amount += bonus_amount
            notification_text = (
                f"✅ Баланс пополнен на <b>{amount:.2f} RUB</b>.\n"
                f"🎉 Сработал бонус <b>+{bonus_percent}%</b>! Зачислено: <b>{final_amount:.2f} RUB</b>."
            )
            await db.set_user_deposit_bonus(user_id, 0, None)

    await db.update_user_balance(user_id, final_amount)
    await db.update_payment_request_status(request_id, 'approved', admin_id=callback.from_user.id)

    referrer_id = await db.get_referrer_id(user_id)
    if referrer_id:
        await db.add_referral_reward(referrer_id, amount)

    target_user = await bot.get_chat(user_id)
    await log_action(bot, callback.from_user, f"одобрил (Bot) заявку #{request_id} на {amount:.2f} RUB", target_user)

    try:
        await bot.send_message(user_id, notification_text)
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n✅ <b>ОДОБРЕНО</b>\nАдмин: {callback.from_user.full_name}",
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    await callback.answer("Успешно одобрено!")

@router.callback_query(F.data.startswith("adm_dep_dec_start:"))
async def admin_decline_deposit_start(callback: types.CallbackQuery, state: FSMContext):
    
    try:
        request_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    req = await db.get_payment_request_by_id(request_id)
    if not req:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    
    if req['status'] != 'pending':
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return

    await state.set_state(AdminDeclineState.waiting_for_reason)
    await state.update_data(
        request_id=request_id,
        message_id=callback.message.message_id,
        original_text=callback.message.html_text
    )

    await callback.message.reply(
        f"📝 Введите причину отказа для заявки #{request_id}:",
        reply_markup=get_cancel_admin_action_keyboard("cancel_decline")
    )
    await callback.answer()

@router.message(AdminDeclineState.waiting_for_reason)
async def admin_decline_deposit_reason(message: types.Message, state: FSMContext, bot: Bot):
    reason = message.text
    data = await state.get_data()
    request_id = data.get('request_id')
    original_message_id = data.get('message_id')
    original_text = data.get('original_text')

    try:
        await message.delete()
        
    except: pass

    req = await db.get_payment_request_by_id(request_id)
    if not req or req['status'] != 'pending':
        await message.answer("Заявка уже не актуальна.")
        await state.clear()
        return

    await db.update_payment_request_status(request_id, 'declined', admin_id=message.from_user.id, reason=reason)

    target_user = await bot.get_chat(req['user_id'])
    await log_action(bot, message.from_user, f"отклонил (Bot) заявку #{request_id}. Причина: {reason}", target_user)

    try:
        await bot.send_message(
            req['user_id'],
            f"❌ Ваша заявка на пополнение #{request_id} отклонена.\n\n<b>Причина:</b> {reason}"
        )
    except Exception: pass

    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=original_message_id,
            text=f"{original_text}\n\n❌ <b>ОТКЛОНЕНО</b>\nПричина: {reason}\nАдмин: {message.from_user.full_name}",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось обновить сообщение заявки: {e}")

    await message.answer(f"Заявка #{request_id} отклонена.")
    await state.clear()

@router.callback_query(F.data == "cancel_decline", AdminDeclineState.waiting_for_reason)
async def cancel_decline(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Отмена")
