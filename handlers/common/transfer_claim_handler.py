import logging
from datetime import datetime, timedelta
from aiogram import Bot, types

import database as db
from lexicon import LEXICON
from utils.action_logger import log_action

from config import IMAGES, SERVERS, TARIFFS
from .menu_utils import format_seconds_to_dhms

async def claim_container_by_token(message: types.Message, token: str, bot: Bot):
    new_owner = message.from_user
    language_code = await db.get_user_language(new_owner.id) or 'ru'
    lex = LEXICON[language_code]

    container, result = await db.claim_container_transfer(token, new_owner.id)
    if result == "self":
        await message.answer(lex.get('transfer_self_claim', "Вы не можете передать контейнер самому себе. Для отмены передачи воспользуйтесь соответствующей кнопкой в меню управления контейнером."))
        return
    if not container:
        await message.answer(lex.get('transfer_token_not_found', "❌ Эта ссылка для передачи недействительна, просрочена или уже была использована."))
        return

    container_id = container['id']
    original_owner_id = container['original_owner_id']

    await message.answer(lex.get('transfer_claim_success_new_owner').format(container_name=container['container_name']))

    try:
        original_owner_user = await bot.get_chat(original_owner_id)
        original_owner_lang = await db.get_user_language(original_owner_id) or 'ru'
        original_owner_lex = LEXICON[original_owner_lang]
        await bot.send_message(
            original_owner_id,
            original_owner_lex.get('transfer_claim_success_old_owner').format(
                container_name=container['container_name'],
                new_owner_name=new_owner.full_name
            )
        )

        updated_container = await db.get_container_by_id(container_id)
        end_time = datetime.now() + timedelta(seconds=updated_container['remaining_seconds'])

        log_text_topic = (
            f"👤 <b>[ПОЛЬЗОВАТЕЛЬ: {new_owner.full_name} (<code>{new_owner.id}</code>)]</b>\n"
            f"Получил контейнер:\n\n"
            f"<b>От пользователя:</b> {original_owner_user.full_name} (<code>{original_owner_id}</code>)\n\n"
            f"<b>Дата получения:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"<b>Образ контейнера:</b> {IMAGES.get(updated_container['image_id'], {}).get('name', updated_container['image_id'])}\n"
            f"<b>ID контейнера:</b> <code>{updated_container['id']}</code>\n"
            f"<b>Время окончания аренды:</b> {end_time.strftime('%Y-%m-%d %H:%M:%S')} ({format_seconds_to_dhms(updated_container['remaining_seconds'])})\n"
            f"<b>Сервер контейнера:</b> {SERVERS.get(updated_container['server_id'], {}).get('name', updated_container['server_id'])}\n"
            f"<b>Тариф контейнера:</b> {TARIFFS.get(updated_container['tariff_id'], {}).get('name', updated_container['tariff_id'])}"
        )
        logging.info("Topic log removed")

    except Exception as e:
        logging.warning(f"Не удалось уведомить старого владельца {original_owner_id} или залогировать передачу: {e}")

    await log_action(bot, new_owner, f"получил по ссылке контейнер '{container['container_name']}' от пользователя с ID {original_owner_id}")
