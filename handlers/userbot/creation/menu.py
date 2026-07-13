import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

import database as db
from config import TARIFFS, IMAGES
from keyboards import (
    get_creation_hub_keyboard,
    get_tariff_selection_for_hub,
    get_image_selection_for_hub
)
from states.user_states import UserBotCreateState
from lexicon import LEXICON
from utils.action_logger import log_action
from ...common.menu_utils import set_loading_state


router = Router()

async def show_creation_hub(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'

    await state.set_state(UserBotCreateState.hub_selection)
    selection_data = await state.get_data()

    markup = get_creation_hub_keyboard(language_code, selection_data)
    caption = "<b>Выберите конфигурацию для вашего UserBot'а</b>\n\nНажимайте на категории, чтобы выбрать нужный пункт. Когда все будет готово, кнопка 'Готово' станет активной."

    try:
        await callback.message.edit_text(caption, reply_markup=markup)
    except (TelegramBadRequest, TelegramNetworkError, Exception) as e:
        logging.warning(f"Ошибка при обновлении меню конструктора: {e}. Пробую пересоздать сообщение.")
        try:
            await callback.message.delete()
        except Exception: 
            pass
        await callback.message.answer(caption, reply_markup=markup)

    try:
        await callback.answer()
    except Exception: 
        pass

@router.callback_query(F.data == "tariffs")
async def start_creation_hub(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    await set_loading_state(callback, "Конструктор")
    await log_action(bot, callback.from_user, "начал создание UserBot'а (вошел в меню-конструктор)")
    await state.clear() 
    await show_creation_hub(callback, state, bot)

@router.callback_query(UserBotCreateState.hub_selection, F.data.startswith("create_select:"))
async def select_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'

    if category == "tariff":
        await state.set_state(UserBotCreateState.choosing_tariff)
        markup = await get_tariff_selection_for_hub(language_code, user_id)
        await callback.message.edit_caption(caption="<b>Шаг 1: Выбор Тарифа</b>", reply_markup=markup)
    elif category == "image":
        await state.set_state(UserBotCreateState.choosing_image)
        await callback.message.edit_caption(caption="<b>Шаг 2: Выбор Образа</b>", reply_markup=get_image_selection_for_hub(language_code))
    await callback.answer()

@router.callback_query(F.data.startswith("create_set:"))
async def set_option_and_return_to_hub(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    parts = callback.data.split(":")
    option_type = parts[1]
    option_value = parts[2]

    current_state = await state.get_state()
    if not current_state:
         await state.set_state(UserBotCreateState.hub_selection)

    await state.update_data({f"{option_type}_id": option_value})
    await show_creation_hub(callback, state, bot)

@router.callback_query(F.data == "create_hub:back")
async def back_to_hub(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await show_creation_hub(callback, state, bot)

@router.callback_query(UserBotCreateState.hub_selection, F.data == "create_hub:incomplete")
async def incomplete_selection(callback: types.CallbackQuery):
    await callback.answer("❌ Пожалуйста, выберите тариф и образ.", show_alert=True)

@router.callback_query(F.data.in_({"free_tariff_used"}))
async def info_callbacks(callback: types.CallbackQuery):
    await callback.answer("❌ Вы уже использовали свой бесплатный пробный период.", show_alert=True)

@router.callback_query(F.data.startswith("create_select:"))
@router.callback_query(F.data == "create_hub:incomplete")
async def handle_expired_session(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer("⚠️ Время сессии истекло. Перезагружаем меню...", show_alert=True)
    await start_creation_hub(callback, state, bot)
