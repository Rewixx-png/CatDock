import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from .dependencies import get_current_admin
import database as db
from config import SERVERS
from utils import bot_state
from utils.server_loader import load_servers_to_cache
from roles import UserRole

router = APIRouter(prefix="/servers", tags=["Admin Servers"])

@router.get("/")
async def get_servers_list(admin: dict = Depends(get_current_admin)):
    """Получить список всех серверов с их статусами из кэша."""
    
    servers_data = []

    for server_id, info in bot_state.servers_cache.items():
        is_active = bot_state.server_states.get(server_id, True)

        status_info = next((s for s in bot_state.server_statuses_cache if s['id'] == server_id), None)
        
        servers_data.append({
            "id": server_id,
            "name": info.get('name', server_id),
            "ip": info.get('ip'),
            "user": info.get('user'),
            "port": info.get('check_port', 22),
            "is_active": is_active,
            "is_local": info.get('local', False),
            "status": status_info.get('status', 'unknown') if status_info else 'unknown',
            "ping": status_info.get('ping', 'N/A') if status_info else 'N/A',
            "stats": {
                "cpu": status_info.get('cpu', 'N/A') if status_info else 'N/A',
                "ram": status_info.get('ram', 'N/A') if status_info else 'N/A',
                "disk": status_info.get('disk', 'N/A') if status_info else 'N/A'
            }
        })
    
    return {"status": "success", "data": servers_data}

@router.post("/add")
async def add_server(payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    """Добавить новый сервер."""
    if admin['role_enum'] < UserRole.CO_OWNER:
        raise HTTPException(status_code=403, detail="Требуются права CO_OWNER")
        
    server_id = payload.get("id", "").strip().lower()
    name = payload.get("name")
    ip = payload.get("ip")
    password = payload.get("password")
    
    if not all([server_id, name, ip]):
        raise HTTPException(status_code=400, detail="Не все поля заполнены")
        
    if server_id in SERVERS:
        raise HTTPException(status_code=400, detail="ID сервера уже существует")
        
    default_limits = {'free': 5, 'basic': 10, 'medium': 10, 'large': 5}
    
    try:
        await db.add_server(
            server_id=server_id,
            name=name,
            ip=ip,
            ssh_user='root',
            password=password,
            check_port=22,
            limits=default_limits
        )
        await load_servers_to_cache()
        return {"status": "success", "message": f"Сервер {name} добавлен"}
    except Exception as e:
        logging.error(f"Error adding server: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{server_id}/toggle")
async def toggle_server(server_id: str, admin: dict = Depends(get_current_admin)):
    """Включить/Выключить сервер."""
    if admin['role_enum'] < UserRole.CO_OWNER:
        raise HTTPException(status_code=403, detail="Требуются права CO_OWNER")

    if server_id not in bot_state.servers_cache:
        raise HTTPException(status_code=404, detail="Сервер не найден")
        
    current_state = bot_state.server_states.get(server_id, True)
    new_state = not current_state
    
    bot_state.server_states[server_id] = new_state
    
    try:
        await db.set_bot_setting('server_states', json.dumps(bot_state.server_states))
        await db.update_server_status(server_id, new_state)
        
        if server_id in bot_state.servers_cache:
            bot_state.servers_cache[server_id]['active'] = new_state
            
        return {"status": "success", "new_state": new_state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{server_id}")
async def delete_server(server_id: str, admin: dict = Depends(get_current_admin)):
    """Удалить сервер."""
    if admin['role_enum'] < UserRole.CO_OWNER:
        raise HTTPException(status_code=403, detail="Требуются права CO_OWNER")
        
    try:
        await db.delete_server(server_id)
        await load_servers_to_cache()
        return {"status": "success", "message": "Сервер удален"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{server_id}")
async def edit_server(server_id: str, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    """Редактировать параметры сервера."""
    if admin['role_enum'] < UserRole.CO_OWNER:
        raise HTTPException(status_code=403, detail="Требуются права CO_OWNER")
        
    allowed_fields = ['name', 'ip', 'password', 'check_port']
    
    try:
        for field, value in payload.items():
            if field in allowed_fields:
                if field == 'check_port':
                    value = int(value)
                await db.update_server_field(server_id, field, value)
        
        await load_servers_to_cache()
        return {"status": "success", "message": "Сервер обновлен"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
