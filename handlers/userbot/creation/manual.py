from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import SERVERS
from utils import bot_state
from keyboards.userbot.creation import get_manual_server_selection_keyboard
from states.user_states import UserBotCreateState
from .menu import show_creation_hub, start_creation_hub

router = Router()

@router.callback_query(UserBotCreateState.hub_selection, F.data == "manual_server_select")
async def manual_server_select_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    await state.set_state(UserBotCreateState.choosing_server_manually)

    markup = await get_manual_server_selection_keyboard(language_code, user_id)

    try:
        await callback.message.edit_text(text="<b>Выберите сервер для размещения вручную:</b>", reply_markup=markup)
    except TelegramBadRequest:
        
        try:
            await callback.message.answer("<b>Выберите сервер для размещения вручную:</b>", reply_markup=markup)
        except Exception:
            pass

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

@router.callback_query(UserBotCreateState.choosing_server_manually, F.data.startswith("set_manual_server:"))
async def set_manual_server_and_return(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    server_id = callback.data.split(":")[1]

    if server_id == 'auto':
        await state.update_data(manual_server_id=None)
    else:
        if server_id not in SERVERS or not bot_state.server_states.get(server_id, True):
            await callback.answer("❌ Сервер недоступен.", show_alert=True)
            return
        await state.update_data(manual_server_id=server_id)

    await show_creation_hub(callback, state, bot)

@router.callback_query(F.data == "manual_server_select")
async def manual_server_select_expired(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.answer("⚠️ Сессия истекла. Перезагрузка...", show_alert=True)
    except TelegramBadRequest:
        pass
    await start_creation_hub(callback, state, bot)
