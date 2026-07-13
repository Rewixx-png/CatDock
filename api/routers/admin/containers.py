import math
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from aiogram import Bot, types

import database as db
import utils.docker as dm
from config import SERVERS, TARIFFS, IMAGES
from utils.action_logger import log_action
from .dependencies import get_current_admin
from utils.worker_tasks import task_change_server

router = APIRouter()

@router.get("/containers")
async def admin_get_all_containers(page: int = 0, sort_by: str = 'time', search: str = None, admin: dict = Depends(get_current_admin)):
    page_size = 30
    containers_from_db, total_count = await db.get_all_containers_paginated(page, page_size, sort_by=sort_by, search_query=search)
    sanitized = []
    for c in containers_from_db:
        sanitized.append({
            'id': c.get('id'), 
            'user_id': c.get('user_id'), 
            'container_name': c.get('container_name'),
            'remaining_seconds': c.get('remaining_seconds'), 
            'is_frozen': bool(c.get('is_frozen', 0)),
            'tariff_info': TARIFFS.get(c.get('tariff_id'), {}), 
            'server_info': SERVERS.get(c.get('server_id'), {}),
            'image_info': IMAGES.get(c.get('image_id'), {})
        })
    total_pages = math.ceil(total_count / page_size)
    return {'status': 'success', 'data': {'containers': sanitized, 'pagination': {'current_page': page, 'total_pages': total_pages}}}

@router.get("/user/{target_user_id}/containers")
async def admin_get_user_containers(target_user_id: int, admin: dict = Depends(get_current_admin)):
    containers_from_db = await db.get_user_containers(target_user_id)
    status_tasks = [dm.get_container_status(c['server_id'], c['container_name']) for c in containers_from_db]
    statuses = await asyncio.gather(*status_tasks)
    enriched_containers = []
    for i, c in enumerate(containers_from_db):
        c['status'] = statuses[i]
        c['server_info'] = SERVERS.get(c['server_id'], {'name': c['server_id']})
        c['image_info'] = IMAGES.get(c['image_id'], {'name': 'Unknown'})
        enriched_containers.append(c)
    return {'status': 'success', 'data': enriched_containers}

@router.post("/user/{target_user_id}/give-container")
async def admin_give_container(target_user_id: int, request: Request, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    server_id = payload.get('server_id')
    tariff_id = payload.get('tariff_id')
    image_id = payload.get('image_id')
    days = payload.get('days')
    reason = payload.get('reason', 'не указана')

    if not all([server_id, tariff_id, image_id, days]): raise HTTPException(status_code=400, detail="Missing fields")
    try: days = int(days); 
    except: raise HTTPException(status_code=400, detail="Invalid days")
    if days <= 0: raise HTTPException(status_code=400, detail="Invalid days")

    target_profile = await db.get_user_profile(target_user_id)
    if not target_profile: raise HTTPException(status_code=404, detail="User not found")

    container_name, app_port, login_url = await dm.create_container(target_user_id, target_profile.get('username'), server_id, TARIFFS[tariff_id], IMAGES[image_id])
    if not container_name: raise HTTPException(status_code=500, detail="Docker failed")

    await db.add_user_container(target_user_id, server_id, container_name, image_id, tariff_id, app_port, login_url)
    new_container = await db.get_container_by_name(container_name)
    if new_container: await db.admin_set_container_time(new_container['id'], days)

    bot: Bot = request.app.state.bot
    try: await bot.send_message(target_user_id, f"🎉 Админ выдал вам UserBot: <b>{container_name}</b> на {days} дней.\nПричина: {reason}")
    except: pass

    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(target_user_id)
    await log_action(bot, admin_obj, f"выдал контейнер '{container_name}' ({days} дн.)", target_obj, log_type="container_interaction")
    return {'status': 'success', 'message': f'Container {container_name} created.'}

@router.post("/container/{container_id}/freeze")
async def admin_freeze_container(container_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    container = await db.get_container_by_id(container_id)
    if not container: raise HTTPException(status_code=404, detail="Not found")

    await dm.stop_container(container['server_id'], container['container_name'])
    await db.set_container_frozen_state(container_id, True)

    bot: Bot = request.app.state.bot
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(container['user_id'])
    
    await log_action(bot, admin_obj, f"заморозил контейнер '{container['container_name']}'", target_obj, log_type="container_interaction")
    return {"status": "success", "message": "Container frozen"}

@router.post("/container/{container_id}/unfreeze")
async def admin_unfreeze_container(container_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    container = await db.get_container_by_id(container_id)
    if not container: raise HTTPException(status_code=404, detail="Not found")

    await dm.start_container(container['server_id'], container['container_name'])
    await db.set_container_frozen_state(container_id, False)

    bot: Bot = request.app.state.bot
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(container['user_id'])
    
    await log_action(bot, admin_obj, f"разморозил контейнер '{container['container_name']}'", target_obj, log_type="container_interaction")
    return {"status": "success", "message": "Container unfrozen"}

@router.post("/container/{container_id}/add-time")
async def admin_add_time(container_id: int, request: Request, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    days = payload.get("days", 0)
    try: days = int(days)
    except: raise HTTPException(status_code=400)
    
    await db.admin_update_container_time(container_id, days)
    
    container = await db.get_container_by_id(container_id)
    bot: Bot = request.app.state.bot
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(container['user_id'])
    
    await log_action(bot, admin_obj, f"изменил время '{container['container_name']}' на {days} дн.", target_obj, log_type="container_interaction")
    return {"status": "success", "message": "Time updated"}

@router.post("/container/{container_id}/migrate")
async def admin_migrate_container(container_id: int, request: Request, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    new_server_id = payload.get("new_server_id")
    if not new_server_id: raise HTTPException(status_code=400)
    
    container = await db.get_container_by_id(container_id)
    if not container: raise HTTPException(status_code=404)
    
    user_profile = await db.get_user_profile(container['user_id'])

    await task_change_server.kiq(
        chat_id=admin['user_id'], 
        user_id=container['user_id'],
        username=user_profile.get('username'),
        first_name=user_profile.get('first_name'),
        container_id=container_id,
        old_server_id=container['server_id'],
        old_container_name=container['container_name'],
        new_server_id=new_server_id,
        tariff_id=container['tariff_id'],
        image_id=container['image_id']
    )
    
    return {"status": "success", "message": "Миграция запущена в фоне"}

@router.delete("/container/{container_id}")
async def admin_delete_container(container_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    container = await db.get_container_by_id(container_id)
    if not container: raise HTTPException(status_code=404)

    try:
        await dm.delete_container(container['server_id'], container['container_name'])
    except Exception as e:
        logging.warning(f"Failed to delete docker container {container['container_name']}: {e}")
        
    await db.delete_user_container(container_id)
    
    bot: Bot = request.app.state.bot
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(container['user_id'])
    
    await log_action(bot, admin_obj, f"удалил контейнер '{container['container_name']}'", target_obj, log_type="container_interaction")
    return {"status": "success", "message": "Container deleted"}
