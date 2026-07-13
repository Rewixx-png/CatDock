import asyncio
import logging
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile

from utils.filters import IsAdmin
from roles import UserRole
from config import SERVERS, IMAGES
from utils.image_updater import update_docker_image_from_git, GIT_REPOS
from states.user_states import ImageUpdateState
from keyboards.admin import get_server_for_update_keyboard
from keyboards.common_keyboards import get_simple_confirmation_keyboard
from lexicon import LEXICON
import database as db
from utils.ssh_runner import run_command_on_server
from utils.ui_utils import safe_edit_caption

router = Router()
router.callback_query.filter(IsAdmin(min_level=UserRole.CO_OWNER))

async def _perform_update(bot: Bot, status_message: types.Message, server_id_to_update: str):
    update_results = []

    async def progress_callback(status_text: str):
        try:
            await status_message.edit_text(f"⏳ {status_text}", parse_mode="HTML")
        except TelegramBadRequest:
            pass

    server_info = SERVERS.get(server_id_to_update)
    if not server_info:
        await status_message.edit_text(f"❌ Ошибка: Сервер с ID '{server_id_to_update}' не найден в конфигурации.")
        return

    server_name = server_info['name']

    try:

        for image_id in GIT_REPOS.keys():
            image_name_display = IMAGES[image_id]['name']

            await status_message.edit_text(f"🚀 Начинаю обновление образа <b>{image_name_display}</b> на сервере <b>{server_name}</b>...")

            success, result_message = await update_docker_image_from_git(
                server_id_to_update, 
                image_id, 
                progress_callback
            )

            status_icon = "✅" if success else "❌"
            update_results.append(f"{status_icon} <b>{image_name_display}:</b>\n{result_message}\n")
            await asyncio.sleep(2)

        await progress_callback(f"Очищаю неиспользуемые Docker-образы на сервере <b>{server_name}</b>...")
        prune_result = await run_command_on_server(server_id_to_update, "docker image prune -f", timeout=60)
        prune_output = prune_result.stdout.strip() if prune_result.stdout else "Нет вывода."
        update_results.append(f"🧹 <b>Очистка образов:</b>\n{prune_output}")

    except Exception as e:
        logging.critical(f"Критическая ошибка на этапе обновления образов для {server_id_to_update}: {e}", exc_info=True)
        error_text = f"❌ <b>Произошла критическая ошибка:</b>\n<pre><code>{e}</code></pre>"
        update_results.append(error_text)

    final_text = f"🏁 <b>Обновление на сервере «{server_name}» завершено!</b>\n\n<b>Итоги:</b>\n\n" + "\n".join(update_results)

    telegram_limit = 4096

    try:
        if len(final_text) > telegram_limit:
            logging.warning("Итоговый отчет об обновлении слишком длинный. Отправляю файлом.")

            await status_message.edit_text("✅ Обновление завершено. Отчет слишком длинный, формирую и отправляю файл...")

            report_file = BufferedInputFile(
                final_text.encode('utf-8'),
                filename=f"update_report_{server_id_to_update}.txt"
            )

            await bot.send_document(
                chat_id=status_message.chat.id,
                document=report_file,
                caption=f"🏁 <b>Итоговый отчет об обновлении на «{server_name}»</b>"
            )

            await status_message.delete()
        else:
            await status_message.edit_text(final_text, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Непредвиденная ошибка при отправке итогового отчета: {e}", exc_info=True)
        try:
            await status_message.answer(f"❌ Произошла ошибка при отображении итогового отчета: {e}")
        except Exception:
            pass

@router.callback_query(F.data == "admin_update_images")
async def select_server_for_update_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await safe_edit_caption(
        callback.message,
        caption=lex.get('image_update_select_server', "Выберите сервер для обновления образов:"),
        reply_markup=get_server_for_update_keyboard(language_code)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_server_for_update:"))
async def confirm_server_update_handler(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]
    server_name = SERVERS.get(server_id, {}).get('name', 'Неизвестный сервер')
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await state.set_state(ImageUpdateState.confirming_update)
    await state.update_data(server_id=server_id)

    await safe_edit_caption(
        callback.message,
        caption=lex.get('image_update_confirm', "Вы уверены, что хотите обновить все образы на сервере <b>{server_name}</b>? Это может занять несколько минут.").format(server_name=server_name),
        reply_markup=get_simple_confirmation_keyboard(
            language_code,
            yes_callback="confirm_server_image_update",
            no_callback="admin_update_images"
        )
    )
    await callback.answer()

@router.callback_query(StateFilter(ImageUpdateState.confirming_update), F.data == "confirm_server_image_update")
async def process_server_update_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    server_id = data.get('server_id')
    await state.clear()

    if not server_id:
        await callback.answer("❌ Ошибка состояния. Пожалуйста, попробуйте снова.", show_alert=True)
        return

    await callback.answer("Запускаю процесс обновления...", show_alert=True)

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    status_message = await bot.send_message(
        chat_id=callback.from_user.id,
        text=f"🚀 Начинаю процесс обновления образов на сервере <b>{SERVERS[server_id]['name']}</b>..."
    )

    asyncio.create_task(_perform_update(bot, status_message, server_id))
