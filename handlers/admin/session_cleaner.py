import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BufferedInputFile

import database as db
import utils.docker as dm
from config import SERVERS, TARIFFS
from utils.filters import IsAdmin
from roles import UserRole
from states.user_states import AdminSessionScanState
from utils.action_logger import log_action

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.message(Command("session"))
async def cmd_scan_sessions(message: types.Message, state: FSMContext):
    await state.clear()
    status_msg = await message.answer("🕵️‍♂️ <b>Начинаю сканирование контейнеров на наличие сессий...</b>\n\nЭто может занять некоторое время. Пожалуйста, подождите.")

    all_containers = await db.get_active_containers()
    if not all_containers:
        await status_msg.edit_text("✅ В базе данных нет активных контейнеров.")
        return

    empty_containers = []
    scanned_count = 0
    skipped_count = 0

    async def check_container(container):
        nonlocal scanned_count, skipped_count

        if container['server_id'] not in SERVERS:
            skipped_count += 1
            return

        try:
            status = await dm.get_container_status(container['server_id'], container['container_name'])

            if status != 'running':
                skipped_count += 1
                return

            has_session = await dm.check_session_files_exist(container['server_id'], container['container_name'])

            if not has_session:
                days_left = round(container['remaining_seconds'] / 86400, 1)
                tariff_name = TARIFFS.get(container['tariff_id'], {}).get('name', str(container['tariff_id']))
                empty_containers.append({
                    'id': container['id'],
                    'name': container['container_name'],
                    'server': SERVERS[container['server_id']]['name'],
                    'server_id': container['server_id'],
                    'user_id': container['user_id'],
                    'days_left': days_left,
                    'tariff': tariff_name or "Unknown"
                })

            scanned_count += 1
        except Exception as e:
            logging.error(f"Ошибка сканирования {container['container_name']}: {e}")
            skipped_count += 1

    BATCH_SIZE = 10
    for i in range(0, len(all_containers), BATCH_SIZE):
        batch = all_containers[i:i+BATCH_SIZE]
        await asyncio.gather(*[check_container(c) for c in batch])

        if i % 20 == 0:
             try:
                 await status_msg.edit_text(f"🕵️‍♂️ Сканирование... Проверено: {scanned_count}/{len(all_containers)}")
             except: pass

    if not empty_containers:
        await status_msg.edit_text(
            f"✅ <b>Сканирование завершено!</b>\n\n"
            f"Всего проверено: {scanned_count}\n"
            f"Пропущено (остановлены/ошибка): {skipped_count}\n\n"
            f"🎉 Контейнеров без сессий не найдено."
        )
        return

    report = f"⚠️ <b>Найдено {len(empty_containers)} контейнеров БЕЗ сессий!</b>\n"
    report += f"<i>(Проверено: {scanned_count}, Пропущено: {skipped_count})</i>\n\n"

    if len(empty_containers) > 10:
        full_report = "ID | Name | Server | User | Tariff | Days Left\n"
        full_report += "-" * 50 + "\n"
        for c in empty_containers:
            full_report += f"{c['id']} | {c['name']} | {c['server']} | {c['user_id']} | {c['tariff']} | {c['days_left']}\n"

        file = BufferedInputFile(full_report.encode('utf-8'), filename="empty_sessions.txt")
        await message.answer_document(file, caption=f"⚠️ <b>Отчет слишком большой ({len(empty_containers)} шт).</b>\nСм. файл.")

        report += "<i>(Полный список в файле выше)</i>\n\n"
    else:
        for c in empty_containers:
            report += (
                f"📦 <b>{c['name']}</b> (ID: <code>{c['id']}</code>)\n"
                f"├ Сервер: {c['server']}\n"
                f"├ Юзер: <code>{c['user_id']}</code>\n"
                f"├ Тариф: {c['tariff']}\n"
                f"└ Осталось: {c['days_left']} дн.\n\n"
            )

    report += "❓ <b>Что делаем?</b>"

    builder = InlineKeyboardBuilder()
    builder.button(text=f"🗑️ Удалить все ({len(empty_containers)})", callback_data="admin_delete_sessions_confirm")
    builder.button(text="❌ Отмена", callback_data="cancel_admin_action")

    await state.set_state(AdminSessionScanState.confirming_delete)
    await state.update_data(empty_containers=empty_containers)

    await status_msg.edit_text(report, reply_markup=builder.as_markup())


@router.callback_query(F.data == "admin_scan_sessions")
async def scan_sessions_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Запускаю сканирование")
    await cmd_scan_sessions(callback.message, state)

@router.callback_query(AdminSessionScanState.confirming_delete, F.data == "admin_delete_sessions_confirm")
async def confirm_deletion(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    empty_containers = data.get('empty_containers', [])

    if not empty_containers:
        await callback.answer("Список пуст или устарел.", show_alert=True)
        return

    await callback.message.edit_text("⏳ <b>Начинаю удаление пустых контейнеров...</b>")

    deleted_count = 0
    errors_count = 0

    for c in empty_containers:
        try:
            await dm.delete_container(c['server_id'], c['name'])
            await db.delete_user_container(c['id'])
            deleted_count += 1
        except Exception as e:
            logging.error(f"Ошибка при удалении пустого контейнера {c['id']}: {e}")
            errors_count += 1
        await asyncio.sleep(0.1)

    await log_action(bot, callback.from_user, f"удалил {deleted_count} контейнеров без сессий (ошибок: {errors_count})")

    await callback.message.edit_text(
        f"✅ <b>Очистка завершена!</b>\n\n"
        f"🗑️ Удалено: {deleted_count}\n"
        f"⚠️ Ошибок: {errors_count}"
    )
    await state.clear()
