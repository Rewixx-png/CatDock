import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

import database as db
from config import SERVERS
from keyboards.admin import get_orphaned_containers_keyboard
from keyboards import get_simple_confirmation_keyboard
from states.user_states import AdminOrphanState
from lexicon import LEXICON
from utils.filters import IsAdmin
from roles import UserRole
from .main_menu import admin_dashboard as admin_main_menu 
from utils.action_logger import log_action

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.CO_OWNER))
router.callback_query.filter(IsAdmin(min_level=UserRole.CO_OWNER))

@router.message(Command("orphans"))
async def find_orphaned_containers(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await message.answer("⏳ Идет поиск 'осиротевших' контейнеров...")

    valid_server_ids = set(SERVERS.keys())
    orphaned_containers = await db.find_orphaned_containers(valid_server_ids)

    if not orphaned_containers:
        await message.answer(lex.get('orphans_not_found', "✅ 'Осиротевшие' контейнеры не найдены. Все записи в БД актуальны."))
        return

    await log_action(bot, message.from_user, f"запустил проверку и нашел {len(orphaned_containers)} 'осиротевших' контейнеров")

    text_parts = [
        lex.get('orphans_found_text', "⚠️ <b>Найдены 'осиротевшие' контейнеры!</b>\n\nЭто записи о контейнерах, чьи серверы были удалены из конфигурации. Рекомендуется удалить эти записи, чтобы избежать ошибок.").format(count=len(orphaned_containers))
    ]
    for container in orphaned_containers:
        text_parts.append(
            f"- ID: <code>{container['id']}</code>, Имя: <code>{container['container_name']}</code>, "
            f"Сервер: <code>{container['server_id']}</code>, Юзер: <code>{container['user_id']}</code>"
        )

    text = "\n".join(text_parts)

    await state.update_data(orphaned_ids=[c['id'] for c in orphaned_containers])

    await message.answer(
        text=text,
        reply_markup=get_orphaned_containers_keyboard(len(orphaned_containers), language_code)
    )

@router.callback_query(F.data == "admin_delete_orphans")
async def confirm_delete_orphans(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await callback.message.edit_text(
        text=lex.get('orphans_confirm_deletion', "Вы уверены, что хотите удалить все найденные записи? Это действие необратимо."),
        reply_markup=get_simple_confirmation_keyboard(
            language_code,
            yes_callback="admin_confirm_delete_orphans",
            no_callback="cancel_admin_action:admin_panel"
        )
    )
    await state.set_state(AdminOrphanState.confirming_deletion)
    await callback.answer()

@router.callback_query(StateFilter(AdminOrphanState.confirming_deletion), F.data == "admin_confirm_delete_orphans")
async def process_delete_orphans(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text("⏳ Удаляю записи из базы данных...")

    data = await state.get_data()
    orphaned_ids = data.get('orphaned_ids', [])

    if not orphaned_ids:
        await callback.answer("❌ Не найдены ID для удаления. Возможно, состояние истекло. Попробуйте снова.", show_alert=True)
        await state.clear()
        return

    deleted_count = 0
    for container_id in orphaned_ids:
        await db.delete_user_container(container_id)
        deleted_count += 1

    await log_action(bot, callback.from_user, f"подтвердил и удалил {deleted_count} 'осиротевших' контейнеров из БД")

    await callback.message.edit_text(f"✅ Успешно удалено {deleted_count} записей.")
    await state.clear()
    await admin_main_menu(callback, state)

@router.callback_query(StateFilter(AdminOrphanState.confirming_deletion), F.data == "cancel_admin_action:admin_panel")
async def cancel_delete_orphans(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await admin_main_menu(callback, state)
    await callback.answer("Удаление отменено.")
