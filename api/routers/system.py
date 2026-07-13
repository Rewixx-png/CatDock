import os
import asyncio
import logging
import json
import re
import shlex
from contextlib import asynccontextmanager
from fastapi import APIRouter, WebSocket, Query, HTTPException, Request, UploadFile, File, Body
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketDisconnect

from config import PROJECT_ROOT, IMAGES, TARIFFS
import database as db
from roles import UserRole
from utils.ssh_runner import _get_ssh_connection
from utils import bot_state
import utils.docker as dm
from utils.worker_tasks import task_change_image

router = APIRouter(tags=["System"])
SESSION_FILE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MAX_SESSION_SIZE = 16 * 1024 * 1024


@asynccontextmanager
async def _open_terminal_process(server_id: str, command: str | None):
    """Open an interactive process on either a local or SSH-backed node."""
    server_config = bot_state.servers_cache.get(server_id, {})
    if server_config.get('local') or server_config.get('is_local'):
        local_command = command or f"{shlex.quote(os.environ.get('SHELL', '/bin/sh'))} -i"
        local_command = local_command.replace("docker exec -it ", "docker exec -i ", 1)
        process = await asyncio.create_subprocess_shell(
            local_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, 'TERM': 'xterm'},
        )
        try:
            yield process
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        return

    async with await _get_ssh_connection(server_id) as connection:
        process = await connection.create_process(
            command,
            term_type='xterm',
            term_size=(80, 24),
        )
        try:
            yield process
        finally:
            try:
                process.terminate()
            except Exception:
                pass

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "CatDock API Terminal"}

@router.get("/terminal", response_class=HTMLResponse)
async def get_terminal_page(token: str = Query(...)):
    terminal_path = os.path.join(PROJECT_ROOT, "terminal.html")
    if not os.path.exists(terminal_path):
        raise HTTPException(status_code=404, detail="Terminal template not found")
    with open(terminal_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


def _request_token(request: Request, query_token: str | None) -> str | None:
    return query_token or request.headers.get("X-Web-Access-Token")


async def _get_authorized_container(token: str | None, container_id: int) -> dict:
    """Authorize either a normal web token or a 30-minute container token."""
    if not token:
        raise HTTPException(status_code=403, detail="Token required")

    user_data = await db.get_user_by_web_token(token)
    if user_data:
        container = await db.get_container_by_id(container_id)
        if not container:
            raise HTTPException(status_code=404, detail="Container not found")
        user_id = user_data['user_id']
        user_role = await db.get_user_role(user_id)
        if container['user_id'] != user_id and (user_role is None or user_role < UserRole.ADMIN):
            raise HTTPException(status_code=403, detail="Access denied")
        return container

    token_container = await db.get_container_by_log_token(token)
    if not token_container or token_container['id'] != container_id:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return token_container


@router.get("/images")
async def get_terminal_images(request: Request, token: str | None = Query(None)):
    access_token = _request_token(request, token)
    if not access_token:
        raise HTTPException(status_code=403, detail="Token required")
    if not await db.get_user_by_web_token(access_token) and not await db.get_container_by_log_token(access_token):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return {
        "status": "success",
        "data": [
            {"id": image_id, "name": image_data['name']}
            for image_id, image_data in IMAGES.items()
        ],
    }


@router.get("/container/{container_id}/health")
async def get_container_health(
    container_id: int,
    request: Request,
    token: str | None = Query(None),
):
    container = await _get_authorized_container(_request_token(request, token), container_id)
    status, stats, session_status = await asyncio.gather(
        dm.get_container_status(container['server_id'], container['container_name']),
        dm.get_container_stats(container['server_id'], container['container_name']),
        dm.get_session_status(container['server_id'], container['container_name'], container['image_id']),
        return_exceptions=True,
    )
    if isinstance(status, Exception):
        status = "error"
    if isinstance(stats, Exception) or stats is None:
        stats = {}
    if isinstance(session_status, Exception):
        session_status = "error"
    return {
        "status": "success",
        "data": {
            "container_id": container_id,
            "container_name": container['container_name'],
            "server_id": container['server_id'],
            "image_id": container['image_id'],
            "container_status": status,
            "session_status": session_status,
            "stats": stats,
            "frozen": bool(container.get('is_frozen')),
            "blocked": bool(container.get('is_blocked')),
        },
    }


@router.get("/container/{container_id}/logs")
async def get_terminal_logs(
    container_id: int,
    request: Request,
    token: str | None = Query(None),
    lines: int = Query(200, ge=10, le=2000),
):
    container = await _get_authorized_container(_request_token(request, token), container_id)
    logs = await dm.get_container_logs(container['server_id'], container['container_name'], lines)
    if logs is None:
        raise HTTPException(status_code=502, detail="Container logs are unavailable")
    return {"status": "success", "data": logs}


@router.post("/container/{container_id}/restart")
async def restart_terminal_container(
    container_id: int,
    request: Request,
    token: str | None = Query(None),
):
    container = await _get_authorized_container(_request_token(request, token), container_id)
    if container.get('is_frozen') or container.get('is_blocked'):
        raise HTTPException(status_code=409, detail="Container is frozen or blocked")
    result = await dm.restart_container(container['server_id'], container['container_name'])
    if getattr(result, 'exit_status', 0) != 0:
        raise HTTPException(status_code=502, detail=getattr(result, 'stderr', 'Restart failed'))
    return {"status": "success", "message": "Container restarted"}


@router.post("/container/{container_id}/session")
async def upload_container_session(
    container_id: int,
    request: Request,
    session_file: UploadFile = File(...),
    token: str | None = Query(None),
):
    container = await _get_authorized_container(_request_token(request, token), container_id)
    uploaded_filename = os.path.basename(session_file.filename or "")
    if not SESSION_FILE_RE.fullmatch(uploaded_filename):
        raise HTTPException(status_code=400, detail="Only *.session or session.string files are allowed")
    if uploaded_filename.endswith('.session'):
        filename = uploaded_filename
    elif uploaded_filename.endswith('.string'):
        filename = 'session.string'
    else:
        raise HTTPException(status_code=400, detail="Only *.session or *.string files are allowed")

    content = await session_file.read(MAX_SESSION_SIZE + 1)
    if not content or len(content) > MAX_SESSION_SIZE:
        raise HTTPException(status_code=413, detail="Session file is empty or larger than 16 MB")
    if filename.endswith('.session') and not content.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400, detail="Invalid SQLite session file")

    server_id = container['server_id']
    container_name = container['container_name']
    remote_dir = f"/var/lib/catdock/containers/{container_name}/data"
    remote_path = f"{remote_dir}/{filename}"
    server_config = bot_state.servers_cache.get(server_id, {})
    was_running = await dm.get_container_status(server_id, container_name) == 'running'

    if was_running:
        await dm.stop_container(server_id, container_name)
    try:
        if server_config.get('local') or server_config.get('is_local'):
            os.makedirs(remote_dir, exist_ok=True)
            with open(remote_path, 'wb') as local_file:
                local_file.write(content)
        else:
            async with await _get_ssh_connection(server_id) as conn:
                await conn.run(f"mkdir -p {shlex.quote(remote_dir)}", check=True)
                async with conn.start_sftp_client() as sftp:
                    async with sftp.open(remote_path, 'wb') as remote_file:
                        await remote_file.write(content)
    finally:
        if was_running:
            await dm.start_container(server_id, container_name)

    return {"status": "success", "message": f"Session {filename} uploaded"}


