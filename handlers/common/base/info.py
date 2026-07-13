from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime
import asyncio

import database as db
from lexicon import LEXICON
from roles import UserRole, ROLE_NAMES
from config import WEB_APP_URL

router = Router()

HELP_CATEGORIES = {
    'user': {
        'min_level': UserRole.PARTICIPANT,
        'button_text': "👤 Пользователь",
        'content': (
            "👤 <b>ПОЛЬЗОВАТЕЛЬСКОЕ:</b>\n\n"
            "🔹 <code>/start</code> — Главное меню / Перезагрузка\n"
            "🔹 <code>/top</code> — Доска почета\n"
            "🔹 <code>/status</code> — Состояние серверов\n"
            "🔹 <code>/ping</code> — Проверка скорости отклика\n"
            "🔹 <code>/login</code> — Ссылка на веб-панель\n\n"
            "ℹ️ <i>Все остальные функции доступны через кнопки меню.</i>"
        )
    },
    'admin': {
        'min_level': UserRole.ADMIN,
        'button_text': "🛡 Администратор",
        'content': (
            "🛡 <b>АДМИНИСТРАТОР:</b>\n\n"
            "🔸 <code>/admin</code> — Панель управления\n"
            "🔸 <code>/stats</code> — Аналитика ресурсов (графики)\n"
            "🔸 <code>/ban [время] [причина]</code> — Бан (реплай)\n"
            "🔸 <code>/unban</code> — Разбан (реплай)\n"
            "🔸 <code>/mute [время] [причина]</code> — Мут (реплай)\n"
            "🔸 <code>/unmute</code> — Размут (реплай)\n"
            "🔸 <code>/kick</code> — Кикнуть участника\n"
            "🔸 <code>/warn</code> / <code>/unwarn</code> — Варны\n"
            "🔸 <code>/raidcheck</code> — Проверить юзера в БД (реплай)\n"
            "🔸 <code>/cont check [ID]</code> — Инспекция контейнера\n"
            "🔸 <code>/cont delete [ID]</code> — <b>Удалить</b> контейнер\n"
            "🔸 <code>/cont logs [ID]</code> — Получить логи\n"
            "🔸 <code>/cont [start|stop|block] [ID]</code> — Действия"
        )
    },
    'senior': {
        'min_level': UserRole.SENIOR_ADMIN,
        'button_text': "👑 Руководство",
        'content': (
            "👑 <b>ВЫСШЕЕ РУКОВОДСТВО:</b>\n\n"
            "💠 <code>/give cont</code> — Выдать контейнер (реплай)\n"
            "💠 <code>/give money [сумма]</code> — Выдать баланс\n"
            "💠 <code>/give rmoney [сумма]</code> — Выдать реф. баланс\n"
            "💠 <code>/give check [кол-во]</code> — Выдать игровые чеки\n"
            "💠 <code>/admin [lvl] [prefix]</code> — Назначить админа чата\n"
            "💠 <code>/unadmin</code> — Снять админа чата\n"
            "💠 <code>/rinfo</code> — Полное досье на юзера (реплай)\n"
            "💠 <code>/report</code> — Принудительный отчет по серверам\n"
            "💠 <code>/session</code> — Поиск контейнеров без сессий\n"
            "💠 <code>/purge_chat</code> — Инструкция по чистке чата"
        )
    },
    'system': {
        'min_level': UserRole.CO_OWNER,
        'button_text': "⚡️ Системное Ядро",
        'content': (
            "⚡️ <b>СИСТЕМНОЕ ЯДРО:</b>\n\n"
            "☢️ <code>/migration</code> — Миграция с оффлайн нод\n"
            "☢️ <code>/htop</code> — Мониторинг ресурсов (GUI)\n"
            "☢️ <code>/dstats</code> — Docker Stats (GUI)\n"
            "☢️ <code>/drestart</code> — Плавный рестарт ноды\n"
            "☢️ <code>/restart</code> — Полный перезапуск бота\n"
            "☢️ <code>/fixloop</code> — Поиск и лечение BootLoop\n"
            "☢️ <code>/checkcont</code> — Поиск контейнеров-призраков (Docker vs DB)\n"
            "☢️ <code>/orphans</code> — Поиск записей в БД без серверов\n"
            "☢️ <code>/zombie</code> — Зачистка зомби-процессов\n"
            "☢️ <code>/test_ssh [server]</code> — Тест коннекта к ноде\n"
            "☢️ <code>/backup</code> — Бэкап базы данных"
        )
    }
}

@router.message(Command("status"))
async def cmd_status(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🌍 Открыть страницу статуса", url="https://catdock.catdock.io/status"))

    await message.answer(
        "📊 Чтобы проверить актуальное состояние серверов, перейдите на нашу страницу статуса:",
        reply_markup=builder.as_markup()
    )

@router.message(Command("ping"))
async def cmd_ping(message: types.Message):
    start_time = datetime.now()
    sent_message = await message.answer("🏓 <b>Понг!</b>")
    end_time = datetime.now()
    delta = end_time - start_time
    latency_ms = delta.total_seconds() * 1000
    await sent_message.edit_text(f"🏓 <b>Понг!</b>\n📡 Задержка API: <code>{latency_ms:.2f} мс</code>")

async def send_help_menu(message_or_callback: types.Message | types.CallbackQuery):
    user_id = message_or_callback.from_user.id
    user_role = await db.get_user_role(user_id) or UserRole.PARTICIPANT
    role_name = ROLE_NAMES.get(user_role, 'Пользователь')

    header_text = (
        f"🛰 <b>Командный центр CatDock</b>\n"
        f"👤 <b>Ваш допуск:</b> <code>{role_name}</code>\n\n"
        f"Выберите категорию команд:"
    )

    builder = InlineKeyboardBuilder()

    for key, data in HELP_CATEGORIES.items():
        if user_role >= data['min_level']:
            builder.row(types.InlineKeyboardButton(
                text=data['button_text'], 
                callback_data=f"help_cat:{key}"
            ))

    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(header_text, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            pass
    else:
        await message_or_callback.answer(header_text, reply_markup=builder.as_markup())

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await send_help_menu(message)

@router.callback_query(F.data.startswith("help_cat:"))
async def help_category_handler(callback: types.CallbackQuery):
    category_key = callback.data.split(":")[1]
    user_id = callback.from_user.id
    user_role = await db.get_user_role(user_id) or UserRole.PARTICIPANT

    category_data = HELP_CATEGORIES.get(category_key)

    if not category_data:
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    if user_role < category_data['min_level']:
        await callback.answer("⛔️ Недостаточно прав для просмотра этого раздела.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="help_main"))

    try:
        await callback.message.edit_text(
            category_data['content'],
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    await callback.answer()

@router.callback_query(F.data == "help_main")
async def help_back_handler(callback: types.CallbackQuery):
    await send_help_menu(callback)
    await callback.answer()

@router.message(F.chat.type == "private")
async def unhandled_text_message(message: types.Message):

    if message.text and message.text.startswith('/'):
        return

    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    await message.reply(
        LEXICON[language_code].get(
            'unhandled_message',
            "Я не понимаю эту команду. Пожалуйста, используйте кнопки меню или перезапустите бота командою /start."
        )
    )
