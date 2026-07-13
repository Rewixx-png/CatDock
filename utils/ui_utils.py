import logging
import asyncio
from typing import Union, Optional
from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

async def safe_edit_text(
    message: types.Message,
    text: str,
    reply_markup: Optional[types.InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True
) -> bool:
    """
    Безопасное редактирование текста сообщения.
    Игнорирует ошибку 'message is not modified'.
    """
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return True 
        logging.warning(f"[UI] Failed to edit text: {e}")
        return False
    except Exception as e:
        logging.error(f"[UI] Unexpected error in edit_text: {e}")
        return False

async def safe_edit_caption(
    message: types.Message,
    caption: str,
    reply_markup: Optional[types.InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML"
) -> bool:
    """
    Безопасное редактирование подписи к медиа.
    """
    try:
        await message.edit_caption(
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return True
        logging.warning(f"[UI] Failed to edit caption: {e}")
        return False
    except Exception as e:
        logging.error(f"[UI] Unexpected error in edit_caption: {e}")
        return False

async def safe_delete_message(
    bot: Bot,
    chat_id: int,
    message_id: int
) -> bool:
    """
    Безопасное удаление сообщения.
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except (TelegramBadRequest, TelegramForbiddenError):
        
        return False
    except Exception as e:
        logging.debug(f"[UI] Failed to delete message {message_id}: {e}")
        return False

async def safe_callback_answer(
    callback: types.CallbackQuery,
    text: str = None,
    show_alert: bool = False
) -> bool:
    """
    Безопасный ответ на callback.
    Игнорирует 'query is too old'.
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as e:
        if "query is too old" in str(e):
            return False
        logging.warning(f"[UI] Failed to answer callback: {e}")
        return False
    except Exception:
        return False
