import os
import asyncio
import logging
import json
from fastapi import APIRouter, WebSocket, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketDisconnect

from config import PROJECT_ROOT
import database as db
from roles import UserRole
from utils.ssh_runner import _get_ssh_connection

router = APIRouter(tags=["System"])

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "CatDock API Terminal"}

@router.get("/routes", include_in_schema=True)
async def get_all_routes(request: Request):
    """
    Debug Endpoint: Показывает все зарегистрированные маршруты в FastAPI.
    Помогает диагностировать 404 ошибки.
    """
    url_list = [
        {"path": route.path, "name": route.name, "methods": list(route.methods) if hasattr(route, 'methods') else None}
        for route in request.app.routes
    ]
    return {"status": "success", "routes": url_list}

@router.get("/terminal", response_class=HTMLResponse)
async def get_terminal_page(token: str = Query(...)):
    terminal_path = os.path.join(PROJECT_ROOT, "terminal.html")
    if not os.path.exists(terminal_path):
        raise HTTPException(status_code=404, detail="Terminal template not found")
    with open(terminal_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

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

    user_data = await db.get_user_by_web_token(token)
    if not user_data:
        await websocket.close(code=4003, reason="Invalid token")
        return

    user_id = user_data['user_id']
    user_role = await db.get_user_role(user_id)
    is_admin = user_role >= UserRole.ADMIN
    is_owner = user_role >= UserRole.CO_OWNER

    target_server_id = None
    command = None

    try:
        if container_id:
            container = await db.get_container_by_id(container_id)
            if not container:
                await websocket.close(code=4004, reason="Container not found")
                return
            if container['user_id'] != user_id and not is_admin:
                await websocket.close(code=4003, reason="Access denied")
                return
            target_server_id = container['server_id']
            command = f"export TERM=xterm; docker exec -it {container['container_name']} /bin/bash"

        elif server_id:
            if not is_owner:
                await websocket.close(code=4003, reason="Access denied")
                return
            target_server_id = server_id
            command = None 
        else:
            await websocket.close(code=4000, reason="Missing target")
            return

        await websocket.send_json({"type": "output", "data": f"\r\nConnecting to {target_server_id}...\r\n"})

        async with await _get_ssh_connection(target_server_id) as conn:
            process = await conn.create_process(command, term_type='xterm', term_size=(80, 24))
            await websocket.send_json({"type": "output", "data": f"Connected!\r\n"})

            async def read_from_ssh():
                try:
                    while not process.stdout.at_eof():
                        data = await process.stdout.read(4096)
                        if data:
                            text = data if isinstance(data, str) else data.decode('utf-8', errors='replace')
                            await websocket.send_json({"type": "output", "data": text})
                        else:
                            await asyncio.sleep(0.01)
                except Exception:
                    pass

            read_task = asyncio.create_task(read_from_ssh())

            try:
                while True:
                    message = await websocket.receive_text()
                    msg_json = json.loads(message)
                    if msg_json['type'] == 'input':
                        process.stdin.write(msg_json['data'])
                    elif msg_json['type'] == 'resize':
                        process.set_terminal_size(msg_json.get('cols', 80), msg_json.get('rows', 24))
            except WebSocketDisconnect:
                pass
            finally:
                read_task.cancel()
                try: process.terminate()
                except: pass

    except Exception as e:
        logging.error(f"WS Error: {e}", exc_info=True)
        try: await websocket.close(code=1011)
        except: pass
