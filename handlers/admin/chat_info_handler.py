import logging
import asyncio
import html
from datetime import datetime, timedelta
from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hlink
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import INFO_CHAT_ID, SERVERS, IMAGES, TARIFFS
from utils.filters import IsAdmin
from keyboards.admin import get_rinfo_main_keyboard, get_rinfo_userbots_keyboard
from lexicon import LEXICON
from handlers.common.menu_utils import show_management_menu, format_seconds_to_dhms
from roles import UserRole, ROLE_NAMES
import utils.docker as dm

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.JUNIOR_ADMIN), F.chat.id == INFO_CHAT_ID)
router.callback_query.filter(IsAdmin(min_level=UserRole.JUNIOR_ADMIN), F.message.chat.id == INFO_CHAT_ID)

async def get_rinfo_text(target_user: types.User, language_code: str = 'ru') -> str:
    lex = LEXICON.get(language_code, LEXICON['ru'])

    user_profile, user_containers, ref_stats, user_role = await asyncio.gather(
        db.get_user_profile(target_user.id),
        db.get_user_containers(target_user.id),
        db.get_referral_stats(target_user.id),
        db.get_user_role(target_user.id)
    )

    if not user_profile:
        return lex.get('rinfo_user_not_in_db')

    safe_full_name = html.escape(target_user.full_name)
    safe_username = html.escape(target_user.username or 'N/A')

    user_link = hlink(safe_full_name, f'tg://user?id={target_user.id}')

    is_blocked = "🔴 ЗАБЛОКИРОВАН" if user_profile.get('is_blocked') else "🟢 Активен"
    used_free = "✅ Да" if user_profile.get('has_used_free_tariff') else "❌ Нет"
    role_name = ROLE_NAMES.get(user_role, str(user_role))

    level = user_profile.get('level', 1)
    xp = user_profile.get('xp', 0)

    referrer_name = ref_stats.get('referrer_name')
    safe_referrer = html.escape(referrer_name) if referrer_name else 'Нет'

    text = lex.get('rinfo_header')
    text += f"<b>👤 Пользователь:</b> {user_link}\n"
    text += f"<b>🆔 ID:</b> <code>{target_user.id}</code>\n"
    text += f"<b>📛 Username:</b> @{safe_username}\n"
    text += f"<b>🔑 Роль:</b> {role_name}\n"
    text += f"<b>🛡 Статус:</b> {is_blocked}\n"
    text += f"<b>⚠️ Варнов:</b> {user_profile.get('warn_count', 0)}/3\n"
    text += f"<b>⭐️ Уровень:</b> {level} ({xp} XP)\n"
    text += f"<b>🌐 Язык:</b> {user_profile.get('language_code', 'ru')}\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    text += f"<b>💰 Баланс:</b> {user_profile['balance']:.2f} RUB\n"
    text += f"<b>👥 Реф. баланс:</b> {user_profile['ref_balance']:.2f} RUB\n"
    text += f"<b>💎 RewCoins:</b> {user_profile.get('rewcoin_balance', 0)}\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    text += f"<b>🤖 Юзерботов:</b> {len(user_containers)}\n"
    text += f"<b>📅 Регистрация:</b> {user_profile['reg_date']}\n"
    text += f"<b>🎁 Использовал Free:</b> {used_free}\n"
    text += f"<b>📈 Рефералов:</b> {ref_stats['count']}\n"
    text += f"<b>🔗 Реферер:</b> {safe_referrer}"

    return text

@router.message(Command("rinfo", "info", "инфо", prefix="/!"), F.reply_to_message)
async def cmd_rinfo(message: types.Message, bot: Bot):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    target_user = message.reply_to_message.from_user

    text = await get_rinfo_text(target_user, language_code)
    keyboard = get_rinfo_main_keyboard(target_user.id, language_code)

    await bot.send_message(
        chat_id=message.chat.id,
        text=text,
        reply_markup=keyboard,
        message_thread_id=message.message_thread_id,
        reply_to_message_id=message.message_id,
        disable_web_page_preview=True
    )

@router.callback_query(F.data.startswith("rinfo_main:"))
async def back_to_rinfo_main(callback: types.CallbackQuery):
    target_user_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'

    user_profile_db = await db.get_user_profile(target_user_id)
    target_user = types.User(
        id=target_user_id, 
        is_bot=False, 
        first_name=user_profile_db.get('first_name', 'User'), 
        username=user_profile_db.get('username')
    )

    text = await get_rinfo_text(target_user, language_code)
    keyboard = get_rinfo_main_keyboard(target_user.id, language_code)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    except TelegramBadRequest as e:
        logging.warning(f"Не удалось отредактировать сообщение rinfo: {e}")
    await callback.answer()

@router.callback_query(F.data.startswith("rinfo_bots:"))
async def show_rinfo_userbots(callback: types.CallbackQuery):
    target_user_id = int(callback.data.split(":")[1])
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])

    target_user_profile = await db.get_user_profile(target_user_id)
    
    safe_target_name = html.escape(target_user_profile['first_name'])
    
    containers = await db.get_user_containers(target_user_id)

    if not containers:
        await callback.answer(lex.get('rinfo_no_userbots'), show_alert=True)
        return

    text_parts = [f"🤖 <b>Юзерботы пользователя {safe_target_name}:</b>\n"]

    for c in containers:
        server_name = SERVERS.get(c['server_id'], {}).get('name', c['server_id'])
        image_name = IMAGES.get(c['image_id'], {}).get('name', c['image_id'])
        tariff_name = TARIFFS.get(c['tariff_id'], {}).get('name', c['tariff_id'])

        seconds_left = c['remaining_seconds']
        
        if seconds_left > 3153600000: 
             expiry_str = "∞ (Вечно)"
        else:
            try:
                expiry_date = datetime.now() + timedelta(seconds=seconds_left)
                expiry_str = expiry_date.strftime("%d.%m.%Y %H:%M")
            except OverflowError:
                expiry_str = "∞ (Ошибка даты)"
            except Exception:
                expiry_str = "Ошибка"

        status = "❄️ FROZEN" if c.get('is_frozen') else "🟢 ACTIVE"

        safe_container_name = html.escape(c['container_name'])

        text_parts.append(
            f"📦 <b>{safe_container_name}</b> (ID: <code>{c['id']}</code>)\n"
            f"   ├ <b>Статус:</b> {status}\n"
            f"   ├ <b>Сервер:</b> {server_name}\n"
            f"   ├ <b>Образ:</b> {image_name}\n"
            f"   ├ <b>Тариф:</b> {tariff_name}\n"
            f"   └ <b>Истекает:</b> {expiry_str}\n"
        )

    text = "\n".join(text_parts)
    keyboard = get_rinfo_userbots_keyboard(target_user_id, language_code)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        logging.warning(f"Не удалось отредактировать сообщение rinfo_bots: {e}")
    await callback.answer()

@router.callback_query(F.data.contains(":rinfo_back:"))
async def manage_bot_from_chat_info(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(':')
    container_id = int(parts[1])
    target_user_id = int(parts[3])

    back_callback = f"rinfo_bots:{target_user_id}"

    await show_management_menu(
        event=callback,
        container_id=container_id,
        state=state,
        bot=callback.bot,
        is_admin_view=True,
        admin_back_callback=back_callback
    )
    await callback.answer()
