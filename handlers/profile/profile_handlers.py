from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import logging
import asyncio
from datetime import datetime

import database as db
from config import REFERRAL_PERCENTAGE
from keyboards import get_profile_keyboard, get_referral_menu_keyboard, get_simple_confirmation_keyboard
from lexicon import LEXICON
from roles import UserRole, ROLE_NAMES
from ..common.menu_utils import set_loading_state
from utils.ui_utils import safe_edit_caption, safe_edit_text, safe_callback_answer, safe_delete_message

router = Router()

def create_progress_bar(current, total, length=10):
    if total == 0: total = 1 
    percent = min(1.0, current / total)
    filled_length = int(length * percent)

    bar = "▰" * filled_length + "▱" * (length - filled_length)
    return bar

@router.callback_query(F.data == "profile")
async def show_profile_menu(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await safe_callback_answer(callback)
    await set_loading_state(callback, "Профиль")
    await state.clear()

    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])

    user_profile, settings, containers, user_role_enum = await asyncio.gather(
        db.get_user_profile(user_id, use_cache=False),
        db.get_user_settings(user_id),
        db.get_user_containers(user_id),
        db.get_user_role(user_id)
    )

    if user_profile:
        referrer_info = "—"
        if user_profile.get('referrer_id'):
            try:
                ref_user = await db.get_user_profile(user_profile['referrer_id'])
                if ref_user:
                    ref_name = ref_user.get('username') or ref_user.get('first_name') or str(user_profile['referrer_id'])
                    referrer_info = f"@{ref_name}" if ref_user.get('username') else ref_name
            except Exception:
                pass

        reg_date_str = str(user_profile.get('reg_date', '—'))
        try:
             reg_date_obj = datetime.fromisoformat(reg_date_str.split('.')[0])
             reg_date_str = reg_date_obj.strftime("%d.%m.%Y")
        except ValueError:
             pass

        user_profile['referrer_display'] = referrer_info
        user_profile['reg_date_display'] = reg_date_str
        user_profile['lang_display'] = language_code.upper()

        level = user_profile.get('level') or 1
        xp = user_profile.get('xp') or 0

        next_level_xp = int(100 * (level ** 1.5))

        progress_bar = create_progress_bar(xp, next_level_xp, length=8)
        progress_percent = int((xp / next_level_xp) * 100)

        user_profile['level'] = level
        user_profile['xp'] = xp
        user_profile['next_level_xp'] = next_level_xp
        user_profile['progress_bar'] = progress_bar
        user_profile['progress_percent'] = progress_percent
        user_profile['next_level'] = level + 1

        user_profile['userbots_count'] = len(containers)
        user_profile['role'] = ROLE_NAMES.get(user_role_enum, "Неизвестная роль")
        user_profile['username'] = user_profile.get('username') or '—'

        try:
            profile_text = lex.get('profile_text', 'profile_text').format(**user_profile)
        except KeyError as e:
            logging.error(f"Ошибка форматирования профиля: отсутствует ключ {e}")
            profile_text = "Ошибка отображения профиля. Пожалуйста, сообщите администратору."

        bonuses_text = ""
        has_bonuses = False

        discount = user_profile.get('active_discount_percent', 0)
        if discount > 0:
            code = user_profile.get('active_discount_code') or 'AUTO'
            bonuses_text += lex.get('bonus_row_discount', '\n📉 Скидка: <b>{percent}%</b>').format(percent=discount, code=code)
            has_bonuses = True

        dep_bonus = user_profile.get('active_deposit_bonus_percent', 0)
        if dep_bonus > 0:
            code = user_profile.get('active_deposit_bonus_code') or 'AUTO'
            bonuses_text += lex.get('bonus_row_deposit', '\n💰 Депозит: <b>+{percent}%</b>').format(percent=dep_bonus, code=code)
            has_bonuses = True

        if user_profile.get('has_free_container_promo', False):
            code = user_profile.get('free_container_promo_code') or 'AUTO'
            bonuses_text += lex.get('bonus_row_free_cont', '\n📦 Free Container').format(code=code)
            has_bonuses = True

        if has_bonuses:
            profile_text += lex.get('bonuses_header', '\n\n<b>✨ Активные баффы:</b>') + bonuses_text

    else:
        profile_text = lex.get('error_profile_not_found')

    if callback.message:
        try:
            if callback.message.photo:
                try:
                    await callback.message.edit_text(text=profile_text, reply_markup=get_profile_keyboard(language_code))
                except TelegramBadRequest as e:
                    if "message is not modified" not in str(e):
                         raise e
            else:
                await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
                await bot.send_message(chat_id=user_id, text=profile_text, reply_markup=get_profile_keyboard(language_code))
        except Exception as e:
            logging.warning(f"Profile refresh fallback: {e}")
            try: await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
            except: pass
            await bot.send_message(chat_id=user_id, text=profile_text, reply_markup=get_profile_keyboard(language_code))

@router.callback_query(F.data == "ref_system")
async def show_referral_menu(callback: types.CallbackQuery, bot: Bot):
    await safe_callback_answer(callback)
    await set_loading_state(callback, "Реферальная система")

    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])

    user_profile = await db.get_user_profile(user_id)
    has_advanced = user_profile.get('has_advanced_referral', 0)

    current_percent = REFERRAL_PERCENTAGE

    bot_info = await bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    stats = await db.get_referral_stats(user_id)

    if stats['referrer_name']:
        referrer_info = lex.get('referrer_info_who', 'referrer_info_who').format(referrer_name=stats['referrer_name'])
    else:
        referrer_info = lex.get('referrer_info_self', 'referrer_info_self')

    text = lex.get('referral_text', 'referral_text').format(
        ref_percent=int(current_percent * 100),
        ref_link=referral_link,
        ref_count=stats['count'],
        referrer_info=referrer_info
    )
    if not has_advanced:
        text += "\n\n" + lex.get('referral_upgrade_promo', "Хотите получать больше? Улучшите свою реферальную систему до 40% навсегда!")

    await safe_edit_caption(
        callback.message,
        caption=text, 
        reply_markup=get_referral_menu_keyboard(has_advanced, language_code)
    )

@router.callback_query(F.data == "upgrade_referral_confirm")
async def confirm_upgrade_referral(callback: types.CallbackQuery):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    text = lex.get('referral_confirm_upgrade_text').format(price=75)
    markup = get_simple_confirmation_keyboard(language_code, "upgrade_referral_buy", "ref_system")

    await safe_edit_caption(callback.message, caption=text, reply_markup=markup)
    await safe_callback_answer(callback)

@router.callback_query(F.data == "upgrade_referral_buy")
async def buy_advanced_referral(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    user_balance = await db.get_user_balance(user_id)

    if user_balance < 75.0:
        await safe_callback_answer(callback, lex.get('insufficient_funds_for_upgrade'), show_alert=True)
        return

    await db.update_user_balance(user_id, -75.0)
    await db.set_advanced_referral(user_id)

    logging.info(f"Пользователь {user_id} купил продвинутую реферальную систему.")
    await safe_callback_answer(callback, lex.get('referral_upgrade_success'), show_alert=True)

    await show_referral_menu(callback, bot)

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_profile_menu(callback, state, callback.bot)
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    await safe_callback_answer(callback, LEXICON[language_code]['action_canceled'])
