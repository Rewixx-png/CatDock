from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext

import database as db
from config import TARIFFS, SUBSCRIPTION_PLANS, DEFAULT_CPU_LIMIT, CPU_UPGRADE_PRICE, RAM_UPGRADE_PRICE
from keyboards import get_extend_options_keyboard
from states.user_states import ExtendSubscriptionState
from lexicon import LEXICON
from ..common.menu_utils import show_management_menu
from utils.action_logger import log_action 

router = Router()

@router.callback_query(F.data.startswith("extend_bot_start:"))
async def start_extend(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    container = await db.get_container_for_actor(
        container_id, callback.from_user.id, allow_admin=False
    )
    if not container:
        await callback.answer("❌ Контейнер не найден.", show_alert=True)
        return

    tariff_id = container.get('tariff_id')
    if tariff_id == 'free' or not TARIFFS.get(tariff_id):
        await callback.answer(lex.get('extend_free_not_allowed'), show_alert=True)
        return

    await state.set_state(ExtendSubscriptionState.confirming_extension)
    await state.update_data(container_id=container_id)

    tariff_price = TARIFFS[tariff_id]['price_rub']

    current_cpu_limit = container.get('cpu_limit') or DEFAULT_CPU_LIMIT
    extra_cpu_cores = current_cpu_limit - DEFAULT_CPU_LIMIT

    cpu_monthly_cost = 0
    if extra_cpu_cores > 0:
        cpu_monthly_cost = CPU_UPGRADE_PRICE * (extra_cpu_cores / 0.1)

    base_ram_mb = TARIFFS.get(tariff_id, {}).get('ram_mb', 300)
    actual_ram_mb = container.get('ram_mb') or base_ram_mb
    extra_ram_mb = actual_ram_mb - base_ram_mb
    ram_monthly_cost = 0
    if extra_ram_mb > 0:
        ram_monthly_cost = RAM_UPGRADE_PRICE * (extra_ram_mb / 100.0)

    caption = lex.get('extend_prompt')
    if cpu_monthly_cost > 0:
        caption += "\n\n" + lex.get('extend_cpu_surcharge_info').format(
            cpu_percent=int(current_cpu_limit * 100),
            cpu_cost=cpu_monthly_cost
        )
    if ram_monthly_cost > 0:
        caption += "\n\n" + lex.get('extend_ram_surcharge_info').format(
            actual_ram=actual_ram_mb,
            ram_cost=ram_monthly_cost
        )

    await callback.message.edit_text(
        text=caption,
        reply_markup=get_extend_options_keyboard(container_id, tariff_price, cpu_monthly_cost, ram_monthly_cost, language_code)
    )
    await callback.answer()

@router.callback_query(ExtendSubscriptionState.confirming_extension, F.data.startswith("extend_confirm:"))
async def confirm_extension(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        _, container_id_str, months_str = callback.data.split(":")
        container_id, months = int(container_id_str), int(months_str)
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных. Попробуйте снова.", show_alert=True)
        return

    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    container = await db.get_container_for_actor(
        container_id, user_id, allow_admin=False
    )
    if not container:
        await callback.answer("❌ Контейнер не найден.", show_alert=True)
        return

    tariff = TARIFFS.get(container.get('tariff_id'))
    if not tariff or container.get('tariff_id') == 'free':
        await callback.answer(lex.get('extend_free_not_allowed'), show_alert=True)
        return

    tariff_price = tariff['price_rub']
    plan = next((p for p in SUBSCRIPTION_PLANS if p['months'] == months), None)

    if not plan:
        await callback.answer("Ошибка: неверный план подписки.", show_alert=True)
        return

    current_cpu_limit = container.get('cpu_limit') or DEFAULT_CPU_LIMIT
    extra_cpu_cores = current_cpu_limit - DEFAULT_CPU_LIMIT
    cpu_monthly_cost = 0
    if extra_cpu_cores > 0:
        cpu_monthly_cost = CPU_UPGRADE_PRICE * (extra_cpu_cores / 0.1)

    base_ram_mb = TARIFFS.get(container['tariff_id'], {}).get('ram_mb', 300)
    actual_ram_mb = container.get('ram_mb') or base_ram_mb
    extra_ram_mb = actual_ram_mb - base_ram_mb
    ram_monthly_cost = 0
    if extra_ram_mb > 0:
        ram_monthly_cost = RAM_UPGRADE_PRICE * (extra_ram_mb / 100.0)

    base_price = (tariff_price + cpu_monthly_cost + ram_monthly_cost) * months
    final_price = base_price * (1 - plan['discount_percent'] / 100)

    seconds_to_add = plan['months'] * 30 * 24 * 60 * 60
    success, reason, cashback = await db.purchase_container_time(
        user_id,
        container_id,
        seconds_to_add,
        final_price,
    )
    if not success:
        if reason == 'insufficient_funds':
            error_text = lex.get('extend_insufficient_funds').format(
                cost=final_price,
                balance=await db.get_user_balance(user_id),
            )
        elif reason in {'forbidden', 'not_found'}:
            error_text = "❌ Контейнер не найден или недоступен."
        else:
            error_text = "❌ Не удалось продлить подписку. Попробуйте позже."
        await callback.answer(
            error_text,
            show_alert=True
        )
        return

    success_msg = lex.get('extend_success', "✅ Подписка успешно продлена!")
    if cashback > 0:
        success_msg += f"\n🎁 Кешбэк: +{cashback:.2f} RUB"

    log_text = (
        f"продлил контейнер '{container['container_name']}' на {months} мес. "
        f"за {final_price:.2f} RUB (включая доплату за ресурсы)"
    )
    await log_action(bot, callback.from_user, log_text)

    await callback.answer(success_msg, show_alert=True)

    await show_management_menu(callback, container_id, state, bot)
