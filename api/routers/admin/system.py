import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from .dependencies import get_current_admin
from utils import bot_state
import database as db
import os

router = APIRouter(prefix="/system", tags=["Admin System"])

@router.post("/restart")
async def restart_bot(admin: dict = Depends(get_current_admin)):
    if admin['role_enum'].value < 4: 
        raise HTTPException(status_code=403, detail="Нужны права CO_OWNER")

    async def _restart():
        await asyncio.sleep(1)
        os.system("pm2 restart CatDock")

    asyncio.create_task(_restart())
    return {"status": "success", "message": "Бот перезагружается..."}

@router.post("/clear-cache")
async def clear_cache(admin: dict = Depends(get_current_admin)):
    bot_state.user_profile_cache.clear()
    bot_state.user_role_cache.clear()
    bot_state.user_language_cache.clear()
    bot_state.user_block_cache.clear()
    bot_state.server_statuses_cache = []

    bot_state.admin_ids_cache.clear()
    bot_state.admin_ids_cache.update(await db.get_all_admin_ids())

    return {"status": "success", "message": "Кэш очищен"}

@router.get("/status")
async def get_system_status(admin: dict = Depends(get_current_admin)):
    return {
        "status": "success",
        "data": {
            "maintenance_mode": bot_state.maintenance_mode,
            "raid_mode": bot_state.raid_mode
        }
    }

@router.post("/maintenance")
async def toggle_maintenance(admin: dict = Depends(get_current_admin)):
    bot_state.maintenance_mode = not bot_state.maintenance_mode

    status = "включен" if bot_state.maintenance_mode else "выключен"
    return {"status": "success", "message": f"Режим тех. работ {status}", "enabled": bot_state.maintenance_mode}

@router.post("/raid")
async def toggle_raid(admin: dict = Depends(get_current_admin)):
    bot_state.raid_mode = not bot_state.raid_mode
    status = "включен" if bot_state.raid_mode else "выключен"
    return {"status": "success", "message": f"Рейд-контроль {status}", "enabled": bot_state.raid_mode}
