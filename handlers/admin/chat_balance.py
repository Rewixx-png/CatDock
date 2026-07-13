import logging
import html
from aiogram import F, Router, Bot, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db
from utils.filters import IsAdmin
from roles import UserRole
from lexicon import LEXICON
from utils.action_logger import log_action

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

@router.message(Command("get", "give", "add", prefix="/!"), F.reply_to_message)
async def cmd_manage_resources(message: types.Message, bot: Bot):
    if not message.reply_to_message.from_user or message.reply_to_message.from_user.is_bot:
        await message.reply("Не могу определить пользователя из реплая или это бот.")
        return

    command_text = message.text.lower()
    command_parts = message.text.split()

    if len(command_parts) != 3:
        await message.reply(
            "<b>Ошибка.</b> Неверный формат команды.\n"
            "Пример:\n"
            "<code>/give money 100</code> (Баланс)\n"
            "<code>/give rmoney 50</code> (Реф. баланс)\n"
            "<code>/give check 2</code> (Игровые чеки)"
        )
        return

    is_give = command_text.startswith(("/give", "!give", "/add", "!add"))

    resource_type = command_parts[1].lower()

    try:
        value = float(command_parts[2])
    except (ValueError, TypeError):
        await message.reply("<b>Ошибка.</b> Указано неверное число.\nПример: <code>100</code>")
        return

    if not is_give and value > 0:
        value = -value

    target_user = message.reply_to_message.from_user
    admin_user = message.from_user

    safe_target_name = html.escape(target_user.full_name)

    try:
        if resource_type in ["money", "balance"]:
            await db.admin_update_user_balance(target_user.id, value)
            updated_profile = await db.get_user_profile(target_user.id)
            new_balance = updated_profile.get('balance', 0.0)

            action_word = "пополнил" if value >= 0 else "списал"
            log_text = f"{action_word} основной баланс на {abs(value):.2f} RUB. Новый баланс: {new_balance:.2f} RUB"
            await log_action(bot, admin_user, log_text, target_user)

            await message.reply(
                f"✅ Успешно! Основной баланс пользователя <b>{safe_target_name}</b> изменен на {value:+.2f} RUB.\n"
                f"Новый баланс: <b>{new_balance:.2f} RUB</b>."
            )
            try:
                await bot.send_message(target_user.id, f"💰 Администратор изменил ваш основной баланс на <b>{value:+.2f} RUB</b>.")
            except: pass

        elif resource_type in ["rmoney", "rbalance"]:
            await db.admin_update_user_ref_balance(target_user.id, value)
            updated_profile = await db.get_user_profile(target_user.id)
            new_ref_balance = updated_profile.get('ref_balance', 0.0)

            action_word = "пополнил" if value >= 0 else "списал"
            log_text = f"{action_word} реферальный баланс на {abs(value):.2f} RUB. Новый баланс: {new_ref_balance:.2f} RUB"
            await log_action(bot, admin_user, log_text, target_user)

            await message.reply(
                f"✅ Успешно! Реферальный баланс пользователя <b>{safe_target_name}</b> изменен на {value:+.2f} RUB.\n"
                f"Новый реф. баланс: <b>{new_ref_balance:.2f} RUB</b>."
            )

        elif resource_type in ["check", "checks"]:
            amount_int = int(value)
            await db.admin_update_user_checks(target_user.id, amount_int)
            updated_profile = await db.get_user_profile(target_user.id)
            new_checks = updated_profile.get('game_checks', 0)

            action_word = "выдал" if amount_int >= 0 else "забрал"
            log_text = f"{action_word} {abs(amount_int)} игровых чеков. Теперь чеков: {new_checks}"
            await log_action(bot, admin_user, log_text, target_user)

            await message.reply(
                f"✅ Успешно! Количество чеков пользователя <b>{safe_target_name}</b> изменено на {amount_int:+d}.\n"
                f"Всего чеков: <b>{new_checks}</b>."
            )
            try:
                msg = f"🎫 Администратор выдал вам <b>{amount_int}</b> игровых чеков!" if amount_int > 0 else f"🎫 Администратор списал <b>{abs(amount_int)}</b> игровых чеков."
                await bot.send_message(target_user.id, msg)
            except: pass

        else:
            await message.reply(f"<b>Ошибка.</b> Неизвестный тип ресурса: '<code>{resource_type}</code>'.\nДоступны: `money`, `rmoney`, `check`.")

    except Exception as e:
        logging.error(f"Ошибка при изменении ресурсов через чат: {e}", exc_info=True)
        
        from config import LOG_CHAT_ID
        if LOG_CHAT_ID:
             try:
                 error_msg = html.escape(str(e))
                 await bot.send_message(LOG_CHAT_ID, f"❌ <b>CRITICAL ERROR in /give</b>\nUser: {safe_target_name}\nError: {error_msg}")
             except: pass
        
        await message.reply(f"❌ <b>Критическая ошибка!</b> Детали в логах.")

@router.message(Command("get", "give", "add", prefix="/!"))
async def cmd_manage_no_reply(message: types.Message):
    await message.reply("<b>Ошибка.</b> Используйте эту команду в ответ на сообщение пользователя.")
