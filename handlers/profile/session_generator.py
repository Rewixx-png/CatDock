import logging
import re
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.exceptions import TelegramBadRequest

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

import database as db
from states.user_states import SessionGenState
from lexicon import LEXICON
from keyboards import get_session_management_keyboard, get_cancel_keyboard, get_skip_comment_keyboard, get_session_view_keyboard
from utils.action_logger import log_action

router = Router()
temp_clients: dict[int, TelegramClient] = {}

async def show_session_menu(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    text = lex.get('session_menu_title')
    markup = get_session_management_keyboard(language_code)

    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.delete()
        except TelegramBadRequest:
            pass
        await event.message.answer(text, reply_markup=markup)
        try:
            await event.answer()
        except TelegramBadRequest:
            pass
    else:
        await event.answer(text, reply_markup=markup)

async def cleanup_client(user_id: int, state: FSMContext):
    await state.clear()
    if user_id in temp_clients:
        client = temp_clients[user_id]
        if client.is_connected():
            await client.disconnect()
        del temp_clients[user_id]

@router.callback_query(F.data == "string_session_menu")
async def string_session_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await show_session_menu(callback, state)

@router.callback_query(F.data == "session_generate")
async def start_session_gen(callback: types.CallbackQuery, state: FSMContext):
    await cleanup_client(callback.from_user.id, state)

    language_code = await db.get_user_language(callback.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    try:
        await callback.message.edit_text(
            lex.get('session_enter_api_id'),
            reply_markup=get_cancel_keyboard(language_code)
        )
    except TelegramBadRequest: 
        await callback.message.answer(
            lex.get('session_enter_api_id'),
            reply_markup=get_cancel_keyboard(language_code)
        )
    await state.set_state(SessionGenState.waiting_for_api_id)
    await callback.answer()

@router.message(SessionGenState.waiting_for_api_id)
async def api_id_handler(message: types.Message, state: FSMContext):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    if not message.text or not message.text.isdigit():
        await message.reply(lex.get('session_invalid_api_id'))
        return

    await state.update_data(api_id=int(message.text))
    await message.answer(lex.get('session_enter_api_hash'))
    await state.set_state(SessionGenState.waiting_for_api_hash)

@router.message(SessionGenState.waiting_for_api_hash)
async def api_hash_handler(message: types.Message, state: FSMContext):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]

    await state.update_data(api_hash=message.text.strip())
    await message.answer(lex.get('session_enter_phone'))
    await state.set_state(SessionGenState.waiting_for_phone)

@router.message(SessionGenState.waiting_for_phone)
async def phone_handler(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    user_id = message.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]
    data = await state.get_data()

    client = TelegramClient(StringSession(), data['api_id'], data['api_hash'])
    temp_clients[user_id] = client

    await message.answer(lex.get('session_sending_code'))

    try:
        await client.connect()
        sent_code = await client.send_code_request(phone, force_sms=False)

        await state.update_data(phone=phone, phone_code_hash=sent_code.phone_code_hash)
        await message.answer(lex.get('session_enter_code'))
        await state.set_state(SessionGenState.waiting_for_code)
    except Exception as e:
        logging.error(f"Telethon: Ошибка при запросе кода для {phone}: {e}", exc_info=True)
        await message.answer(lex.get('session_generic_error').format(error=e))
        await cleanup_client(user_id, state)
        await show_session_menu(message, state)

async def _process_sign_in_final(message: types.Message, state: FSMContext):
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    client = temp_clients[message.from_user.id]

    session_string = client.session.save()
    await state.update_data(session_string=session_string)

    await message.answer(lex.get('session_success_title'))
    await message.answer(lex.get('session_enter_comment_prompt'), reply_markup=get_skip_comment_keyboard(language_code))
    await state.set_state(SessionGenState.waiting_for_comment)

@router.message(SessionGenState.waiting_for_code)
async def code_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    client = temp_clients[user_id]
    raw_code = message.text
    code = re.sub(r'\D', '', raw_code)

    try:
        await client.sign_in(
            phone=data['phone'],
            code=code,
            phone_code_hash=data['phone_code_hash']
        )
        await _process_sign_in_final(message, state)
    except SessionPasswordNeededError:
        language_code = await db.get_user_language(user_id) or 'ru'
        await message.answer(LEXICON[language_code].get('session_enter_password'))
        await state.set_state(SessionGenState.waiting_for_password)
    except Exception as e:
        language_code = await db.get_user_language(user_id) or 'ru'
        logging.error(f"Telethon: Ошибка при вводе кода для {user_id}: {e}", exc_info=True)
        await message.answer(LEXICON[language_code].get('session_generic_error').format(error=e))
        await cleanup_client(user_id, state)
        await show_session_menu(message, state)

@router.message(SessionGenState.waiting_for_password)
async def password_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    client = temp_clients[user_id]
    password = message.text

    try:
        await client.sign_in(password=password)
        await _process_sign_in_final(message, state)
    except Exception as e:
        language_code = await db.get_user_language(user_id) or 'ru'
        logging.error(f"Telethon: Ошибка при вводе пароля для {user_id}: {e}", exc_info=True)
        await message.answer(LEXICON[language_code].get('session_generic_error').format(error=e))
        await cleanup_client(user_id, state)
        await show_session_menu(message, state)

@router.message(SessionGenState.waiting_for_comment)
@router.callback_query(F.data == "session_skip_comment", SessionGenState.waiting_for_comment)
async def comment_handler(event: types.Message | types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = event.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]
    data = await state.get_data()

    comment = None
    if isinstance(event, types.Message) and event.text.strip() != '-':
        comment = event.text.strip()

    await db.add_user_session(user_id, data['session_string'], comment)

    log_text = f"сгенерировал новую строковую сессию (комментарий: «{comment}»)" if comment else "сгенерировал новую строковую сессию (без комментария)"
    await log_action(bot, event.from_user, log_text)

    message_to_send_from = event.message if isinstance(event, types.CallbackQuery) else event
    if isinstance(event, types.CallbackQuery):
        try:
            if event.message: await event.message.delete()
        except TelegramBadRequest: pass
        await event.answer(lex.get('session_saved_success'), show_alert=True)
    else:
        await event.answer(lex.get('session_saved_success'))

    await message_to_send_from.answer(lex.get('session_string_is'))
    await message_to_send_from.answer(f"<code>{data['session_string']}</code>")

    await cleanup_client(user_id, state)
    await show_session_menu(event, state)

@router.callback_query(F.data == "session_view")
async def view_sessions_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    sessions = await db.get_user_sessions(user_id)
    if not sessions:
        await callback.answer(lex.get('session_no_saved_sessions'), show_alert=True)
        return

    text = lex.get('session_list_title')
    markup = get_session_view_keyboard(sessions, language_code)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("session_delete:"))
async def delete_session_handler(callback: types.CallbackQuery):
    session_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    await db.delete_user_session(session_id, user_id)
    await callback.answer(lex.get('session_deleted_success'), show_alert=True)
    await view_sessions_handler(callback)

@router.callback_query(F.data == "session_download")
async def download_sessions_handler(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    sessions = await db.get_user_sessions(user_id)
    if not sessions:
        await callback.answer(lex.get('session_no_saved_sessions'), show_alert=True)
        return

    file_content = ""
    for s in sessions:
        file_content += f"--- Session created on: {s['creation_date']} ---\n"
        if s['comment']:
            file_content += f"Comment: {s['comment']}\n"
        file_content += f"{s['session_string']}\n\n"

    file_data = BufferedInputFile(file_content.encode('utf-8'), filename="catdock_sessions.txt")
    await bot.send_document(user_id, file_data, caption=lex.get('session_download_caption'))
    await callback.answer()

@router.callback_query(F.data == "cancel_payment", SessionGenState)
async def cancel_session_gen(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Генерация сессии отменена.")
    await cleanup_client(callback.from_user.id, state)
    await show_session_menu(callback, state)
