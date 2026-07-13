import hashlib
import hmac
import base64
import logging
import asyncio
import os
import time
import aiohttp
from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from aiogram import Bot
from pydantic import BaseModel

from config import get_bot_username, get_version, TOKEN, TARIFFS, IMAGES, SERVERS, PROJECT_ROOT, WEB_APP_URL
from database.user.api_tokens import create_api_token
import database as db
import utils.docker as dm
from utils import bot_state

from api.schemas import (
    VersionResponse, ServerStatusResponse, SystemHealthResponse, 
    UserPhotoResponse, VerifyResponse, LogsDataResponse
)

router = APIRouter(tags=["Public"])

@router.get("/logs/data/{token}", response_model=LogsDataResponse, summary="Данные логов")
async def get_logs_by_token(token: str):
    try:
        container = await db.get_container_by_log_token(token)
        if not container:
            
            raise HTTPException(status_code=404, detail="Ссылка устарела или недействительна")

        try:
            
            logs = await asyncio.wait_for(
                dm.get_container_logs(container['server_id'], container['container_name'], 2000),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logs = "⚠️ Timeout: Сервер долго не отвечает. Попробуйте позже."
        except Exception as e:
            logs = f"⚠️ Ошибка получения логов: {str(e)}"

        if logs is None:
            logs = "⚠️ Логи пустые или контейнер недоступен."

        return {
            "status": "success", 
            "data": logs,
            "meta": {
                "container_name": container['container_name'],
                "server_id": container['server_id']
            }
        }
    except HTTPException: 
        raise
    except Exception as e:
        logging.error(f"Logs Error: {e}")
        return {
            "status": "error",
            "data": f"Server Error: {str(e)}",
            "meta": {"container_name": "Unknown", "server_id": "Unknown"}
        }

@router.get("/install", include_in_schema=False)
async def get_termux_installer():
    script_path = os.path.join(PROJECT_ROOT, 'web', 'static', 'scripts', 'termux_install.sh')
    if os.path.exists(script_path):
        return FileResponse(script_path, media_type='text/x-shellscript', filename='install.sh')
    return "Script not found", 404

class ClientLogRequest(BaseModel):
    level: str
    message: str
    context: str = "Frontend"

@router.post("/client-log")
async def log_client_error(payload: ClientLogRequest):
    log_msg = f"🖥️ [CLIENT-SIDE {payload.level.upper()}] {payload.context}: {payload.message}"
    if payload.level == 'error': logging.error(log_msg)
    elif payload.level == 'warn': logging.warning(log_msg)
    else: logging.info(log_msg)
    return {"status": "ok"}

@router.get("/version", response_model=VersionResponse)
async def get_app_version():
    version, bot_username = await asyncio.gather(asyncio.to_thread(get_version), asyncio.to_thread(get_bot_username))
    return {"version": version, "bot_username": bot_username}

@router.get("/server_status", response_model=ServerStatusResponse)
async def get_server_status_list():
    if not bot_state.server_statuses_cache:
        return {"status": "pending", "data": [], "meta": {"last_updated": 0, "update_interval": 60}}
    return {"status": "success", "data": bot_state.server_statuses_cache, "meta": {"last_updated": bot_state.server_status_last_update, "update_interval": 60}}

@router.get("/system_health", response_model=SystemHealthResponse)
async def get_system_health():
    start_time = time.time()
    db_status = "offline"
    db_latency = 0
    try:
        db_start = time.time()
        pool = await db.get_db()
        async with pool.acquire() as conn: await conn.fetchval("SELECT 1")
        db_end = time.time()
        db_status = "online"
        db_latency = round((db_end - db_start) * 1000, 2)
    except Exception: db_status = "error"
    return {"status": "success", "data": {"api": {"status": "online", "latency": round((time.time() - start_time) * 1000, 2)}, "database": {"status": db_status, "latency": db_latency}}}

@router.get("/user_photo/{user_id}")
async def proxy_user_photo(user_id: int, request: Request):
    bot: Bot = request.app.state.bot
    try:
        custom_avatar_path = await db.get_user_custom_avatar(user_id)
        if custom_avatar_path: return RedirectResponse(custom_avatar_path)
    except: pass
    try:
        profile_photos = await bot.get_user_profile_photos(user_id, limit=1)
        if not (profile_photos and profile_photos.photos): return RedirectResponse("https://ui-avatars.com/api/?name=User&background=3b82f6&color=fff&size=150")
        file = await bot.get_file(profile_photos.photos[0][0].file_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}") as resp:
                if resp.status == 200: return Response(content=await resp.read(), media_type="image/jpeg")
    except: pass
    return RedirectResponse("https://ui-avatars.com/api/?name=Error&background=red&color=fff")

@router.get("/telegram-auth", response_class=HTMLResponse, include_in_schema=False)
async def handle_telegram_auth(request: Request):
    try:
        params = dict(request.query_params)
        if 'hash' not in params: return RedirectResponse(f'{WEB_APP_URL}/index.html?error=NoHash')
        check_hash = params.pop('hash')
        data_check_string = "\n".join(sorted([f"{k}={v}" for k, v in params.items()]))
        secret_key = hashlib.sha256(TOKEN.encode()).digest()
        if hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest() != check_hash: return RedirectResponse(f'{WEB_APP_URL}/index.html?error=InvalidHash')
        user_id = int(params['id'])
        await db.add_user(user_id, params.get('username'), params.get('first_name', ''))
        api_key = await create_api_token(user_id)
        return HTMLResponse(content=f"<script>localStorage.setItem('catDockApiKey', '{api_key}'); window.location.replace('/profile');</script>")
    except: return RedirectResponse(f'{WEB_APP_URL}/index.html?error=ServerError')

@router.get("/verify-free-request/{token}", response_model=VerifyResponse)
async def verify_free_request(token: str, request: Request):
    bot_username = await asyncio.to_thread(get_bot_username)
    container_name = None
    user_id = None
    try:
        token_data, reserve_status = await db.reserve_free_verification_token(token)
        if reserve_status == 'already_exists':
            return {"status": "success", "message": "У вас уже есть контейнер.", "bot_username": bot_username}
        if not token_data:
            return {"status": "error", "message": "Ссылка недействительна или Free уже использован.", "bot_username": bot_username}

        user_id = token_data['user_id']
        server_id = token_data['server_id']
        tariff_id = token_data['tariff_id']
        image_id = token_data['image_id']
        if server_id not in SERVERS or tariff_id != 'free' or image_id not in IMAGES:
            await db.release_free_verification_token(token, user_id)
            raise HTTPException(status_code=400, detail="Invalid verification parameters")

        container_name, app_port, login_url = await dm.create_container(
            user_id,
            token_data['username'],
            server_id,
            TARIFFS[tariff_id],
            IMAGES[image_id],
        )
        if not container_name: raise Exception("Docker Error")
        await db.add_user_container(user_id, server_id, container_name, image_id, tariff_id, app_port, login_url)
        client_host = request.client.host if request.client else "unknown"
        await db.set_user_verified_ip(user_id, request.headers.get('x-forwarded-for', client_host))
        return {"status": "success", "message": f"UserBot '{container_name}' создан!", "bot_username": bot_username}
    except HTTPException:
        raise
    except Exception:
        if container_name and user_id is not None:
            try:
                token_data = token_data if 'token_data' in locals() else None
                if token_data:
                    await dm.delete_container(token_data['server_id'], container_name)
            except Exception:
                pass
        if user_id is not None:
            await db.release_free_verification_token(token, user_id)
        logging.exception("Free verification failed")
        raise HTTPException(status_code=500, detail="Verification failed")
