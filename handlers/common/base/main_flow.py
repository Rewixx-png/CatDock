import html
from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext

import database as db
from config import BOT_VERSION
from keyboards import get_main_menu_keyboard, get_language_selection_keyboard
from lexicon import LEXICON
from utils.ui_utils import safe_edit_caption, safe_delete_message, safe_callback_answer

from ..transfer_claim_handler import claim_container_by_token

router = Router()

async def send_main_menu(event: types.Message | types.CallbackQuery, state: FSMContext, is_new_user: bool = False):
    await state.clear()

    user = event.from_user
    language_code = await db.get_user_language(user.id) or 'ru'
    lex = LEXICON.get(language_code, LEXICON['ru'])
    welcome_text_key = 'welcome_text_new_user' if is_new_user else 'welcome_text'

    caption_template = lex.get(welcome_text_key) or lex.get('welcome_text') or "Привет, {first_name}!"
    safe_first_name = html.escape(user.first_name or "User")
    caption = caption_template.format(first_name=safe_first_name)
    caption += f"\n\n<tg-spoiler>v{BOT_VERSION}</tg-spoiler>"

    markup = await get_main_menu_keyboard(language_code, user.id)

    if isinstance(event, types.CallbackQuery):
        edited = await safe_edit_caption(
            callback=event,
            caption=caption,
            reply_markup=markup,
        )
        if not edited:
            await event.bot.send_message(
                chat_id=event.from_user.id,
                text=caption,
                reply_markup=markup,
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

    referrer_id = None
    transfer_prefixes = ("ct_", "claim_")
    is_referral = bool(args and (args.startswith("ref_") or args.isdigit()))
    if is_referral:
        try:
            referral_value = args[4:] if args.startswith("ref_") else args
            ref_id = int(referral_value.replace('/', ''))
            if ref_id != user.id:
                referrer_id = ref_id
        except (ValueError, TypeError):
            await message.answer(LEXICON['ru']['invalid_referral'])
            return

    profile = await db.get_user_profile(user.id)
    is_new = False
    if not profile:
        is_new = await db.add_user(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "User",
            referrer_id=referrer_id,
        )

    if args and args.startswith(transfer_prefixes):
        await claim_container_by_token(message, args, message.bot)
        return

    if is_new:
        await state.update_data(is_new_user=True)
        await message.answer(
            "Select language / Выберите язык:",
            reply_markup=get_language_selection_keyboard(),
        )
        return

    await send_main_menu(message, state, is_new_user=is_new)


@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    await safe_delete_message(callback.bot, callback.message.chat.id, callback.message.message_id)
    await send_main_menu(callback, state)


@router.callback_query(F.data == "initial_start_done")
async def initial_start_done_handler(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete_message(callback.bot, callback.message.chat.id, callback.message.message_id)
    await send_main_menu(callback, state, is_new_user=True)
    await safe_callback_answer(callback)
