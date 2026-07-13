from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import database as db
from config import TARIFFS, IMAGES
from keyboards import get_simple_confirmation_keyboard
from states.user_states import ReinstallState
from lexicon import LEXICON
from utils.worker_tasks import task_reinstall_container

router = Router()

@router.callback_query(F.data.startswith("reinstall_bot_start:"))
async def reinstall_start(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    container = await db.get_container_for_actor(container_id, callback.from_user.id)
    if not container:
        await callback.answer("❌ Контейнер не найден или недоступен.", show_alert=True)
        return
    await state.set_state(ReinstallState.confirming_reinstall)
    await state.update_data(container_id=container_id)
    await callback.message.edit_text(
        text=LEXICON[language_code]['reinstall_confirm_text'],
        reply_markup=get_simple_confirmation_keyboard(language_code, "confirm_reinstall", "cancel_change")
    )
    await callback.answer()

@router.callback_query(ReinstallState.confirming_reinstall, F.data == "confirm_reinstall")
async def reinstall_confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    container_id = data['container_id']
    container = await db.get_container_for_actor(container_id, callback.from_user.id)

    if not container:
        await callback.answer("❌ Контейнер не найден.", show_alert=True)
        return
        
    user = callback.from_user

    await task_reinstall_container.kiq(
        chat_id=user.id,
        user_id=user.id,
        first_name=user.first_name,
        container_db_id=container_id,
        server_id=container['server_id'],
        old_container_name=container['container_name'],
        tariff_data=TARIFFS.get(container['tariff_id'], TARIFFS['basic']),
        image_data=IMAGES.get(container['image_id'], IMAGES['catdock']),
        username_for_create=user.username
    )

    try:
        await callback.message.edit_text(
            text="⏳ <b>Задача на переустановку принята.</b>\nОжидайте уведомления.",
            reply_markup=None
        )
    except TelegramBadRequest: pass
    
    await state.clear()
