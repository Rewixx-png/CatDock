import logging
import traceback
import html
from datetime import datetime
from aiogram import Bot
from aiogram.types import ErrorEvent, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from utils import bot_state
from lexicon import LEXICON
import database as db
from config import SUPPORT_URL
from config import TOKEN, LOG_CHAT_ID

async def handle_errors(event: ErrorEvent, bot: Bot):
    update = event.update
    exception = event.exception
    error_msg = str(exception)

    if isinstance(exception, TelegramBadRequest):
        if "message is not modified" in error_msg:
            return 
        if "query is too old" in error_msg:
            return 
        if "message to delete not found" in error_msg:
            return 

    logging.critical(f"❌ EXCEPTION: {type(exception).__name__}: {exception}", exc_info=exception)

    effective_user = (
        getattr(update.callback_query, 'from_user', None) or
        getattr(update.message, 'from_user', None) or
        getattr(update.inline_query, 'from_user', None) or
        getattr(update.chosen_inline_result, 'from_user', None) or
        getattr(update.pre_checkout_query, 'from_user', None) or
        getattr(update.my_chat_member, 'from_user', None) or
        getattr(update.chat_join_request, 'from_user', None)
    )

    user_id = effective_user.id if effective_user else 0

    safe_username = html.escape(effective_user.username) if effective_user and effective_user.username else "No Username"
    safe_full_name = html.escape(effective_user.full_name) if effective_user else "Unknown"
    
    username_display = f"@{safe_username}"

    tb_str = traceback.format_exc()
    if TOKEN:
        tb_str = tb_str.replace(TOKEN, "******")

    error_name = html.escape(type(exception).__name__)
    safe_error_msg = html.escape(error_msg)

    if effective_user:
        try:
            language_code = await db.get_user_language(user_id) or 'ru'
            lex = LEXICON[language_code]

            user_text = (
                f"{lex.get('error_unhandled_notification', '⚙️ Произошла ошибка.')}\n\n"
                f"<blockquote>❌ <b>{error_name}</b>\n{safe_error_msg}</blockquote>"
            )

            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🆘 Связаться с поддержкой", url=SUPPORT_URL)
            ]])

            if update.callback_query:
                try:
                    await update.callback_query.answer("Error!", show_alert=False)
                except:
                    pass

            try:
                await bot.send_message(chat_id=user_id, text=user_text, reply_markup=markup)
            except:
                pass

        except Exception as e:
            logging.error(f"Не удалось отправить юзеру сообщение об ошибке: {e}")

    short_tb = tb_str.strip().split('\n')[-3:] 
    short_tb_str = html.escape("\n".join(short_tb))

    timestamp = datetime.now().strftime("%H:%M:%S")

    report_text = (
        f"🔥 <b>RUNTIME EXCEPTION</b> <code>{timestamp}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> <a href='tg://user?id={user_id}'>{safe_full_name}</a>\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code> • {username_display}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛑 <b>Error:</b> <code>{error_name}</code>\n"
        f"💬 <b>Info:</b> <i>{safe_error_msg}</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧩 <b>Last Trace:</b>\n"
        f"<pre><code class='language-python'>{short_tb_str}</code></pre>"
    )

    targets = []
    if LOG_CHAT_ID:
        targets.append(LOG_CHAT_ID)
    else:
        
        targets = list(bot_state.admin_ids_cache)

    for target_id in targets:
        try:
            await bot.send_message(target_id, report_text, parse_mode="HTML")

            file_data = BufferedInputFile(
                tb_str.encode('utf-8'), 
                filename=f"crash_{error_name}_{int(datetime.now().timestamp())}.log"
            )
            await bot.send_document(target_id, file_data, caption="📄 <b>Full Traceback</b>", parse_mode="HTML")

            if LOG_CHAT_ID: break 
        except Exception as e:
            logging.error(f"Failed to send error report to {target_id}: {e}")
