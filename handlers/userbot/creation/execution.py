import logging
import asyncio
from functools import wraps
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext

import database as db
from config import TARIFFS, SERVERS, IMAGES, WEB_APP_URL
from states.user_states import UserBotCreateState
from roles import UserRole
from utils.action_logger import log_action
from utils.pricing import calculate_final_price, use_purchase_bonus
from keyboards import get_main_menu_keyboard
from .menu import start_creation_hub
from utils.worker_tasks import task_create_container

router = Router()
_creation_locks: dict[int, asyncio.Lock] = {}


def _serialize_creation(handler):
    @wraps(handler)
    async def wrapped(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        user_id = callback.from_user.id
        lock = _creation_locks.setdefault(user_id, asyncio.Lock())
        if lock.locked():
            await callback.answer("⏳ Заказ уже обрабатывается.", show_alert=True)
            return
        try:
            async with lock:
                return await handler(callback, state, bot)
        finally:
            _creation_locks.pop(user_id, None)
    return wrapped


async def _restore_purchase_bonus(
    user_id: int,
    promo_used: str | None,
    promo_code: str | None,
    discount_percent: int,
    discount_code: str | None,
):
    if promo_used == 'free_container':
        await db.set_user_free_container_promo(user_id, True, promo_code)
    elif promo_used == 'tariff_discount':
        await db.set_user_tariff_discount(user_id, discount_percent, discount_code)

@router.callback_query(F.data == "confirm_creation")
@_serialize_creation
async def confirm_creation_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer("🚀 Обработка...", show_alert=False)

    current_state = await state.get_state()
    if current_state != UserBotCreateState.confirming_creation:
        try: await callback.message.edit_text(text="⚠️ Сессия истекла.", reply_markup=None)
        except: pass
        await asyncio.sleep(1)
        await start_creation_hub(callback, state, bot)
        return

    user = callback.from_user
    user_id = user.id
    data = await state.get_data()
    tariff_id = data.get('tariff_id')
    image_id = data.get('image_id')

    if tariff_id not in TARIFFS or image_id not in IMAGES:
         await callback.answer("❌ Тариф или образ недоступен. Начните заново.", show_alert=True)
         await state.clear()
         await start_creation_hub(callback, state, bot)
         return

    server_id = data.get('manual_server_id') or data.get('server_id')
    if not server_id:
        import utils.docker as dm
        server_id = await dm.find_optimal_server(tariff_id, user_id)
        if not server_id:
            await callback.message.edit_text(text="❌ <b>Нет свободных мест</b>\n\nПопробуйте позже.")
            return

    if server_id not in SERVERS:
        await callback.answer("❌ Выбранный сервер недоступен.", show_alert=True)
        await state.clear()
        return

    if tariff_id == 'free':
        await log_action(bot, user, "подтвердил создание бесплатного UserBot'а")
        user_role = await db.get_user_role(user.id)
        is_admin = user_role and user_role >= UserRole.ADMIN

        if not is_admin and await db.check_if_user_used_free_tariff(user.id):
            await callback.message.edit_text(text="❌ Вы уже использовали пробный период.")
            return

        token = await db.create_verification_token(
            user.id, server_id, image_id, tariff_id, user.username,
            message_id=callback.message.message_id, chat_id=user.id
        )
        if not token:
            await callback.message.edit_text("❌ Не удалось создать ссылку верификации. Попробуйте позже.")
            return
        base_url = WEB_APP_URL.rstrip('/')
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder().row(InlineKeyboardButton(
            text="🛡 Перейти к верификации",
            url=f"{base_url}/verify-free-request/{token}",
        ))
        await state.clear()
        await callback.message.edit_text(text="⚠️ <b>Требуется верификация!</b>", reply_markup=builder.as_markup())
        return

    user_profile = await db.get_user_profile(user.id)
    if not user_profile:
        await callback.message.edit_text("❌ Профиль пользователя не найден. Выполните /start.")
        await state.clear()
        return
    final_price = await calculate_final_price(tariff_id, server_id, user_profile)

    _, promo_used = await use_purchase_bonus(user.id, tariff_id)
    promo_code = user_profile.get('free_container_promo_code') if promo_used == 'free_container' else None
    discount_percent = user_profile.get('active_discount_percent', 0) if promo_used == 'tariff_discount' else 0
    discount_code = user_profile.get('active_discount_code') if promo_used == 'tariff_discount' else None

    if final_price > 0 and not await db.try_deduct_user_balance(user.id, final_price):
        await _restore_purchase_bonus(
            user_id, promo_used, promo_code, discount_percent, discount_code
        )
        balance = await db.get_user_balance(user.id)
        await callback.message.edit_text(
            text=f"❌ <b>Недостаточно средств!</b>\n\nБаланс: {balance:.2f} RUB\nНужно: {final_price:.2f} RUB"
        )
        return

    try:
        await task_create_container.kiq(
            user_id=user_id,
            username=user.username or str(user_id),
            first_name=user.first_name,
            server_id=server_id,
            tariff_id=tariff_id,
            image_id=image_id,
            cost=final_price,
            days=30,
            promo_used=promo_used,
            promo_code=promo_code,
            discount_percent=discount_percent,
            discount_code=discount_code,
        )
    except Exception as e:
        logging.error("Не удалось поставить создание контейнера в очередь: %s", e, exc_info=True)
        if final_price > 0:
            await db.update_user_balance(user_id, final_price)
        await _restore_purchase_bonus(
            user_id, promo_used, promo_code, discount_percent, discount_code
        )
        await callback.message.edit_text(
            "❌ Не удалось поставить задачу в очередь. Средства и бонус восстановлены. Попробуйте позже."
        )
        return

    await state.clear()
    language_code = await db.get_user_language(user_id) or 'ru'
    markup = await get_main_menu_keyboard(language_code, user_id)

    await callback.message.edit_text(
        text=f"⏳ <b>Задача в очереди!</b>\n\n"
                f"Мы приняли ваш заказ. Бот создается на сервере <b>{SERVERS[server_id]['name']}</b>.\n"
                f"Это займет от 10 до 60 секунд. Вы получите уведомление по завершении.",
        reply_markup=markup
    )
