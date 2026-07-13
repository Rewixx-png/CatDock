from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import database as db
from config import TARIFFS, IMAGES
from keyboards import get_simple_confirmation_keyboard
from states.user_states import ReinstallState
from lexicon import LEXICON
from ..common.menu_utils import show_management_menu
from utils.worker_tasks import task_reinstall_container

router = Router()

@router.callback_query(F.data.startswith("reinstall_bot_start:"))
async def reinstall_start(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await state.set_state(ReinstallState.confirming_reinstall)
    await state.update_data(container_id=container_id)
    await callback.message.edit_caption(
        caption=LEXICON[language_code]['reinstall_confirm_text'], 
        reply_markup=get_simple_confirmation_keyboard(language_code, "confirm_reinstall", "cancel_change")
    )
    await callback.answer()

@router.callback_query(ReinstallState.confirming_reinstall, F.data == "confirm_reinstall")
async def reinstall_confirm(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    container_id = data['container_id']
    container = await db.get_container_by_id(container_id)

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
        tariff_data=TARIFFS[container['tariff_id']],
        image_data=IMAGES[container['image_id']],
        username_for_create=user.username
    )

    try:
        await callback.message.edit_caption(
            caption="⏳ <b>Задача на переустановку принята.</b>\nОжидайте уведомления.",
            reply_markup=None
        )
    except TelegramBadRequest: pass
    
    await state.clear()
