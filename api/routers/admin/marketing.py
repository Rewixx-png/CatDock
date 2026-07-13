import logging
import asyncio
import secrets
from fastapi import APIRouter, Depends, HTTPException, Body, Request, BackgroundTasks
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError

import database as db
import settings
from .dependencies import get_current_admin
from utils.action_logger import log_action
from aiogram.types import User

router = APIRouter(prefix="/marketing", tags=["Admin Marketing"])

async def _perform_broadcast(bot: Bot, admin_user_id: int, text: str):
    try:
        user_ids = await db.get_all_user_ids()
        total = len(user_ids)
        sent = 0
        failed = 0

        logging.info(f"📢 [API Broadcast] Запуск рассылки для {total} юзеров. Админ: {admin_user_id}")

        for uid in user_ids:
            try:
                await bot.send_message(uid, text, parse_mode="HTML", disable_web_page_preview=True)
                sent += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.send_message(uid, text, parse_mode="HTML")
                    sent += 1
                except:
                    failed += 1
            except TelegramForbiddenError:
                failed += 1
            except Exception as e:
                logging.warning(f"Failed to send broadcast to {uid}: {e}")
                failed += 1

            await asyncio.sleep(0.05) 

        admin_user = await bot.get_chat(admin_user_id)
        await bot.send_message(
            admin_user_id,
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📨 Отправлено: {sent}\n"
            f"❌ Не доставлено: {failed}\n\n"
            f"Текст:\n{text[:50]}..."
        )

    except Exception as e:
        logging.error(f"Broadcast Task Error: {e}", exc_info=True)

@router.post("/promos/create")
async def create_promo_code(
    request: Request,
    payload: dict = Body(...), 
    admin: dict = Depends(get_current_admin)
):
    code = payload.get('code')
    promo_type = payload.get('type')
    value = payload.get('value')
    post_to_channel = payload.get('post_to_channel', False)

    if not promo_type or value is None:
        raise HTTPException(status_code=400, detail="Type and Value required")

    if code:
        code = code.strip().upper().replace(" ", "_")
    else:
        code = f"CAT-{secrets.token_hex(3).upper()}"

    bot: Bot = request.app.state.bot
    message_id = 0

    try:
        if post_to_channel:
            bot_info = await bot.get_me()
            deep_link = f"https://t.me/{bot_info.username}?start=promo_{code}"

            type_text = {
                'MONEY_BONUS': 'Денежный бонус',
                'FREE_CONTAINER': 'Бесплатный контейнер',
                'DEPOSIT_BONUS': 'Бонус к депозиту',
                'DISCOUNT_BONUS': 'Скидка на услуги',
                'GAME_CHECK': 'Игровые чеки'
            }.get(promo_type, promo_type)

            val_text = f"{value:.2f} RUB" if promo_type == 'MONEY_BONUS' else str(value)
            if promo_type == 'DISCOUNT_BONUS' or promo_type == 'DEPOSIT_BONUS':
                val_text += "%"
            if promo_type == 'FREE_CONTAINER':
                val_text = "1 шт. (Basic)"

            text = (
                f"🎁 <b>НОВЫЙ ПРОМОКОД!</b>\n\n"
                f"Тип: <b>{type_text}</b>\n"
                f"Номинал: <b>{val_text}</b>\n\n"
                f"<code>{code}</code>\n\n"
                f"<i>Успей активировать первым!</i>"
            )

            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="⚡️ Активировать", url=deep_link))

            try:
                target_chat = settings.NEWS_CHAT_USERNAME 
                target_topic = settings.PROMO_TOPIC_ID

                sent_msg = await bot.send_message(
                    chat_id=target_chat,
                    message_thread_id=target_topic,
                    text=text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
                message_id = sent_msg.message_id
                logging.info(f"Промокод отправлен в канал. MessageID: {message_id}")
            except Exception as e:
                logging.error(f"Не удалось отправить промокод в канал: {e}")

        promo_id = await db.create_global_promo_code(
            code=code,
            promo_type=promo_type,
            value=float(value),
            message_id=message_id
        )

        if not promo_id:
            raise HTTPException(status_code=500, detail="DB Error: Failed to create promo (Duplicate?)")

        admin_obj = User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
        await log_action(bot, admin_obj, f"создал глобальный промокод '{code}' ({promo_type}: {value}) через Web")

        return {
            "status": "success", 
            "message": f"Промокод {code} создан!",
            "promo_id": promo_id,
            "code": code,
            "published": message_id > 0
        }

    except Exception as e:
        logging.error(f"Promo create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/broadcast/send")
async def send_broadcast_message(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: dict = Body(...),
    admin: dict = Depends(get_current_admin)
):
    text = payload.get('text')
    if not text or len(text) < 5:
        raise HTTPException(status_code=400, detail="Text is too short")

    bot: Bot = request.app.state.bot

    background_tasks.add_task(_perform_broadcast, bot, admin['user_id'], text)

    admin_obj = User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    await log_action(bot, admin_obj, "запустил массовую рассылку через Web")

    return {"status": "success", "message": "Рассылка запущена в фоновом режиме."}
