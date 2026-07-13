import asyncio
import logging
import math
import os
import uuid
import aiofiles
import random
import time
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Body
from api.dependencies import get_current_user_id
import database as db
from config import SERVERS, TARIFFS, IMAGES, PROJECT_ROOT
from roles import ROLE_NAMES, UserRole
from utils import bot_state
from api.utils import _get_avatar_url
import utils.docker as dm
from utils.action_logger import log_action
from aiogram import types
from utils.leveling import process_chat_xp, process_spending_xp

logger = logging.getLogger(__name__)

router = APIRouter(tags=["User"])

AVATAR_UPLOAD_DIR = os.path.join(PROJECT_ROOT, 'web', 'uploads', 'avatars')
os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)

def safe_serialize(data):
    if hasattr(data, "isoformat"):
        return data.isoformat()
    return str(data)

async def get_safe_servers_info():
    sanitized = {}
    for sid, sdata in SERVERS.items():
        sanitized[sid] = {
            'name': sdata.get('name', sid),
            'limits': sdata.get('limits', {})
        }
    return sanitized

@router.get("/dashboard")
async def get_user_dashboard(request: Request, user_id: int = Depends(get_current_user_id)):

    try:
        bot = request.app.state.bot 

        (
            user_profile,
            containers,
            referral_stats,
            user_role_enum,
            unread_notifs,
            tickets,
            safe_servers,
            tg_avatar_url,
            user_settings 
        ) = await asyncio.gather(
            db.get_user_profile(user_id, use_cache=False),
            db.get_user_containers(user_id),
            db.get_referral_stats(user_id),
            db.get_user_role(user_id),
            db.count_unread_notifications(user_id),
            db.get_user_tickets(user_id),
            get_safe_servers_info(),
            _get_avatar_url(bot, user_id),
            db.get_user_settings(user_id)
        )

        if not user_profile:
            raise HTTPException(status_code=404, detail="User profile not found")

        custom_avatar = await db.get_user_custom_avatar(user_id)
        final_avatar_url = custom_avatar if custom_avatar else tg_avatar_url

        status_tasks = []
        for c in containers:
            status_tasks.append(dm.get_container_status(c['server_id'], c['container_name']))

        real_statuses = await asyncio.gather(*status_tasks, return_exceptions=True)

        safe_containers = []
        for i, c in enumerate(containers):
            sid = c.get('server_id')
            tid = c.get('tariff_id')
            iid = c.get('image_id')

            status_result = real_statuses[i]
            if isinstance(status_result, Exception):
                c['status'] = 'error'
            else:
                c['status'] = status_result

            c['server_info'] = {'name': SERVERS.get(sid, {}).get('name', sid)}
            c['tariff_info'] = TARIFFS.get(tid, {'name': 'Unknown'})
            c['image_info'] = IMAGES.get(iid, {'name': 'Unknown'})
            safe_containers.append(c)

        level = user_profile.get('level', 1)
        xp = user_profile.get('xp', 0)
        next_xp = int(100 * (level ** 1.5))
        progress = min(100, int((float(xp) / max(1, next_xp)) * 100))

        dashboard_data = {
            'profile': {
                'user_id': user_id,
                'username': user_profile.get('username'),
                'first_name': user_profile.get('first_name'),
                'balance': float(user_profile.get('balance', 0)),
                'ref_balance': float(user_profile.get('ref_balance', 0)),
                'game_checks': int(user_profile.get('game_checks', 0)),
                'role_name': ROLE_NAMES.get(user_role_enum, "User"),
                'effective_role': user_role_enum.value,
                'userbots_count': len(safe_containers),
                'avatar_url': final_avatar_url,
                'is_blocked': bool(user_profile.get('is_blocked', False)), 
                'level_info': {
                    'level': level,
                    'xp': xp,
                    'next_level_xp': next_xp,
                    'progress_percent': progress
                },
                'telemetry': {
                    'ip': user_profile.get('last_ip'),
                    'country_code': user_profile.get('country_code'), 
                    'device_info': user_profile.get('device_info')
                }
            },
            'containers': safe_containers,
            'servers': safe_servers,
            'tariffs': TARIFFS,
            'images': IMAGES,
            'referral_stats': referral_stats,
            'referral_link': f"https://t.me/{bot_state.bot_info_cache.username}?start=ref_{user_id}" if bot_state.bot_info_cache else "#",
            'bonuses': {
                'discount': user_profile.get('active_discount_percent', 0),
                'deposit_bonus': user_profile.get('active_deposit_bonus_percent', 0),
                'free_container': bool(user_profile.get('has_free_container_promo'))
            },
            'unread_notifications_count': unread_notifs,
            'open_tickets_count': len([t for t in tickets if t.get('status') != 'closed']),
            'settings': user_settings
        }

        return {
            "status": "success",
            "data": dashboard_data
        }

    except Exception as e:
        logger.error(f"Dashboard Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/telemetry")
