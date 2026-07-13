import asyncio
import logging
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from utils.filters import IsAdmin 
from keyboards.admin import get_cancel_admin_action_keyboard, get_yes_no_keyboard, get_broadcast_confirmation_keyboard
from states.user_states import BroadcastState
from roles import UserRole
from lexicon import LEXICON

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.SENIOR_ADMIN))

async def show_preview(message: types.Message, state: FSMContext, bot: Bot):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    data = await state.get_data()

    text = data.get('broadcast_text')
    photo_id = data.get('broadcast_photo_id')
    button_text = data.get('broadcast_button_text')
    button_url = data.get('broadcast_button_url')

    markup = None
    if button_text and button_url:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text=button_text, url=button_url))
        markup = builder.as_markup()

    await message.answer(lex.get('broadcast_confirmation_title'))
    await message.answer(lex.get('broadcast_preview_label'), parse_mode=None)

    try:
        if photo_id:
            preview_message = await bot.send_photo(chat_id=message.chat.id, photo=photo_id, caption=text, reply_markup=markup, parse_mode="HTML")
        else:
            preview_message = await bot.send_message(chat_id=message.chat.id, text=text, reply_markup=markup, disable_web_page_preview=True, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "BUTTON_URL_INVALID" in str(e) or "invalid" in str(e).lower():
            await message.answer(f"❌ <b>Ошибка в кнопке!</b>\nTelegram не принял URL: <code>{button_url}</code>\n\nПроверьте ссылку и введите её заново.")
            await message.answer(lex.get('broadcast_prompt_button_url'))
            await state.set_state(BroadcastState.waiting_for_button_url)
            return
        else:
            raise e

    await message.answer(lex.get('broadcast_preview_label'), parse_mode=None)

    confirmation_message = await message.answer("Подтверждаете рассылку?", reply_markup=get_broadcast_confirmation_keyboard(language_code))
    await state.update_data(
        preview_message_id=preview_message.message_id,
        confirmation_message_id=confirmation_message.message_id
    )
    await state.set_state(BroadcastState.confirming_broadcast)

@router.callback_query(F.data == "start_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    msg = await callback.message.answer(
        lex.get('broadcast_prompt_text'),
        reply_markup=get_cancel_admin_action_keyboard("admin_panel", language_code)
    )
    await state.set_state(BroadcastState.waiting_for_text)
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(BroadcastState.waiting_for_text)
async def process_broadcast_text(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await bot.delete_message(message.chat.id, data['prompt_message_id'])
        await message.delete()
    except TelegramBadRequest:
        pass

    await state.update_data(broadcast_text=message.text)

    msg = await message.answer(
        lex.get('broadcast_prompt_media_q'),
        reply_markup=get_yes_no_keyboard(language_code, 'broadcast_add_media', 'broadcast_skip_media')
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await state.set_state(BroadcastState.waiting_for_media_q)

@router.callback_query(BroadcastState.waiting_for_media_q, F.data == 'broadcast_add_media')
async def ask_for_media(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    await callback.message.edit_text(lex.get('broadcast_prompt_media_send'))
    await state.set_state(BroadcastState.waiting_for_media)
    await callback.answer()

@router.message(BroadcastState.waiting_for_media, F.photo)
async def process_broadcast_media(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await bot.delete_message(message.chat.id, data['prompt_message_id'])
        await message.delete()
    except TelegramBadRequest:
        pass

    await state.update_data(broadcast_photo_id=message.photo[-1].file_id)

    msg = await message.answer(
        lex.get('broadcast_prompt_button_q'),
        reply_markup=get_yes_no_keyboard(language_code, 'broadcast_add_button', 'broadcast_skip_button')
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await state.set_state(BroadcastState.waiting_for_button_q)

@router.callback_query(BroadcastState.waiting_for_media_q, F.data == 'broadcast_skip_media')
@router.callback_query(BroadcastState.waiting_for_button_q, F.data == 'broadcast_skip_button')
async def skip_to_confirmation(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await show_preview(callback.message, state, bot)
    await callback.answer()

@router.callback_query(BroadcastState.waiting_for_button_q, F.data == 'broadcast_add_button')
async def ask_for_button_text(callback: types.CallbackQuery, state: FSMContext):
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    await callback.message.edit_text(lex.get('broadcast_prompt_button_text'))
    await state.set_state(BroadcastState.waiting_for_button_text)
    await callback.answer()

@router.message(BroadcastState.waiting_for_button_text)
async def process_button_text(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await bot.delete_message(message.chat.id, data['prompt_message_id'])
        await message.delete()
    except TelegramBadRequest:
        pass

    await state.update_data(broadcast_button_text=message.text)
    msg = await message.answer(lex.get('broadcast_prompt_button_url'))
    await state.update_data(prompt_message_id=msg.message_id)
    await state.set_state(BroadcastState.waiting_for_button_url)

@router.message(BroadcastState.waiting_for_button_url)
async def process_button_url(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    if not message.text.startswith(('http://', 'https://')):
        await message.reply(lex.get('broadcast_invalid_url'))
        return

    try:
        await bot.delete_message(message.chat.id, data['prompt_message_id'])
        await message.delete()
    except TelegramBadRequest:
        pass

    await state.update_data(broadcast_button_url=message.text)
    await show_preview(message, state, bot)

@router.callback_query(BroadcastState.confirming_broadcast, F.data == "confirm_send_broadcast")
async def confirm_and_send_broadcast(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_ids = await db.get_all_user_ids()
    total_users = len(user_ids)

    if total_users == 0:
        await callback.answer("Нет пользователей для рассылки.", show_alert=True)
        return

    data = await state.get_data()
    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await bot.delete_message(callback.message.chat.id, data['preview_message_id'])
        await bot.delete_message(callback.message.chat.id, data['confirmation_message_id'])
    except (TelegramBadRequest, KeyError):
        pass

    status_message = await callback.message.answer(lex.get('broadcast_start_message'))

    text = data.get('broadcast_text')
    photo_id = data.get('broadcast_photo_id')
    button_text = data.get('broadcast_button_text')
    button_url = data.get('broadcast_button_url')

    markup = None
    if button_text and button_url:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text=button_text, url=button_url))
        markup = builder.as_markup()

    sent_count, failed_count = 0, 0

    for i, user_id in enumerate(user_ids, 1):
        try:
            if photo_id:
                await bot.send_photo(user_id, photo_id, caption=text, reply_markup=markup, parse_mode="HTML")
            else:
                await bot.send_message(user_id, text, reply_markup=markup, disable_web_page_preview=True, parse_mode="HTML")
            sent_count += 1
            logging.info(f"Рассылка: успешно отправлено {user_id}")
        except Exception as e:
            failed_count += 1
            logging.warning(f"Рассылка: не удалось отправить {user_id}: {e}")

        if i % 20 == 0:
            try:
                await status_message.edit_text(lex.get('broadcast_progress_update').format(sent=i, total=total_users))
            except TelegramBadRequest:
                pass

        await asyncio.sleep(0.1)

    await status_message.edit_text(lex.get('broadcast_finish_message').format(sent=sent_count, failed=failed_count))
    await state.clear()
