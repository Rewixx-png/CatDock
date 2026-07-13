import math
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from aiogram import Bot, types

import database as db
from roles import UserRole, ROLE_NAMES
from utils.action_logger import log_action
from .dependencies import get_current_admin
import utils.docker as dm  

router = APIRouter()

@router.get("/users")
async def admin_get_users(page: int = 0, search: str = None, admin: dict = Depends(get_current_admin)):
    page_size = 30
    users, total_count = await db.get_all_users_paginated(page, page_size, search_query=search)
    sanitized_users = []
    for user in users:
        try:
            raw_role = user['role']
            if str(raw_role).isdigit():
                role_enum = UserRole(int(raw_role))
            else:
                role_enum = UserRole[raw_role]
        except: role_enum = UserRole.PARTICIPANT

        sanitized_users.append({
            'user_id': int(user['user_id']),
            'username': user['username'],
            'first_name': user['first_name'],
            'role': role_enum.value,
            'role_name': ROLE_NAMES.get(role_enum, "Неизвестно"),
            'balance': float(user['balance']),
            'is_blocked': bool(user['is_blocked'])
        })
    total_pages = math.ceil(total_count / page_size)
    return {'status': 'success', 'data': {'users': sanitized_users, 'pagination': {'current_page': page, 'total_pages': total_pages}}}

@router.get("/admins")
async def get_admin_list(admin: dict = Depends(get_current_admin)):
    admins = await db.get_all_admins()
    for ad in admins:
        try:
            raw_role = ad['role']
            if str(raw_role).isdigit(): role_enum = UserRole(int(raw_role))
            else: role_enum = UserRole[raw_role]
        except: role_enum = UserRole.PARTICIPANT
        ad['role_name'] = ROLE_NAMES.get(role_enum, "Неизвестно")
        ad['user_id'] = int(ad['user_id'])
    return {'status': 'success', 'data': admins}

@router.get("/user/{target_user_id}")
async def admin_get_user_details(target_user_id: int, admin: dict = Depends(get_current_admin)):
    user_profile = await db.get_user_profile(target_user_id)
    if not user_profile: raise HTTPException(status_code=404, detail="User not found")
    user_role_enum = await db.get_user_role(target_user_id)
    user_profile['role_name'] = ROLE_NAMES.get(user_role_enum, "Неизвестно")
    return {'status': 'success', 'data': user_profile}

@router.post("/user/{target_user_id}/toggle-block")
async def admin_toggle_user_block(target_user_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    target_role = await db.get_user_role(target_user_id)
    if target_role >= UserRole.JUNIOR_ADMIN: raise HTTPException(status_code=403, detail="Cannot block admin")
    
    new_status = await db.toggle_user_block(target_user_id)
    bot: Bot = request.app.state.bot
    status_text = "заблокирован" if new_status else "разблокирован"
    
    try: await bot.send_message(target_user_id, f"Администратор {status_text} ваш аккаунт.")
    except: pass
    
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(target_user_id)
    await log_action(bot, admin_obj, f"{status_text} пользователя", target_obj)
    
    return {'status': 'success', 'is_blocked': new_status}

@router.post("/user/{target_user_id}/set-role")
async def admin_set_user_role(target_user_id: int, request: Request, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    new_role_id = int(payload.get('role'))
    admin_role = admin['role_enum']
    
    if admin_role.value <= new_role_id: raise HTTPException(status_code=403, detail="Cannot assign role equal/higher")
    
    new_role_name = UserRole(new_role_id).name
    await db.set_user_role(target_user_id, new_role_name)
    role_display = ROLE_NAMES.get(UserRole(new_role_id), new_role_name)
    
    bot: Bot = request.app.state.bot
    try: await bot.send_message(target_user_id, f"Администратор изменил вашу роль на: <b>{role_display}</b>")
    except: pass
    
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(target_user_id)
    await log_action(bot, admin_obj, f"изменил роль на {role_display}", target_obj)
    
    return {'status': 'success', 'message': f'Role changed to {role_display}'}

@router.post("/user/{target_user_id}/balance")
async def admin_update_balance(target_user_id: int, request: Request, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    amount = float(payload.get('amount', 0))
    if amount == 0: raise HTTPException(status_code=400, detail="Amount must be non-zero")
    
    await db.admin_update_user_balance(target_user_id, amount)
    new_bal = await db.get_user_balance(target_user_id)
    
    bot: Bot = request.app.state.bot
    try: await bot.send_message(target_user_id, f"💰 Ваш баланс изменен на <b>{amount:+.2f} RUB</b>. Текущий: {new_bal:.2f} RUB")
    except: pass
    
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = await bot.get_chat(target_user_id)
    await log_action(bot, admin_obj, f"изменил баланс на {amount:+.2f} RUB", target_obj, log_type="balance_change")
    
    return {'status': 'success', 'message': 'Balance updated'}

@router.delete("/user/{target_user_id}/delete")
async def admin_delete_user(target_user_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    if admin['role_enum'] < UserRole.SENIOR_ADMIN: raise HTTPException(status_code=403, detail="Insufficient rights")
    if target_user_id == admin['user_id']: raise HTTPException(status_code=400, detail="Cannot delete self")
    
    target_role = await db.get_user_role(target_user_id)
    if target_role >= admin['role_enum']: raise HTTPException(status_code=403, detail="Cannot delete admin with equal/higher rank")

    containers = await db.get_user_containers(target_user_id)
    for c in containers:
        try: await dm.delete_container(c['server_id'], c['container_name'])
        except Exception: pass

    await db.delete_user_fully(target_user_id)
    
    bot: Bot = request.app.state.bot
    admin_obj = types.User(id=admin['user_id'], is_bot=False, first_name=admin.get('first_name', 'Admin'))
    target_obj = types.User(id=target_user_id, is_bot=False, first_name="Deleted User")
    await log_action(bot, admin_obj, "ПОЛНОСТЬЮ удалил пользователя", target_obj)
    
    return {'status': 'success', 'message': 'User deleted'}