@router.post("/container/{container_id}/image", status_code=202)
async def change_terminal_image(
    container_id: int,
    request: Request,
    payload: dict = Body(...),
    token: str | None = Query(None),
):
    container = await _get_authorized_container(_request_token(request, token), container_id)
    image_id = payload.get('image_id')
    if image_id not in IMAGES:
        raise HTTPException(status_code=400, detail="Unknown image")
    if image_id == container['image_id']:
        return {"status": "success", "message": "Image is already selected"}
    if container.get('is_frozen') or container.get('is_blocked'):
        raise HTTPException(status_code=409, detail="Container is frozen or blocked")

    owner = await db.get_user_profile(container['user_id']) or {}
    tariff_id = container['tariff_id'] if container['tariff_id'] in TARIFFS else 'basic'
    await task_change_image.kiq(
        chat_id=container['user_id'],
        user_id=container['user_id'],
        first_name=owner.get('first_name', 'User'),
        container_id=container_id,
        server_id=container['server_id'],
        container_name=container['container_name'],
        old_image_name=IMAGES.get(container['image_id'], {}).get('name', container['image_id']),
        new_image_id=image_id,
        tariff_id=tariff_id,
        external_port=container['external_port'],
    )
    return {"status": "accepted", "message": "Image change queued", "image_id": image_id}


@router.websocket("/ws")
async def terminal_websocket_handler(
    websocket: WebSocket, 
    token: str = Query(None), 
    container_id: int = Query(None),
    server_id: str = Query(None)
):
    await websocket.accept()

    if not token:
        await websocket.close(code=4003, reason="Token required")
        return

    target_server_id = None
    command = None

    try:
        if container_id:
            try:
                container = await _get_authorized_container(token, container_id)
            except HTTPException as exc:
                await websocket.close(code=4003, reason=str(exc.detail))
                return
            target_server_id = container['server_id']
            command = f"export TERM=xterm; docker exec -it {shlex.quote(container['container_name'])} /bin/sh"

        elif server_id:
            user_data = await db.get_user_by_web_token(token)
            if not user_data:
                await websocket.close(code=4003, reason="Invalid token")
                return
            user_role = await db.get_user_role(user_data['user_id'])
            is_owner = user_role >= UserRole.CO_OWNER
            if not is_owner:
                await websocket.close(code=4003, reason="Access denied")
                return
            target_server_id = server_id
            command = None 
        else:
            await websocket.close(code=4000, reason="Missing target")
            return

        await websocket.send_json({"type": "output", "data": f"\r\nConnecting to {target_server_id}...\r\n"})

        async with _open_terminal_process(target_server_id, command) as process:
            await websocket.send_json({"type": "output", "data": f"Connected!\r\n"})

            async def read_from_ssh(stream):
                try:
                    while not stream.at_eof():
                        data = await stream.read(4096)
                        if data:
                            text = data if isinstance(data, str) else data.decode('utf-8', errors='replace')
                            await websocket.send_json({"type": "output", "data": text})
                        else:
                            await asyncio.sleep(0.01)
                except Exception:
                    pass

            read_tasks = [
                asyncio.create_task(read_from_ssh(process.stdout)),
                asyncio.create_task(read_from_ssh(process.stderr)),
            ]

            try:
                while True:
                    message = await websocket.receive_text()
                    try:
                        msg_json = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    if msg_json.get('type') == 'input':
                        input_data = msg_json.get('data', '')
                        try:
                            process.stdin.write(input_data)
                        except TypeError:
                            process.stdin.write(input_data.encode('utf-8'))
                    elif msg_json.get('type') == 'resize':
                        if hasattr(process, 'set_terminal_size'):
                            process.set_terminal_size(msg_json.get('cols', 80), msg_json.get('rows', 24))
            except WebSocketDisconnect:
                pass
            finally:
                for task in read_tasks:
                    task.cancel()

    except Exception as e:
        logging.error(f"WS Error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
