import asyncio
import logging
import json
from aiogram import Router, types, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
import utils.docker as dm
from config import SERVERS
from keyboards.admin import get_fixloop_list_keyboard
from keyboards import get_simple_confirmation_keyboard
from states.user_states import AdminFixLoopState
from lexicon import LEXICON
from utils.filters import IsAdmin
from roles import UserRole
from utils.action_logger import log_action

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.CO_OWNER))
router.callback_query.filter(IsAdmin(min_level=UserRole.CO_OWNER))

@router.message(Command("fixloop"))
async def find_looping_containers(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    status_msg = await message.answer(lex.get('fixloop_scan_start', "⏳ Сканирую серверы на наличие Restart Loop..."))

    restarting_containers = []

    for server_id, server_info in SERVERS.items():
        try:
            command = 'docker ps -a --filter "status=restarting" --filter "name=cat-" --format "{{json .}}"'
            result = await dm.run_command_on_server(server_id, command, check=False)

            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    try:
                        container_data = json.loads(line)
                        container_name = container_data.get("Names")

                        container_db_info = await db.get_container_by_name(container_name)
                        if container_db_info:
                            restarting_containers.append({
                                'db_id': container_db_info['id'],
                                'user_id': container_db_info['user_id'],
                                'name': container_name,
                                'server_id': server_id,
                                'server_name': server_info['name'],
                                'image': container_data.get("Image")
                            })
                    except (json.JSONDecodeError, KeyError) as e:
                        logging.error(f"Ошибка парсинга вывода docker ps с сервера {server_id}: {e} | Строка: {line}")

        except Exception as e:
            logging.error(f"Не удалось просканировать сервер {server_id} на наличие зацикленных контейнеров: {e}")

    await state.update_data(restarting_containers=restarting_containers)

    if not restarting_containers:
        await status_msg.edit_text(lex.get('fixloop_scan_no_results', "✅ Зацикленных контейнеров не найдено."))
        return

    text_parts = [lex.get('fixloop_scan_results_title', "⚠️ <b>Найдены зацикленные контейнеры ({count}):</b>").format(count=len(restarting_containers))]
    for c in restarting_containers:
        text_parts.append(f"• <code>{c['name']}</code> (Сервер: {c['server_name']}, Образ: {c['image']})")

    await status_msg.edit_text("\n".join(text_parts), reply_markup=get_fixloop_list_keyboard(restarting_containers))

@router.callback_query(F.data.startswith("fixloop_delete_start:"))
async def confirm_fixloop_delete(callback: types.CallbackQuery, state: FSMContext):
    container_db_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    data = await state.get_data()
    restarting_containers = data.get('restarting_containers', [])
    container_to_delete = next((c for c in restarting_containers if c['db_id'] == container_db_id), None)

    if not container_to_delete:
        await callback.answer("❌ Контейнер не найден в списке. Возможно, он уже удален.", show_alert=True)
        return

    await state.set_state(AdminFixLoopState.confirming_deletion)
    await state.update_data(container_to_delete=container_to_delete)

    await callback.message.edit_text(
        text=lex.get('fixloop_confirm_deletion', "Удалить контейнер <b>{container_name}</b>?").format(container_name=container_to_delete['name']),
        reply_markup=get_simple_confirmation_keyboard(
            language_code,
            yes_callback="fixloop_confirm_delete",
            no_callback="fixloop_cancel_delete"
        )
    )
    await callback.answer()

@router.callback_query(AdminFixLoopState.confirming_deletion, F.data == "fixloop_confirm_delete")
async def process_fixloop_delete(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    container_to_delete = data.get('container_to_delete')

    if not container_to_delete:
        await callback.answer("❌ Ошибка состояния. Попробуйте снова.", show_alert=True)
        return

    server_id = container_to_delete['server_id']
    container_name = container_to_delete['name']
    container_db_id = container_to_delete['db_id']
    user_id = container_to_delete['user_id']
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await dm.delete_container(server_id, container_name)
        await db.delete_user_container(container_db_id)

        await log_action(bot, callback.from_user, f"удалил циклично перезагружающийся контейнер '{container_name}' (ID: {container_db_id})")

        try:
            user_lang = await db.get_user_language(user_id) or 'ru'
            user_lex = LEXICON[user_lang]
            notification = user_lex.get('fixloop_user_notification', "⚠️ Ваш контейнер <b>{container_name}</b> был удален администратором, так как он вошел в вечный цикл перезагрузки.").format(container_name=container_name)
            await bot.send_message(user_id, notification)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logging.warning(f"Не удалось уведомить пользователя {user_id} об удалении зацикленного контейнера: {e}")

        await callback.answer(lex.get('fixloop_deleted_success', "✅ Контейнер удален."), show_alert=True)

    except Exception as e:
        logging.error(f"Ошибка при удалении зацикленного контейнера {container_name}: {e}", exc_info=True)
        await callback.answer(lex.get('fixloop_deleted_error', "❌ Ошибка удаления."), show_alert=True)

    all_containers_in_state = data.get('restarting_containers', [])
    updated_containers = [c for c in all_containers_in_state if c['db_id'] != container_db_id]
    await state.update_data(restarting_containers=updated_containers)

    if not updated_containers:
        await callback.message.edit_text(lex.get('fixloop_scan_no_results', "✅ Зацикленных контейнеров не найдено."))
    else:
        text_parts = [lex.get('fixloop_scan_results_title', "⚠️ <b>Найдены зацикленные контейнеры ({count}):</b>").format(count=len(updated_containers))]
        for c in updated_containers:
            text_parts.append(f"• <code>{c['name']}</code> (Сервер: {c['server_name']}, Образ: {c['image']})")
        await callback.message.edit_text("\n".join(text_parts), reply_markup=get_fixloop_list_keyboard(updated_containers))

@router.callback_query(AdminFixLoopState.confirming_deletion, F.data == "fixloop_cancel_delete")
async def cancel_fixloop_delete(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    restarting_containers = data.get('restarting_containers', [])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    text_parts = [lex.get('fixloop_scan_results_title', "⚠️ <b>Найдены зацикленные контейнеры ({count}):</b>").format(count=len(restarting_containers))]
    for c in restarting_containers:
        text_parts.append(f"• <code>{c['name']}</code> (Сервер: {c['server_name']}, Образ: {c['image']})")

    await callback.message.edit_text("\n".join(text_parts), reply_markup=get_fixloop_list_keyboard(restarting_containers))
    await state.clear()
    await callback.answer("Удаление отменено.")
