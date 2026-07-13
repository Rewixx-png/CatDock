from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
import database as db
from config import TARIFFS, IMAGES
from keyboards import get_change_image_keyboard, get_simple_confirmation_keyboard
from states.user_states import ChangeImageState
from lexicon import LEXICON
from utils.worker_tasks import task_change_image

router = Router()

@router.callback_query(F.data.startswith("change_image_start:"))
async def change_image_start(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    container = await db.get_container_for_actor(container_id, callback.from_user.id)
    if not container:
        await callback.answer("❌ Контейнер не найден или недоступен.", show_alert=True)
        return

    await state.set_state(ChangeImageState.choosing_new_image)
    await state.update_data(container_id=container_id)
    await callback.message.edit_text(
        text=LEXICON[language_code]['change_image_prompt'],
        reply_markup=get_change_image_keyboard(language_code, container['image_id'])
    )
    await callback.answer()

@router.callback_query(ChangeImageState.choosing_new_image, F.data.startswith("change_image_select:"))
async def change_image_select(callback: types.CallbackQuery, state: FSMContext):
    new_image_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])

    data = await state.get_data()
    container_id = data.get('container_id')
    container = await db.get_container_for_actor(container_id, user_id) if container_id else None
    if not container or new_image_id not in IMAGES:
        await callback.answer("❌ Образ или контейнер недоступен.", show_alert=True)
        await state.clear()
        return

    new_image_name = IMAGES.get(new_image_id, {}).get('name', 'N/A')

    caption = lex.get('confirm_image_change_prompt').format(image_name=new_image_name)
    caption += "\n\n<b>" + (lex.get('free_action_note', "Это действие бесплатно.")) + "</b>"

    await state.update_data(new_image_id=new_image_id)
    await state.set_state(ChangeImageState.confirming_change)
    await callback.message.edit_text(
        text=caption,
        reply_markup=get_simple_confirmation_keyboard(language_code, "confirm_image_change", "cancel_change")
    )

@router.callback_query(ChangeImageState.confirming_change, F.data == "confirm_image_change")
async def change_image_confirm(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    container_id, new_image_id = data['container_id'], data['new_image_id']
    container = await db.get_container_for_actor(container_id, callback.from_user.id)

    if not container or new_image_id not in IMAGES:
        await callback.answer("❌ Контейнер или образ недоступен.", show_alert=True)
        await state.clear()
        return

    user = callback.from_user
    
    await task_change_image.kiq(
        chat_id=user.id,
        user_id=user.id,
        first_name=user.first_name,
        container_id=container_id,
        server_id=container['server_id'],
        container_name=container['container_name'],
        old_image_name=IMAGES.get(container['image_id'], {}).get('name', container['image_id']),
        new_image_id=new_image_id,
        tariff_id=container['tariff_id'] if container['tariff_id'] in TARIFFS else 'basic',
        external_port=container['external_port']
    )

    await callback.message.edit_text(text="⏳ <b>Смена образа запущена.</b>\nОжидайте уведомления.")
    await state.clear()