async def save_user_telemetry(
    request: Request, 
    payload: dict = Body(...), 
    user_id: int = Depends(get_current_user_id)
):
    ip = request.headers.get("X-Forwarded-For", request.client.host).split(',')[0].strip()

    country = request.headers.get("CF-IPCountry")

    device_info = payload.get('device_info', {})

    if not country or country == 'Unknown':
        country = device_info.get('client_country', 'Unknown')

    device_info['server_detected_ip'] = ip
    device_info['server_detected_country'] = country
    device_info['user_agent'] = request.headers.get("User-Agent")

    try:
        await db.update_user_telemetry(user_id, ip, country, device_info)
        return {"status": "success", "message": "Telemetry collected"}
    except Exception as e:
        logger.error(f"Telemetry save error: {e}")
        return {"status": "error", "message": "Telemetry skip"}

@router.post("/profile/avatar")
async def upload_avatar(avatar: UploadFile = File(...), user_id: int = Depends(get_current_user_id)):
    if not avatar:
        raise HTTPException(status_code=400, detail="File required")

    filename = avatar.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
        raise HTTPException(status_code=400, detail="Invalid format")

    new_filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(AVATAR_UPLOAD_DIR, new_filename)

    try:
        content = await avatar.read()
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)

        file_url = f"/uploads/avatars/{new_filename}"
        await db.set_user_custom_avatar(user_id, file_url)
        return {'status': 'success', 'message': 'Avatar updated', 'data': {'avatar_url': file_url}}
    except Exception as e:
        logging.error(f"Avatar upload error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@router.get("/notifications")
async def get_notifications(user_id: int = Depends(get_current_user_id)):
    notifications = await db.get_user_notifications(user_id)
    return {'status': 'success', 'data': notifications}

@router.get("/notifications/unread-count")
async def get_unread_notification_count(user_id: int = Depends(get_current_user_id)):
    count = await db.count_unread_notifications(user_id)
    return {'status': 'success', 'data': {'count': count}}

@router.post("/notifications/mark-read")
async def mark_notifications_as_read(user_id: int = Depends(get_current_user_id)):
    await db.mark_all_notifications_as_read(user_id)
    return {'status': 'success', 'message': 'All marked as read'}

@router.delete("/notifications/clear")
async def clear_all_notifications(user_id: int = Depends(get_current_user_id)):
    await db.delete_all_user_notifications(user_id)
    return {'status': 'success', 'message': 'All notifications deleted'}

@router.post("/settings/toggle")
async def toggle_user_setting(
    payload: dict = Body(...),
    user_id: int = Depends(get_current_user_id)
):
    key = payload.get("key")
    if not key:
        raise HTTPException(status_code=400, detail="Key required")

    await db.toggle_user_setting(user_id, key)
    return {"status": "success", "message": f"Setting {key} toggled"}

@router.post("/bonus/claim")
async def claim_daily_bonus_api(
    request: Request,
    payload: dict = Body(...),
    user_id: int = Depends(get_current_user_id)
):
    """
    Эндпоинт для получения ежедневного бонуса через Web App.
    """
    bot = request.app.state.bot
    last_claim_ts = await db.get_last_bonus_claim_time(user_id)
    cooldown_seconds = 24 * 3600
    current_ts = int(time.time())

    if current_ts - last_claim_ts < cooldown_seconds:
        remaining_seconds = cooldown_seconds - (current_ts - last_claim_ts)
        raise HTTPException(
            status_code=400, 
            detail=f"Кумаон, ещё рано! Жди {int(remaining_seconds/3600)}ч."
        )

    user_profile = await db.get_user_profile(user_id)
    level = user_profile.get('level', 1)

    prizes = [{'type': 'MONEY_BONUS', 'weight': 50, 'min_amount': 0.1, 'max_amount': 1.0}, {'type': 'TIME_BONUS', 'weight': 30, 'min_hours': 1, 'max_hours': 6}, {'type': 'NOTHING', 'weight': 20}]
    population = []
    weights = []

    for p in prizes:
        population.append(p)
        weight = p['weight']
        if p['type'] == 'NOTHING':
            weight = max(1, weight - (level * 2))
        elif p['type'] in ['MONEY_BONUS', 'TIME_BONUS']:
             weight = weight + int(level * 0.5)
        weights.append(weight)

    chosen_prize = random.choices(population, weights, k=1)[0]
    prize_type = chosen_prize['type']

    await db.set_last_bonus_claim_time(user_id, current_ts)

    await db.add_user_xp(user_id, 5)

    if prize_type == 'MONEY_BONUS':
        base_amount = random.uniform(chosen_prize['min_amount'], chosen_prize['max_amount'])
        level_multiplier = 1 + (level * 0.04) 
        amount = round(base_amount * level_multiplier, 2)
        await db.update_user_balance(user_id, amount)
        
        user_obj = types.User(id=user_id, is_bot=False, first_name=user_profile['first_name'], username=user_profile.get('username'))
        await log_action(bot, user_obj, f"получил ежедневный бонус (Web): +{amount:.2f} RUB")
        return {
            "status": "success",
            "type": "money",
            "message": f"Вы получили {amount:.2f} RUB!",
            "value": amount
        }

    elif prize_type == 'TIME_BONUS':
        
        container_id = payload.get('container_id')
        
        eligible_containers = [
            c for c in await db.get_user_containers(user_id) 
            if c.get('tariff_id') != 'free' and not c.get('is_frozen')
        ]

        duration_hours = random.randint(chosen_prize['min_hours'], chosen_prize['max_hours'])
        duration_hours += int(level / 5)

        if not eligible_containers:
             return {
                "status": "success",
                "type": "nothing",
                "message": "Выпал бонус времени, но у вас нет активных ботов :(",
                "value": 0
            }

        if len(eligible_containers) > 1 and not container_id:
             return {
                 "status": "need_selection",
                 "type": "time",
                 "message": "Выберите контейнер",
                 "duration": duration_hours,
                 "containers": eligible_containers
             }

        target_container = eligible_containers[0]
        if container_id:
            target = next((c for c in eligible_containers if c['id'] == container_id), None)
            if target: target_container = target

        await db.add_container_time(target_container['id'], duration_hours * 3600)
        
        user_obj = types.User(id=user_id, is_bot=False, first_name=user_profile['first_name'], username=user_profile.get('username'))
        await log_action(bot, user_obj, f"получил бонус времени (Web): +{duration_hours} ч. для {target_container['container_name']}")

        return {
            "status": "success",
            "type": "time",
            "message": f"+{duration_hours} часов для {target_container['container_name']}!",
            "value": duration_hours
        }

    else:
        return {
            "status": "success",
            "type": "nothing",
            "message": "Сегодня удача отвернулась...",
            "value": 0
        }
