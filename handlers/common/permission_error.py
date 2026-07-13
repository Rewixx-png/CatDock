from aiogram import Router, types
from aiogram.filters import Command

import database as db
from lexicon import LEXICON

router = Router()

PROTECTED_COMMANDS = [
    "ban", "mute", "kick", "warn", "unwarn", "unban", "unmute",
    "rban", "rmute", "rkick", "rwarn",
    "raidcheck", "rcheck", "check",

    "cont", "give", "get",

    "admin", "unadmin",
    "rinfo", "info", "инфо",
    "unblock",
    "report", "session",
    "purge_chat", "checkerbot",

    "restart", "fixloop", "checkcont", "zombie", 
    "test_ssh", "backup", "orphans", "htop", "drestart", "dstats",
    "migration", "stats"
]

@router.message(Command(*PROTECTED_COMMANDS))
async def permission_denied_handler(message: types.Message):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])

    error_text = lex.get('error_insufficient_permissions', "⛔️ <b>Доступ запрещен.</b>\nУ вас недостаточно прав для выполнения этой команды.")

    await message.reply(error_text)
