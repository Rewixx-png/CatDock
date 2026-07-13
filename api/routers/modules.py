from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
from api.dependencies import get_current_user_id
import database as db
import utils.docker as dm
from utils.worker_tasks import task_backup_modules, task_send_modules

router = APIRouter(tags=["Modules"])

@router.get("/container/{container_id}/modules", response_model=dict)
async def list_container_modules(container_id: int, user_id: int = Depends(get_current_user_id)):
    """Получает список модулей в активном контейнере"""
    container = await db.get_container_by_id(container_id)
    if not container or container['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="Container not found")

    target_path = "/data/loaded_modules"
    
    files = await dm.list_files_in_container(container['server_id'], container['container_name'], target_path)
    
    return {
        "status": "success",
        "container_name": container['container_name'],
        "path": target_path,
        "files": files
    }

@router.post("/container/{container_id}/modules/backup")
async def backup_container_modules(
    container_id: int, 
    payload: dict = Body(...), 
    user_id: int = Depends(get_current_user_id)
):
    """Запускает задачу на бэкап выбранных модулей"""
    container = await db.get_container_by_id(container_id)
    if not container or container['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="Container not found")

    filenames = payload.get('filenames', [])
    if not filenames:
        raise HTTPException(status_code=400, detail="No files selected")

    await task_backup_modules.kiq(
        user_id=user_id,
        container_id=container_id,
        server_id=container['server_id'],
        container_name=container['container_name'],
        filenames=filenames
    )

    return {"status": "success", "message": "Бэкап запущен. Ожидайте уведомления."}

@router.get("/saved", response_model=dict)
async def list_saved_modules(user_id: int = Depends(get_current_user_id)):
    """Возвращает список сохраненных модулей из БД"""
    modules = await db.get_user_saved_modules(user_id)

    result = []
    for m in modules:
        m['saved_at'] = str(m['saved_at'])
        result.append(m)
        
    return {"status": "success", "data": result}

@router.post("/saved/send")
async def send_saved_modules(
    payload: dict = Body(...), 
    user_id: int = Depends(get_current_user_id)
):
    """Отправляет модули в ЛС"""
    module_ids = payload.get('module_ids', [])
    if not module_ids:
        raise HTTPException(status_code=400, detail="No modules selected")

    valid_ids = []
    for mid in module_ids:
        mod = await db.get_module_by_id(mid)
        if mod and mod['user_id'] == user_id:
            valid_ids.append(mid)

    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid modules")

    await task_send_modules.kiq(user_id=user_id, module_ids=valid_ids)
    return {"status": "success", "message": "Файлы отправляются..."}

@router.delete("/saved/{module_id}")
async def delete_saved_module(module_id: int, user_id: int = Depends(get_current_user_id)):
    module = await db.get_module_by_id(module_id)
    if not module or module['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="Not found")
        
    await db.delete_user_module(module_id)

    import os
    try:
        if os.path.exists(module['local_path']):
            os.remove(module['local_path'])
    except: pass
    
    return {"status": "success"}
