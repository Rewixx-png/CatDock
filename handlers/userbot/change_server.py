from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
import database as db
from config import SERVERS, TARIFFS
from keyboards import get_simple_confirmation_keyboard, get_change_server_keyboard
from states.user_states import ChangeServerState
from lexicon import LEXICON
from .manager.list import my_userbots_menu_handler as my_userbots_menu
from utils.worker_tasks import task_change_server
from utils import bot_state

router = Router()

@router.callback_query(F.data.startswith("change_server_start:"))
async def change_server_start(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    container = await db.get_container_for_actor(
        container_id, callback.from_user.id, allow_admin=False
    )
    if not container:
        await callback.answer("❌ Контейнер не найден или недоступен.", show_alert=True)
        return

    await state.set_state(ChangeServerState.choosing_new_server)
    await state.update_data(container_id=container_id)
    await callback.message.edit_text(
        text=LEXICON[language_code]['change_server_prompt'],
        reply_markup=get_change_server_keyboard(language_code, container['server_id'], container['tariff_id'])
    )

@router.callback_query(ChangeServerState.choosing_new_server, F.data.startswith("change_server_select:"))
async def change_server_select(callback: types.CallbackQuery, state: FSMContext):
    new_server_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])

    data = await state.get_data()
    container_id = data.get('container_id')
    container = (
        await db.get_container_for_actor(container_id, user_id, allow_admin=False)
        if container_id else None
    )
    if (
        not container
        or new_server_id not in SERVERS
        or new_server_id == container['server_id']
        or not bot_state.server_states.get(new_server_id, True)
    ):
        await callback.answer("❌ Сервер или контейнер недоступен.", show_alert=True)
        await state.clear()
        return

    new_server_name = SERVERS.get(new_server_id, {}).get('name', 'N/A')

    caption = lex.get('confirm_server_change_prompt').format(server_name=new_server_name)
    caption += "\n\n<b>Это действие бесплатно.</b>"

    await state.update_data(new_server_id=new_server_id)
    await state.set_state(ChangeServerState.confirming_change)
    await callback.message.edit_text(
        text=caption,
        reply_markup=get_simple_confirmation_keyboard(language_code, "confirm_server_change", "cancel_change")
    )

@router.callback_query(ChangeServerState.confirming_change, F.data == "confirm_server_change")
async def change_server_confirm(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    container_id, new_server_id = data['container_id'], data['new_server_id']
    
    container = await db.get_container_for_actor(
        container_id, callback.from_user.id, allow_admin=False
    )
    if (
        not container
        or new_server_id not in SERVERS
        or new_server_id == container['server_id']
        or not bot_state.server_states.get(new_server_id, True)
    ):
        await my_userbots_menu(callback, state)
        return

    user = callback.from_user

    await task_change_server.kiq(
        chat_id=user.id,
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        container_id=container_id,
        old_server_id=container['server_id'],
        old_container_name=container['container_name'],
        new_server_id=new_server_id,
        tariff_id=container['tariff_id'] if container['tariff_id'] in TARIFFS else 'basic',
        image_id=container['image_id']
    )

    await callback.message.edit_text(text="⏳ <b>Миграция запущена.</b>\nМы переносим вашего бота на новый сервер. Это займет некоторое время.")
    await state.clear()
