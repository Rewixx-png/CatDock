import logging
import asyncio
from aiogram import Router, F
from aiogram.types import ChosenInlineResult

import database as db
import utils.docker as dm

router = Router()

@router.chosen_inline_result(F.result_id.startswith("action:"))
async def process_inline_action(chosen_result: ChosenInlineResult):
    user_id = chosen_result.from_user.id

    try:
        _, action, container_id_str = chosen_result.result_id.split(":")
        container_id = int(container_id_str)
    except (ValueError, IndexError):
        logging.error(f"Не удалось распарсить result_id: {chosen_result.result_id}")
        return

    container = await db.get_container_by_id(container_id)
    if not container or container['user_id'] != user_id:
        logging.warning(f"Попытка действия над чужим/несуществующим контейнером. User: {user_id}, Result ID: {chosen_result.result_id}")
        return

    server_id = container['server_id']
    container_name = container['container_name']

    logging.info(f"Пользователь {user_id} инициировал инлайн-действие '{action}' для контейнера {container_name} ({container_id})")

    if action == 'start':
        asyncio.create_task(dm.start_container(server_id, container_name))
    elif action == 'stop':
        asyncio.create_task(dm.stop_container(server_id, container_name))
    elif action == 'restart':
        asyncio.create_task(dm.restart_container(server_id, container_name))
    else:
        logging.warning(f"Получено неизвестное инлайн-действие: {action}")
