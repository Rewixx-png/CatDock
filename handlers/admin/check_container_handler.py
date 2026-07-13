import asyncio
import logging
import json
from aiogram import Router, types, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

import database as db
import utils.docker as dm
from config import SERVERS
from keyboards.admin import get_checkcont_keyboard
from keyboards.common_keyboards import get_simple_confirmation_keyboard
from states.user_states import AdminCheckState
from lexicon import LEXICON
from utils.filters import IsAdmin
from roles import UserRole
from utils.action_logger import log_action
import settings

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.CO_OWNER))
router.callback_query.filter(IsAdmin(min_level=UserRole.CO_OWNER))

@router.message(Command("checkcont"))
async def check_containers_command(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    status_msg = await message.answer("⏳ Начинаю сканирование всех серверов на наличие 'осиротевших' контейнеров...")

    try:
        db_container_names = await db.get_all_container_names()

        orphans = []
        for server_id, server_info in SERVERS.items():
            await status_msg.edit_text(f"⏳ Проверяю сервер <b>{server_info['name']}</b>...")
            try:
                command = 'docker ps -a --filter "name=cat-*" --format "{{.Names}}"'
                result = await dm.run_command_on_server(server_id, command, check=False, timeout=20)

                if result.stdout.strip():
                    server_containers = result.stdout.strip().splitlines()
                    for container_name in server_containers:
                        if container_name in settings.SYSTEM_CONTAINERS_LIST:
                            continue

                        if container_name not in db_container_names:
                            orphans.append({'name': container_name, 'server_id': server_id})
            except Exception as e:
                logging.error(f"Не удалось просканировать сервер {server_id}: {e}")
                await message.answer(f"⚠️ Не удалось просканировать сервер <b>{server_info['name']}</b>. Ошибка: {e}")

        if not orphans:
            await status_msg.edit_text("✅ 'Осиротевших' контейнеров не найдено. Все контейнеры на серверах соответствуют базе данных.")
            return

        report_text = f"⚠️ <b>Найдены 'осиротевшие' контейнеры ({len(orphans)} шт.)!</b>\n\nЭто контейнеры, которые существуют на серверах, но отсутствуют в базе данных бота. Рекомендуется удалить их.\n\n<b>Список:</b>\n"
        for orphan in orphans:
            report_text += f"- <code>{orphan['name']}</code> (на сервере {SERVERS[orphan['server_id']]['name']})\n"

        await state.update_data(orphans_to_delete=orphans)

        await status_msg.edit_text(report_text, reply_markup=get_checkcont_keyboard(len(orphans), language_code))
        await log_action(bot, message.from_user, f"запустил проверку и нашел {len(orphans)} 'осиротевших' контейнеров")

    except Exception as e:
        logging.critical(f"Критическая ошибка при выполнении /checkcont: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Произошла критическая ошибка при выполнении проверки. Детали в логах.")

@router.callback_query(F.data == "admin_delete_checkcont")
async def confirm_delete_orphans(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await callback.message.edit_text(
        text="‼️ <b>Вы уверены, что хотите удалить все найденные 'осиротевшие' контейнеры?</b>\n\nЭто действие необратимо и удалит их с серверов.",
        reply_markup=get_simple_confirmation_keyboard(
            language_code,
            yes_callback="confirm_delete_checkcont_final",
            no_callback="admin_panel"
        )
    )
    await state.set_state(AdminCheckState.confirming_orphan_deletion)
    await callback.answer()

@router.callback_query(StateFilter(AdminCheckState.confirming_orphan_deletion), F.data == "confirm_delete_checkcont_final")
async def process_delete_orphans(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text("⏳ Удаляю 'осиротевшие' контейнеры...")

    data = await state.get_data()
    orphans_to_delete = data.get('orphans_to_delete', [])

    if not orphans_to_delete:
        await callback.answer("❌ Не найдены контейнеры для удаления. Возможно, состояние истекло.", show_alert=True)
        await state.clear()
        return

    deleted_count = 0
    error_count = 0

    for orphan in orphans_to_delete:
        if orphan['name'] in settings.SYSTEM_CONTAINERS_LIST:
            logging.warning(f"SKIP SAFEGUARD: Попытка удалить системный контейнер {orphan['name']} предотвращена.")
            continue

        try:
            await dm.delete_container(orphan['server_id'], orphan['name'])
            deleted_count += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            error_count += 1
            logging.error(f"Не удалось удалить 'осиротевший' контейнер {orphan['name']} с сервера {orphan['server_id']}: {e}")

    await log_action(bot, callback.from_user, f"удалил {deleted_count} 'осиротевших' контейнеров ({error_count} с ошибкой)")

    await callback.message.edit_text(f"✅ Готово!\n\n- Успешно удалено: {deleted_count}\n- Ошибок при удалении: {error_count}")
    await state.clear()
