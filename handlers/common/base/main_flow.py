import logging
import html
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import BOT_VERSION
from keyboards import get_main_menu_keyboard, get_language_selection_keyboard, get_initial_start_keyboard
from lexicon import LEXICON
from utils.action_logger import log_action
from states.user_states import SupportState
from keyboards import get_cancel_keyboard
from utils.ui_utils import safe_edit_caption, safe_delete_message, safe_callback_answer

from ..transfer_claim_handler import claim_container_by_token

router = Router()


async def _delete_message_later(bot: Bot, chat_id: int, message_id: int, delay: int = 5):
    await asyncio.sleep(delay)
    await safe_delete_message(bot, chat_id, message_id)


async def send_main_menu(event: types.Message | types.CallbackQuery, state: FSMContext, is_new_user: bool = False):
    await state.clear()

    user = event.from_user
    language_code = await db.get_user_language(user.id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])
    welcome_text_key = 'welcome_text_new_user' if is_new_user else 'welcome_text'

    caption_template = lex.get(welcome_text_key, lex.get('welcome_text'))
    safe_first_name = html.escape(user.first_name)
    caption = caption_template.format(first_name=safe_first_name)
    caption += f"\n\n<tg-spoiler>v{BOT_VERSION}</tg-spoiler>"

    markup = await get_main_menu_keyboard(language_code, user.id)

    if isinstance(event, types.CallbackQuery):
        try:
            await safe_edit_caption(
                callback=event,
                caption=caption,
                reply_markup=markup
            )
        except TelegramBadRequest:
            try:
                await safe_delete_message(event.bot, event.message.chat.id, event.message.message_id)
            except Exception:
                pass
            await event.bot.send_message(
                chat_id=event.from_user.id,
                text=caption,
                reply_markup=markup
            )
    else:
        await event.answer(
            text=caption,
            reply_markup=markup
        )


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject | None = None):
    await state.clear()
    args = command.args.strip() if command and command.args else None
    user = message.from_user

    exists = await db.user_exists(user.id)
    is_new = False

    if not exists:
        is_new = True
        await db.create_user(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "User"
        )

    if not await db.has_completed_language_selection(user.id):
        await message.answer(
            "Select language / Выберите язык:",
            reply_markup=get_language_selection_keyboard()
        )
        return

    if args and args.startswith("ct_"):
        await claim_container_by_token(message, args, state)
        return

    await send_main_menu(message, state, is_new_user=is_new)


@router.callback_query(F.data == "initial_start_done")
async def initial_start_done_handler(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete_message(callback.bot, callback.message.chat.id, callback.message.message_id)
    await send_main_menu(callback, state, is_new_user=True)
    await safe_callback_answer(callback)


@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    await safe_delete_message(callback.bot, callback.message.chat.id, callback.message.message_id)
    await send_main_menu(callback, state)
