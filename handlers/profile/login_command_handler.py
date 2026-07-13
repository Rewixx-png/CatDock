from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import WEB_APP_URL
import database as db

router = Router()

@router.message(Command("login", "terminal"))
async def command_login_handler(message: types.Message, bot: Bot):
    try:
        await message.delete()
    except:
        pass

    containers = await db.get_user_containers(message.from_user.id)
    if not containers:
        await message.answer(
            "У вас пока нет UserBot. Создайте контейнер через раздел «Тарифы» в главном меню."
        )
        return

    builder = InlineKeyboardBuilder()
    for container in containers:
        token = await db.create_log_token(container['id'])
        if not token:
            continue
        terminal_url = (
            f"{WEB_APP_URL.rstrip('/')}/terminal.html"
            f"?token={token}&container_id={container['id']}"
        )
        builder.row(types.InlineKeyboardButton(
            text=f"🖥️ {container['container_name']}",
            url=terminal_url,
        ))

    if not builder.export():
        await message.answer("Не удалось создать временную ссылку терминала. Попробуйте позже.")
        return

    await message.answer(
        "Выберите UserBot. Ссылка на CatDock Terminal действует 30 минут.",
        reply_markup=builder.as_markup()
    )
