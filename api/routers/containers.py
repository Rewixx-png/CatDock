from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from typing import List
import asyncio
import re
import logging
import database as db
import utils.docker as dm
from config import SERVERS, TARIFFS, IMAGES
from api.dependencies import get_current_user_id
from roles import UserRole
from utils.worker_tasks import task_reinstall_container, task_create_full_backup, task_restore_full_backup

logger = logging.getLogger("API_Containers")

router = APIRouter(tags=["Containers"])
DOCKER_NAME_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]+$")

logger.info("✅ [ROUTER LOADED] api/routers/containers.py - Routes registered")

async def get_user_container(container_id: int, user_id: int):
    container = await db.get_container_by_id(container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found in DB")

    if container['user_id'] != user_id:
        user_role = await db.get_user_role(user_id)
        if not user_role or user_role < UserRole.ADMIN:
             raise HTTPException(status_code=403, detail="Not authorized to access this container")

    return container

@router.get("/containers", response_model=List[dict])
async def list_containers(user_id: int = Depends(get_current_user_id)):
    containers_from_db = await db.get_user_containers(user_id)

    status_tasks = [dm.get_container_status(c['server_id'], c['container_name']) for c in containers_from_db]
    statuses = await asyncio.gather(*status_tasks)

    enriched_containers = []
    for i, c in enumerate(containers_from_db):
        c['status'] = statuses[i]
        c['server_info'] = SERVERS.get(c['server_id'], {'name': c['server_id']})
        c['tariff_info'] = TARIFFS.get(c['tariff_id'], {'name': 'Unknown'})
        c['image_info'] = IMAGES.get(c['image_id'], {'name': 'Unknown'})
        enriched_containers.append(c)

    return enriched_containers

@router.post("/tariffs/purchase")
async def purchase_tariff(request: Request, user_id: int = Depends(get_current_user_id)):
    from utils.pricing import calculate_final_price, use_purchase_bonus

    money_deducted = False
    final_price = 0.0

    try:
        data = await request.json()
        tariff_id, image_id = data.get('tariff_id'), data.get('image_id')

        requested_server_id = data.get('server_id') 

        user_profile = await db.get_user_profile(user_id)

        if not all([tariff_id, image_id]): 
            raise HTTPException(status_code=400, detail='Не все параметры указаны.')

        tariff = TARIFFS.get(tariff_id)
        if not tariff or tariff_id == 'free': 
             raise HTTPException(status_code=400, detail='Неверный или недоступный тариф.')

        if requested_server_id:
            if requested_server_id not in SERVERS:
                raise HTTPException(status_code=400, detail='Неверный ID сервера.')
            server_id = requested_server_id
        else:
            server_id = await dm.find_optimal_server(tariff_id, user_id)

        if not server_id:
            raise HTTPException(status_code=503, detail=f"К сожалению, для тарифа «{tariff['name']}» сейчас нет свободных мест.")

        final_price = await calculate_final_price(tariff_id, server_id, user_profile)

        if final_price > 0:
            if not await db.try_deduct_user_balance(user_id, final_price):
                 raise HTTPException(status_code=402, detail=f"Недостаточно средств. Требуется {final_price:.2f}₽.")
            money_deducted = True

        tariff_id_for_db, promo_used = await use_purchase_bonus(user_id, tariff_id)

        container_name, app_port, login_url = await dm.create_container(
            user_id, user_profile.get('username'), server_id, tariff, IMAGES[image_id]
        )

        if not all([container_name, app_port, login_url]): 
            raise Exception(f"Docker Manager вернул пустые данные. Проверьте логи сервера.")

        await db.add_user_container(user_id, server_id, container_name, image_id, tariff_id_for_db, app_port, login_url)

        return {
            'status': 'success', 
            'message': f'UserBot {container_name} успешно создан!', 
            'final_price': final_price
        }

    except HTTPException:
        if money_deducted:
             await db.update_user_balance(user_id, final_price)
        raise
    except Exception as e:
        if money_deducted: 
            logger.warning(f"[API] Возврат {final_price} RUB пользователю {user_id} из-за ошибки.")
            try:
                await db.update_user_balance(user_id, final_price)
            except: pass

        logger.error(f"[WEB] Ошибка покупки: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка при создании: {str(e)}")

@router.get("/container/{container_id}", response_model=dict)
async def get_container_details(container_id: int, user_id: int = Depends(get_current_user_id)):
    c = await get_user_container(container_id, user_id)

    c['server_info'] = SERVERS.get(c['server_id'], {'name': c['server_id']})
    c['tariff_info'] = TARIFFS.get(c['tariff_id'], {'name': 'Unknown'})
    c['image_info'] = IMAGES.get(c['image_id'], {'name': 'Unknown'})

    status, stats, disk_size = await asyncio.gather(
        dm.get_container_status(c['server_id'], c['container_name']), 
        dm.get_container_stats(c['server_id'], c['container_name']),
        dm.get_container_disk_usage(c['server_id'], c['container_name'])
    )

    c['status'] = status
    c['stats'] = stats or {}
    c['disk_size'] = disk_size

    c['server_name'] = c['server_info'].get('name')
    c['tariff_name'] = c['tariff_info'].get('name')
    c['image_name'] = c['image_info'].get('name')

    return {"status": "success", "data": c}

@router.get("/container/{container_id}/stats", response_model=dict)
async def get_container_stats(container_id: int, user_id: int = Depends(get_current_user_id)):
    container = await get_user_container(container_id, user_id)
    try:
        stats = await asyncio.wait_for(
            dm.get_container_stats(container['server_id'], container['container_name']),
            timeout=5.0
        )
        status = await dm.get_container_status(container['server_id'], container['container_name'])

        return {
            "cpu_usage": stats.get('cpu_usage', 0.0) if stats else 0.0,
            "ram_usage": stats.get('ram_raw', 'N/A') if stats else 'N/A',
            "status": status
        }
    except Exception:
        return {"cpu_usage": 0.0, "ram_usage": "N/A", "status": "error"}

@router.post("/container/{container_id}/action", response_model=dict)
async def handle_container_action(container_id: int, request: Request, user_id: int = Depends(get_current_user_id)):
    container = await get_user_container(container_id, user_id)
    try:
        data = await request.json()
        action = data.get('action')
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if container.get('is_frozen'):
        raise HTTPException(status_code=400, detail="Container is frozen")

    action_map = {'start': dm.start_container, 'stop': dm.stop_container, 'restart': dm.restart_container}
    if action not in action_map:
        raise HTTPException(status_code=400, detail="Invalid action")

    try:
        await action_map[action](container['server_id'], container['container_name'])
        return {"status": "success", "message": f"Action '{action}' initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/container/{container_id}/logs")
async def get_container_logs_handler(container_id: int, lines: int = 100, user_id: int = Depends(get_current_user_id)):
    container = await get_user_container(container_id, user_id)
    if not (10 <= lines <= 2000): lines = 100

    logs = await dm.get_container_logs(container['server_id'], container['container_name'], lines)
    if logs is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve logs")

    return {"status": "success", "data": logs}

@router.post("/container/{container_id}/rename")
async def handle_container_rename(container_id: int, request: Request, user_id: int = Depends(get_current_user_id)):
    logger.info(f"Rename request for {container_id} by {user_id}")
    container = await get_user_container(container_id, user_id)

    try: 
        data = await request.json()
        new_name = data.get('new_name')
    except: 
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not new_name or not (3 < len(new_name) < 30) or not DOCKER_NAME_REGEX.match(new_name):
         raise HTTPException(status_code=400, detail="Invalid name format")

    try:
        await dm.rename_container(container['server_id'], container['container_name'], new_name)
        await db.update_container_name(container_id, new_name)
        return {'status': 'success', 'message': f'Renamed to {new_name}'}
    except Exception as e:
        if 'is already in use' in str(e): 
             raise HTTPException(status_code=409, detail="Name already in use")
        raise HTTPException(status_code=500, detail=f"Rename failed: {str(e)}")

@router.post("/container/{container_id}/reinstall/v2")
async def handle_container_reinstall_v2(container_id: int, user_id: int = Depends(get_current_user_id)):
    logger.info(f"API Reinstall V2 request for {container_id} by {user_id}")
    container = await get_user_container(container_id, user_id)

    try:
        owner_profile = await db.get_user_profile(container['user_id'])

        tariff = TARIFFS.get(container['tariff_id'])
        if not tariff and container['tariff_id'] == 'admin':
            tariff = TARIFFS['basic']

        image = IMAGES.get(container['image_id'])
        if not tariff or not image:
            raise Exception("Invalid tariff or image config in DB")

        await task_reinstall_container.kiq(
            chat_id=user_id,
            user_id=user_id,
            first_name=owner_profile.get('first_name', 'User'),
            container_db_id=container_id,
            server_id=container['server_id'],
            old_container_name=container['container_name'],
            tariff_data=tariff,
            image_data=image,
            username_for_create=owner_profile.get('username') or str(user_id)
        )

        return {'status': 'success', 'message': 'Задача на переустановку запущена (V2).'}
    except Exception as e:
        logger.error(f"API Reinstall V2 Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.delete("/container/{container_id}/delete")
async def handle_container_delete(container_id: int, user_id: int = Depends(get_current_user_id)):
    logger.info(f"Delete request for {container_id} by {user_id}")
    container = await get_user_container(container_id, user_id)

    try:
        try:
            await dm.delete_container(container['server_id'], container['container_name'])
        except Exception as e:
            logger.warning(f"Docker delete failed for {container['container_name']} (maybe already gone): {e}")

        await db.delete_user_container(container_id)
        return {'status': 'success', 'message': 'Deleted'}
    except Exception as e:
        logger.error(f"DB delete failed: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.post("/container/{container_id}/backup/create")
async def create_full_backup(container_id: int, user_id: int = Depends(get_current_user_id)):
    container = await get_user_container(container_id, user_id)

    if container.get('is_frozen'):
        raise HTTPException(status_code=400, detail="Container is frozen")

    await task_create_full_backup.kiq(
        user_id=user_id,
        container_id=container_id,
        server_id=container['server_id'],
        container_name=container['container_name'],
        tariff_id=container['tariff_id']
    )

    return {"status": "success", "message": "Бэкап запущен. Бот будет временно остановлен."}

@router.post("/container/{container_id}/backup/restore")
async def restore_full_backup(container_id: int, user_id: int = Depends(get_current_user_id)):
    container = await get_user_container(container_id, user_id)

    backup = await db.get_user_backup(user_id, container['tariff_id'])

    if not backup:
        raise HTTPException(status_code=404, detail="Нет сохраненных бэкапов для этого тарифа.")

    await task_restore_full_backup.kiq(
        user_id=user_id,
        container_id=container_id,
        server_id=container['server_id'],
        container_name=container['container_name'],
        backup_path=backup['backup_path']
    )

    return {"status": "success", "message": "Восстановление запущено. Бот перезагрузится."}

@router.get("/container/{container_id}/backup/status")
async def get_backup_status(container_id: int, user_id: int = Depends(get_current_user_id)):
    container = await get_user_container(container_id, user_id)
    backup = await db.get_user_backup(user_id, container['tariff_id'])

    if backup:
        return {
            "has_backup": True,
            "date": str(backup['created_at']),
            "size_mb": round(backup['file_size'] / (1024*1024), 2)
        }
    return {"has_backup": False}
