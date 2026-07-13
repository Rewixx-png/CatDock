from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import WEB_APP_URL
from lexicon import LEXICON

router = Router()

@router.callback_query(F.data.startswith("get_logs_start:"))
async def get_logs_handler(callback: types.CallbackQuery, state: FSMContext):
    container_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    container = await db.get_container_for_actor(container_id, user_id)
    if not container:
        await callback.answer("❌ Контейнер не найден.", show_alert=True)
        return

    token = await db.create_log_token(container_id)

    if not token:
        await callback.answer("❌ Ошибка создания ссылки на логи.", show_alert=True)
        return

    base_url = WEB_APP_URL.rstrip('/')
    logs_url = f"{base_url}/terminal.html?token={token}&container_id={container_id}"

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🖥️ Открыть CatDock Terminal", url=logs_url))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data=f"manage_bot:{container_id}"))

    text = (
        "📋 <b>Просмотр логов</b>\n\n"
        "Сгенерирована безопасная ссылка для управления UserBot в браузере.\n"
        "• Интерактивный терминал и логи\n"
        "• Статус и перезапуск\n"
        "• Загрузка сессии и выбор образа\n"
        "• Ссылка активна <b>30 минут</b>"
    )

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()
