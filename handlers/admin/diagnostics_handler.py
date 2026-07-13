import os
import logging
import asyncssh
from datetime import datetime
from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.types import BufferedInputFile

import database as db
from config import BOT_VERSION, SERVERS, SERVER_REPORT_TOPIC_ID, LOG_CHAT_ID, SERVER_REPORT_CHAT_ID
from utils import bot_state 
from lexicon import LEXICON
from utils.filters import IsAdmin
from roles import UserRole
from utils.server_status_graph import generate_server_status_image
from utils.cache import redis_client 
from utils.ui_utils import safe_edit_text, safe_edit_caption, safe_callback_answer

router = Router()

def format_uptime(start_time):
    if start_time is None: return "Неизвестно"
    uptime = datetime.now() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days} д.")
    if hours > 0: parts.append(f"{hours} ч.")
    if minutes > 0: parts.append(f"{minutes} м.")
    if seconds > 0 or not parts: parts.append(f"{seconds} с.")
    return " ".join(parts)

@router.message(Command("report"), IsAdmin(min_level=UserRole.ADMIN))
async def manual_server_report(message: types.Message, bot: Bot):
    from utils.jobs import update_server_statuses_cache

    if not SERVER_REPORT_CHAT_ID or not SERVER_REPORT_TOPIC_ID:
        await message.reply(f"❌ Не настроены ID чата отчетов ({SERVER_REPORT_CHAT_ID}) или топика ({SERVER_REPORT_TOPIC_ID}).")
        return

    status_msg = await message.reply("⏳ <b>Запуск диагностики...</b>")

    try:
        await safe_edit_text(status_msg, "🔄 <b>Опрашиваю серверы (SSH)...</b>\n<i>Это может занять время...</i>", parse_mode="HTML")
        await update_server_statuses_cache()

        statuses = bot_state.server_statuses_cache
        if not statuses:
            await safe_edit_text(status_msg, "⚠️ <b>Ошибка:</b> Не удалось получить данные от серверов (кэш пуст).")
            return

        await safe_edit_text(status_msg, "🎨 <b>Генерация графического отчета...</b>", parse_mode="HTML")

        image_bytes = await asyncio.to_thread(generate_server_status_image, statuses)
        photo_file = BufferedInputFile(image_bytes.read(), filename="server_status_manual.png")

        caption = (
            f"📊 <b>Ручной отчет по состоянию системы</b>\n"
            f"🕒 <code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n"
            f"👤 Запросил: {message.from_user.full_name}"
        )

        await safe_edit_text(status_msg, "📨 <b>Отправляю в топик мониторинга...</b>", parse_mode="HTML")

        sent_message = await bot.send_photo(
            chat_id=SERVER_REPORT_CHAT_ID,
            message_thread_id=SERVER_REPORT_TOPIC_ID,
            photo=photo_file,
            caption=caption,
            parse_mode="HTML"
        )

        chat_link_id = str(SERVER_REPORT_CHAT_ID).replace("-100", "")
        msg_link = f"https://t.me/c/{chat_link_id}/{SERVER_REPORT_TOPIC_ID}/{sent_message.message_id}"

        await safe_edit_text(
            status_msg,
            f"✅ <b>Графический отчет успешно отправлен!</b>\n"
            f"<a href='{msg_link}'>Перейти к сообщению</a>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        logging.error(f"Ошибка при ручном запуске отчета: {e}", exc_info=True)
        await safe_edit_text(status_msg, f"❌ <b>Критическая ошибка:</b>\n<pre>{e}</pre>", parse_mode="HTML")

@router.callback_query(F.data == "admin_diagnostics", IsAdmin(min_level=UserRole.ADMIN))
async def show_diagnostics(callback: types.CallbackQuery, state: FSMContext, scheduler: AsyncIOScheduler):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    version = BOT_VERSION
    uptime = format_uptime(bot_state.bot_start_time)

    scheduler_jobs_count = len(scheduler.get_jobs()) if scheduler else "Н/Д"

    db_size = await db.core.get_db_size()

    redis_mem = "N/A"
    try:
        info = await redis_client.info(section='memory')
        redis_mem = info.get('used_memory_human', 'N/A')
    except Exception as e:
        logging.error(f"Redis info error: {e}")

    total_users, active_containers = await asyncio.gather(
        db.count_all_users(),
        db.count_active_containers()
    )

    diag_text = (
        "<b>⚙️ Диагностика и состояние бота</b>\n\n"
        f"<b>Версия:</b> <code>{version}</code>\n"
        f"<b>Время работы (Uptime):</b> {uptime}\n\n"
        f"<b>База данных (PostgreSQL):</b>\n"
        f"  - Размер: {db_size}\n\n"
        f"<b>Кэш (Redis):</b>\n"
        f"  - Память: {redis_mem}\n\n"
        f"<b>Статистика:</b>\n"
        f"  - Всего пользователей: {total_users}\n"
        f"  - Активных контейнеров: {active_containers}\n\n"
        f"<b>Планировщик (APScheduler):</b>\n"
        f"  - Активных задач: {scheduler_jobs_count}"
    )

    await safe_edit_caption(
        callback.message,
        caption=diag_text,
        reply_markup=callback.message.reply_markup
    )
    await safe_callback_answer(callback, "Диагностика обновлена")

@router.message(Command("test_ssh"), IsAdmin(min_level=UserRole.CO_OWNER))
async def test_ssh_connection(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.reply("<b>Использование:</b> <code>/test_ssh <server_id></code>\n"
                            "Например: <code>/test_ssh de-1</code>")
        return

    server_id = args[1]
    if server_id not in SERVERS:
        await message.reply(f"❌ Сервер с ID '<code>{server_id}</code>' не найден в конфиге.")
        return

    server_config = SERVERS[server_id]
    await message.reply(f"⏳ Тестирую SSH-соединение с <b>{server_config['name']}</b> ({server_config['ip']})...")

    try:
        connect_options = {
            'host': server_config['ip'],
            'username': server_config['user'],
            'known_hosts': None
        }
        if server_config.get('password'):
            connect_options['password'] = server_config['password']
        elif server_config.get('client_keys'):
            connect_options['client_keys'] = server_config['client_keys']

        async with asyncssh.connect(**connect_options) as conn:
            result = await conn.run('whoami', check=True)
            user = result.stdout.strip()
            await message.answer(f"✅ <b>Успех!</b>\n"
                                 f"Подключение к <b>{server_id}</b> установлено.\n"
                                 f"Команда <code>whoami</code> выполнена от имени пользователя: <code>{user}</code>")

    except Exception as e:
        logging.error(f"Ошибка теста SSH для {server_id}: {e}", exc_info=True)
        await message.answer(f"❌ <b>Ошибка подключения к {server_id}!</b>\n\n"
                             f"<b>Тип ошибки:</b> <code>{type(e).__name__}</code>\n"
                             f"<b>Сообщение:</b> <code>{e}</code>\n\n"
                             f"Проверьте IP, логин, пароль и доступность сервера.")

@router.message(Command("backup"), IsAdmin(min_level=UserRole.CO_OWNER))
async def force_backup_command(message: types.Message, bot: Bot):
    from utils.jobs import send_db_backup

    await message.reply("⏳ Запускаю создание бэкапа базы данных...")
    try:
        await send_db_backup(bot)
        await message.answer("✅ Процесс бэкапа завершен. Проверьте лог-чат.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при запуске бэкапа: {e}")


@router.callback_query(F.data == "admin_force_backup", IsAdmin(min_level=UserRole.CO_OWNER))
async def force_backup_callback(callback: types.CallbackQuery, bot: Bot):
    await callback.answer("Запускаю резервное копирование")
    await force_backup_command(callback.message, bot)

@router.message(Command("zombie"), IsAdmin(min_level=UserRole.CO_OWNER))
async def force_zombie_cleaner(message: types.Message, bot: Bot):
    from utils.jobs import clean_zombies_globally

    """Принудительный запуск Zombie Cleaner."""
    await message.reply(
        "🧟 <b>Запускаю протокол 'Некромант'...</b>\n\n"
        "Поиск и перезагрузка зависших контейнеров (PIDs > 200)."
    )
    try:
        await clean_zombies_globally(bot)
        await message.answer("✅ <b>Зачистка завершена.</b>\nЕсли были ошибки, они отправлены в канал логов.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при запуске: {e}")


@router.callback_query(F.data == "admin_force_zombie", IsAdmin(min_level=UserRole.CO_OWNER))
async def force_zombie_cleaner_callback(callback: types.CallbackQuery, bot: Bot):
    await callback.answer("Запускаю проверку контейнеров")
    await force_zombie_cleaner(callback.message, bot)
