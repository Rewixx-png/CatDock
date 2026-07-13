import logging
import asyncio
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import TARIFFS, SERVERS, IMAGES, WEB_APP_URL
from states.user_states import UserBotCreateState
from lexicon import LEXICON
from roles import UserRole
from utils.action_logger import log_action
from utils.pricing import calculate_final_price, use_purchase_bonus
from keyboards import get_main_menu_keyboard
from .menu import start_creation_hub
from utils.leveling import process_spending_xp 

from utils.worker_tasks import task_create_container

router = Router()

@router.callback_query(F.data == "confirm_creation")
async def confirm_creation_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer("🚀 Обработка...", show_alert=False)

    current_state = await state.get_state()
    if current_state != UserBotCreateState.confirming_creation:
        try: await callback.message.edit_caption(caption="⚠️ Сессия истекла.", reply_markup=None)
        except: pass
        await asyncio.sleep(1)
        await start_creation_hub(callback, state, bot)
        return

    user = callback.from_user
    user_id = user.id
    data = await state.get_data()
    tariff_id = data.get('tariff_id')

    if not tariff_id:
         await start_creation_hub(callback, state, bot)
         return

    server_id = data.get('manual_server_id') or data.get('server_id')
    if not server_id:
        import utils.docker as dm
        server_id = await dm.find_optimal_server(tariff_id, user_id)
        if not server_id:
            await callback.message.edit_caption(caption="❌ <b>Нет свободных мест</b>\n\nПопробуйте позже.")
            return

    if tariff_id == 'free':
        await log_action(bot, user, "подтвердил создание бесплатного UserBot'а")
        user_role = await db.get_user_role(user.id)
        is_admin = user_role and user_role >= UserRole.ADMIN

        if not is_admin and await db.check_if_user_used_free_tariff(user.id):
            await callback.message.edit_caption(caption="❌ Вы уже использовали пробный период.")
            return

        token = await db.create_verification_token(
            user.id, server_id, data['image_id'], tariff_id, user.username,
            message_id=callback.message.message_id, chat_id=user.id
        )
        base_url = WEB_APP_URL.rstrip('/')
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder().row(InlineKeyboardButton(text="🛡 Перейти к верификации", url=f"{base_url}/verify/{token}"))
        await callback.message.edit_caption(caption="⚠️ <b>Требуется верификация!</b>", reply_markup=builder.as_markup())
        return

    tariff = TARIFFS[tariff_id]
    user_profile = await db.get_user_profile(user.id)
    final_price = await calculate_final_price(tariff_id, server_id, user_profile)
    balance = await db.get_user_balance(user.id)

    if balance < final_price:
        await callback.message.edit_caption(caption=f"❌ <b>Недостаточно средств!</b>\n\nБаланс: {balance:.2f} RUB\nНужно: {final_price:.2f} RUB")
        return

    tariff_id_for_db, promo_used = await use_purchase_bonus(user.id, tariff_id)
    promo_code = user_profile.get('free_container_promo_code') if promo_used == 'free_container' else None

    if final_price > 0:
        await db.update_user_balance(user.id, -final_price)
        asyncio.create_task(process_spending_xp(bot, user_id, final_price))
        cashback = await db.add_cashback_to_balance(user.id, final_price)
        if cashback > 0:
             try: await bot.send_message(user_id, f"🎁 Кешбэк: <b>+{cashback:.2f} RUB</b>")
             except: pass

    await task_create_container.kiq(
        user_id=user_id,
        username=user.username or str(user_id),
        first_name=user.first_name,
        server_id=server_id,
        tariff_id=tariff_id,
        image_id=data['image_id'],
        cost=final_price,
        days=30, 
        promo_used=promo_used,
        promo_code=promo_code
    )

    language_code = await db.get_user_language(user_id) or 'ru'
    markup = await get_main_menu_keyboard(language_code, user_id)

    await callback.message.edit_caption(
        caption=f"⏳ <b>Задача в очереди!</b>\n\n"
                f"Мы приняли ваш заказ. Бот создается на сервере <b>{SERVERS[server_id]['name']}</b>.\n"
                f"Это займет от 10 до 60 секунд. Вы получите уведомление по завершении.",
        reply_markup=markup
    )

    await state.clear()
