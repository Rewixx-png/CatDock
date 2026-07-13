import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
import utils.docker as dm
from keyboards import get_simple_confirmation_keyboard, get_cancel_admin_action_keyboard
from states.user_states import AdminUnfreezeAllState
from lexicon import LEXICON
from utils.filters import IsAdmin
from roles import UserRole
from utils.action_logger import log_action
from .main_menu import admin_dashboard as admin_main_menu
from utils.ui_utils import safe_edit_caption

router = Router()
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

async def _perform_mass_unfreeze(bot: Bot, admin_id: int, reason: str, status_message: types.Message):
    language_code = await db.get_user_language(admin_id) or 'ru'
    lex = LEXICON[language_code]

    frozen_containers = await db.get_frozen_containers()
    total_count = len(frozen_containers)
    unfrozen_count = 0
    error_count = 0

    for i, container in enumerate(frozen_containers, 1):
        try:
            await dm.start_container(container['server_id'], container['container_name'])
            await db.set_container_frozen_state(container['id'], False)
            unfrozen_count += 1

            try:
                user_lang = await db.get_user_language(container['user_id']) or 'ru'
                user_lex = LEXICON[user_lang]
                notification_text = user_lex.get('user_mass_unfreeze_notification').format(
                    container_name=container['container_name'],
                    reason=reason
                )
                await bot.send_message(container['user_id'], notification_text)
            except (TelegramBadRequest, TelegramForbiddenError) as e:
                logging.warning(f"Не удалось уведомить пользователя {container['user_id']} о разморозке: {e}")

        except Exception as e:
            error_count += 1
            logging.error(f"Ошибка при разморозке контейнера {container['id']}: {e}", exc_info=True)

        if i % 5 == 0 or i == total_count:
            try:
                await status_message.edit_text(lex.get('admin_unfreeze_all_progress').format(processed=i, total=total_count))
            except TelegramBadRequest:
                pass

        await asyncio.sleep(0.5)

    final_text = lex.get('admin_unfreeze_all_finished').format(unfrozen_count=unfrozen_count, error_count=error_count)
    await status_message.edit_text(final_text)
    await log_action(bot, await bot.get_chat(admin_id), f"завершил массовую разморозку. Успешно: {unfrozen_count}, Ошибок: {error_count}. Причина: {reason}")

@router.callback_query(F.data == "admin_unfreeze_all_start")
async def start_unfreeze_all(callback: types.CallbackQuery):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    frozen_containers = await db.get_frozen_containers()
    count = len(frozen_containers)

    if count == 0:
        await callback.answer("✅ Нет замороженных контейнеров для разморозки.", show_alert=True)
        return

    await safe_edit_caption(
        callback.message,
        caption=lex.get('admin_unfreeze_all_confirm').format(count=count),
        reply_markup=get_simple_confirmation_keyboard(language_code, "admin_unfreeze_all_confirmed", "admin_panel")
    )
    await callback.answer()

@router.callback_query(F.data == "admin_unfreeze_all_confirmed")
async def confirm_unfreeze_all(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await callback.message.delete()
    msg = await callback.message.answer(
        text=lex.get('admin_unfreeze_all_reason_prompt'),
        reply_markup=get_cancel_admin_action_keyboard("admin_panel", language_code)
    )

    await state.set_state(AdminUnfreezeAllState.waiting_for_reason)
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(AdminUnfreezeAllState.waiting_for_reason)
async def process_unfreeze_reason_and_run(message: types.Message, state: FSMContext, bot: Bot):
    reason = message.text
    admin_id = message.from_user.id
    language_code = await db.get_user_language(admin_id) or 'ru'
    lex = LEXICON[language_code]

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')

    try:
        await message.delete()
        if prompt_message_id:
            await bot.delete_message(admin_id, prompt_message_id)
    except TelegramBadRequest:
        pass

    frozen_count = len(await db.get_frozen_containers())
    status_message = await message.answer(lex.get('admin_unfreeze_all_started').format(count=frozen_count))

    await log_action(bot, message.from_user, f"запустил массовую разморозку {frozen_count} контейнеров. Причина: {reason}")

    asyncio.create_task(
        _perform_mass_unfreeze(
            bot=bot,
            admin_id=admin_id,
            reason=reason,
            status_message=status_message
        )
    )

    await state.clear()
