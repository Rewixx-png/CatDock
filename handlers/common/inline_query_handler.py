import logging
from uuid import uuid4
from aiogram import Router, F, Bot
from aiogram.types import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton
)

import database as db
from lexicon import LEXICON
from config import IMAGES, SERVERS
import utils.docker as dm

router = Router()

@router.inline_query()
async def inline_mode_handler(query: InlineQuery, bot: Bot):
    user_id = query.from_user.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]

    query_text = query.query.strip()

    results = []

    if query_text.startswith("manage:"):
        try:
            container_id = int(query_text.split(":")[1])
            container = await db.get_container_by_id(container_id)

            if not container or container['user_id'] != user_id:
                return await query.answer([], cache_time=1)

            status = await dm.get_container_status(container['server_id'], container['container_name'])

            actions = []
            if status == 'running':
                actions.append(('stop', lex.get('turn_off_button', 'Выключить'), '⏹️'))
                actions.append(('restart', lex.get('restart_button', 'Рестарт'), '🔄'))
            else:
                actions.append(('start', lex.get('turn_on_button', 'Включить'), '▶️'))

            for action_key, action_text, emoji in actions:
                results.append(
                    InlineQueryResultArticle(
                        id=f"action:{action_key}:{container_id}",
                        title=f"{emoji} {action_text}",
                        description=lex.get('inline_action_description', 'Выполнить для {name}').format(name=container['container_name']),
                        input_message_content=InputTextMessageContent(
                            message_text=f"{emoji} {lex.get('action_triggered', 'Выполняю действие «{action}» для')} <code>{container['container_name']}</code>...".format(action=action_text),
                            parse_mode="HTML"
                        )
                    )
                )

        except (ValueError, IndexError):
            pass

    else:
        user_containers = await db.get_user_containers(user_id)
        if user_containers:
            for container in user_containers:
                server_name = SERVERS.get(container['server_id'], {}).get('name', 'N/A')
                image_name = IMAGES.get(container['image_id'], {}).get('name', 'N/A')

                results.append(
                    InlineQueryResultArticle(
                        id=str(container['id']),
                        title=f"{server_name} - {image_name}",
                        description=f"({container['container_name']})",
                        input_message_content=InputTextMessageContent(
                            message_text=lex.get('inline_bot_selected_text', 'Выбран бот: {name}').format(name=container['container_name'])
                        ),
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(
                                text=lex.get('inline_select_bot_button', "🛠️ Управлять этим ботом"),
                                switch_inline_query_current_chat=f"manage:{container['id']}"
                            )
                        ]])
                    )
                )
        else:
            bot_info = await bot.get_me()
            results.append(
                InlineQueryResultArticle(
                    id='no-bots',
                    title=lex.get('inline_no_bots_title', "У вас нет активных юзерботов"),
                    description=lex.get('inline_no_bots_description', "Нажмите, чтобы перейти в бот и создать нового"),
                    input_message_content=InputTextMessageContent(
                        message_text=lex.get('my_userbots_no_bots', "У вас еще нет юзерботов.")
                    ),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text=lex.get('inline_create_bot_button', "➕ Создать UserBot"),
                            url=f"https://t.me/{bot_info.username}?start=tariffs"
                        )
                    ]])
                )
            )

    await query.answer(results, cache_time=1, is_personal=True)
