from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import WEB_APP_URL

router = Router()

@router.message(Command("login"))
async def command_login_handler(message: types.Message, bot: Bot):
    try:
        await message.delete()
    except:
        pass 

    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Войти в веб-панель", url=f"{WEB_APP_URL}/index.html")

    await message.answer(
        "Для входа в веб-панель, пожалуйста, перейдите по ссылке ниже и авторизуйтесь через Telegram.",
        reply_markup=builder.as_markup()
    )
