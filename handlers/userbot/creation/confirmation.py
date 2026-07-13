from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timedelta
import logging

import database as db
from config import TARIFFS, SERVERS, IMAGES
from keyboards import get_confirmation_keyboard
from states.user_states import UserBotCreateState
import utils.docker as dm
from lexicon import LEXICON
from utils.pricing import calculate_final_price
from .menu import start_creation_hub

router = Router()

@router.callback_query(F.data == "create_hub:confirm")
async def handle_expired_confirm(callback: types.CallbackQuery, state: FSMContext, bot):
    current_state = await state.get_state()

    if current_state is None:
        await callback.answer("⚠️ Время сессии истекло или бот был перезагружен.\nПожалуйста, начните создание заново.", show_alert=True)
        await start_creation_hub(callback, state, bot)
        return

    await show_final_confirmation(callback, state)

@router.callback_query(UserBotCreateState.hub_selection, F.data == "create_hub:confirm")
@router.callback_query(UserBotCreateState.choosing_server_manually, F.data == "create_hub:confirm")
async def show_final_confirmation(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer() 
    except Exception:
        pass

    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]
    data = await state.get_data()

    tariff_id = data.get('tariff_id')
    image_id = data.get('image_id')
    if tariff_id not in TARIFFS or image_id not in IMAGES:
        await callback.answer("Ошибка данных. Начните заново.", show_alert=True)
        return

    manual_server_id = data.get('manual_server_id')
    server_id = manual_server_id
    server_choice_text = "(ручной выбор)"

    if not server_id:
        server_id = await dm.find_optimal_server(tariff_id, user_id)
        server_choice_text = "(авто)"

    if not server_id:
        await callback.answer(f"❌ К сожалению, для тарифа «{TARIFFS[tariff_id]['name']}» сейчас нет свободных мест.", show_alert=True)
        return

    await state.update_data(server_id=server_id)
    server = SERVERS.get(server_id)
    if not server:
        await callback.answer("❌ Сервер больше недоступен.", show_alert=True)
        return

    tariff = TARIFFS[tariff_id]
    image = IMAGES[image_id]
    user_profile = await db.get_user_profile(user_id)
    if not user_profile:
        await callback.answer("❌ Профиль не найден. Выполните /start.", show_alert=True)
        return

    await state.set_state(UserBotCreateState.confirming_creation)

    final_price = await calculate_final_price(tariff_id, server_id, user_profile)

    price_text = ""
    if user_profile.get('has_free_container_promo', 0) and tariff_id == 'basic':
        base_price = TARIFFS['basic']['price_rub']
        price_text = f"<s>{base_price} RUB</s> <b>Бесплатно</b> (по промокоду)"
    elif tariff_id == 'free':
        price_text = lex.get('free_tariff_days', "Free (2 дня)")
    elif user_profile.get('active_discount_percent', 0) > 0:
        base_price = TARIFFS[tariff_id]['price_rub']
        price_text = f"<s>{base_price} RUB</s> <b>{final_price:.2f} RUB</b> (с учетом скидки {user_profile.get('active_discount_percent', 0)}%)"
    else:
        reg_date_str = user_profile['reg_date']
        if '+' in reg_date_str: reg_date_str = reg_date_str.split('+')[0]
        if '.' in reg_date_str: reg_date_str = reg_date_str.split('.')[0]
        try:
            reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            reg_date = datetime.now() - timedelta(days=2)

        is_new_user_for_discount = (datetime.now() - reg_date) < timedelta(days=1) and not await db.get_user_containers(user_id)
        base_price = TARIFFS[tariff_id]['price_rub']

        if is_new_user_for_discount and base_price > 0:
            price_text = f"<s>{base_price} RUB</s> <b>{final_price:.2f} RUB</b> (с учетом скидки 10% для новичка)"
        else:
            price_text = f"{final_price:.2f} RUB"

    confirmation_text = (
        lex.get('tariffs_step4_prompt_title', "<b>Шаг 4/4:</b> Проверьте заказ.") +
        f"\n\n<b>Сервер {server_choice_text}:</b> {server['name']}\n"
        f"<b>Тариф:</b> {tariff['name']} ({tariff['ram_mb']}MB RAM)\n<b>Образ:</b> {image['name']}\n\n"
        f"<b>К списанию:</b> {price_text}\n\n" +
        lex.get('tariffs_step4_prompt_footer', "Подтвердите создание.")
    )

    try:
        await callback.message.edit_text(
            text=confirmation_text,
            reply_markup=get_confirmation_keyboard(language_code)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logging.warning(f"Ошибка при обновлении подтверждения создания: {e}")
