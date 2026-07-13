import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import CPU_UPGRADE_PRICE, DEFAULT_CPU_LIMIT
from keyboards.admin import get_cancel_admin_action_keyboard
from keyboards import get_cpu_upgrade_keyboard
from states.user_states import AdminUpgradeCpuState
from lexicon import LEXICON
from utils.filters import IsAdmin
from roles import UserRole
from utils.action_logger import log_action
import utils.docker as dm
from ..common.menu_utils import show_management_menu

router = Router()
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.callback_query(F.data == "admin_upgrade_cpu_start")
async def start_admin_cpu_upgrade(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await state.set_state(AdminUpgradeCpuState.waiting_for_container_id)
    await callback.message.edit_caption(
        caption=lex.get('admin_upgrade_cpu_prompt_id', "Введите ID контейнера для изменения лимита CPU:"),
        reply_markup=get_cancel_admin_action_keyboard("admin_panel", language_code)
    )
    await callback.answer()

@router.message(AdminUpgradeCpuState.waiting_for_container_id)
async def process_container_id(message: types.Message, state: FSMContext, bot: Bot):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        container_id = int(message.text)
    except (ValueError, TypeError):
        await message.reply("❌ Введите корректный ID (только цифры).")
        return

    container = await db.get_container_by_id(container_id)
    if not container:
        await message.reply(f"❌ Контейнер с ID <code>{container_id}</code> не найден.")
        return

    try:
        await message.delete()
        await bot.delete_message(message.chat.id, message.message_id - 1)
    except TelegramBadRequest:
        pass

    current_limit = container.get('cpu_limit') or DEFAULT_CPU_LIMIT

    await state.set_state(AdminUpgradeCpuState.choosing_option)
    await state.update_data(container_id=container_id)

    await message.answer(
        text=lex.get('upgrade_cpu_prompt', "Выберите, на сколько вы хотите увеличить лимит CPU."),
        reply_markup=get_cpu_upgrade_keyboard(container_id, current_limit, language_code)
    )

async def _apply_cpu_update_task(bot: Bot, admin_id: int, container_id: int, new_limit: float):
    status_msg = await bot.send_message(admin_id, f"🚀 Применяю новый лимит CPU {new_limit*100:.0f}% для контейнера #{container_id}...")

    try:
        container = await db.get_container_by_id(container_id)
        if not container:
            raise Exception("Контейнер не найден в БД во время выполнения задачи.")

        await dm.run_command_on_server(
            container['server_id'],
            f"docker update --cpus=\"{new_limit:.2f}\" {container['container_name']}"
        )

        await db.update_container_cpu_limit(container_id, new_limit)

        target_user = await bot.get_chat(container['user_id'])
        admin_user = await bot.get_chat(admin_id)

        await log_action(bot, admin_user, f"изменил лимит CPU для '{container['container_name']}' на {new_limit*100:.0f}%", target_user)

        await status_msg.edit_text(f"✅ Лимит CPU для контейнера #{container_id} успешно обновлен до {new_limit*100:.0f}%.")

    except Exception as e:
        logging.error(f"Критическая ошибка при админском изменении CPU для {container_id}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка при обновлении лимита CPU для контейнера #{container_id}. Подробности в логах.")

@router.callback_query(AdminUpgradeCpuState.choosing_option, F.data.startswith("upgrade_cpu_for:"))
async def process_admin_cpu_upgrade(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id

    try:
        _, container_id_str, percent_str = callback.data.split(":")
        container_id = int(container_id_str)
        percent_to_add = int(percent_str)
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных. Попробуйте снова.", show_alert=True)
        return

    cores_to_add = percent_to_add / 100.0
    container = await db.get_container_by_id(container_id)
    if not container:
        await callback.answer("❌ Контейнер не найден.", show_alert=True)
        return

    new_limit = (container.get('cpu_limit') or DEFAULT_CPU_LIMIT) + cores_to_add

    await callback.message.delete()
    await callback.answer(f"✅ Задача на обновление лимита CPU для контейнера #{container_id} запущена в фоне.", show_alert=True)

    asyncio.create_task(_apply_cpu_update_task(
        bot=bot,
        admin_id=user_id,
        container_id=container_id,
        new_limit=new_limit
    ))

    await state.clear()
