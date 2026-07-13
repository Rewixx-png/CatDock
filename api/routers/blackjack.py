import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Body, HTTPException, Depends
from api.dependencies import get_current_user_id
import database as db
from api.game_logic.blackjack import game_manager
import json
from api.utils import _get_avatar_url
from aiogram import Bot

router = APIRouter(tags=["Blackjack"])
logger = logging.getLogger("BlackjackAPI")

@router.get("/rooms")
async def get_rooms(user_id: int = Depends(get_current_user_id)):
    return {"status": "success", "data": game_manager.get_public_rooms()}

@router.post("/rooms/create")
async def create_private_room(
    user_id: int = Depends(get_current_user_id),
    payload: dict = Body(...)
):
    name = payload.get('name')
    password = payload.get('password') 
    max_players = int(payload.get('max_players', 5))

    if max_players < 2 or max_players > 7:
        raise HTTPException(status_code=400, detail="Игроков должно быть от 2 до 7")

    room_id = game_manager.create_room(
        is_private=True, 
        name=name, 
        password=password, 
        max_players=max_players
    )
    return {"status": "success", "room_id": room_id}

@router.websocket("/ws/{room_id}")
async def blackjack_ws(
    websocket: WebSocket, 
    room_id: str, 
    token: str = Query(None), 
    password: str = Query(None) 
):
    
    await websocket.accept()

    if not token:
        logger.warning(f"[BJ] No token provided for room {room_id}")
        await websocket.close(code=4003, reason="Token required")
        return

    user_data = await db.get_user_by_web_token(token)
    if not user_data:
        logger.warning(f"[BJ] Invalid token: {token[:10]}...")
        await websocket.close(code=4003, reason="Invalid token")
        return

    user_id = user_data['user_id']
    room = game_manager.get_room(room_id)

    if not room:
        await websocket.send_json({"type": "error", "message": "Комната не найдена или удалена"})
        await websocket.close(code=1000)
        return

    if room.password and room.password != password:
        await websocket.send_json({"type": "error", "message": "Неверный пароль"})
        await websocket.close(code=4003, reason="Wrong password")
        return

    active_players = len([p for p in room.players.values() if not p.disconnected])
    if user_id not in room.players and active_players >= room.max_players:
        await websocket.send_json({"type": "error", "message": "Комната переполнена"})
        await websocket.close(code=4003, reason="Room full")
        return

    if not game_manager.bot:
        if hasattr(websocket.app.state, 'bot'):
            game_manager.init_bot(websocket.app.state.bot)
        else:
            logger.error("[BJ] Bot instance not found in app state")

    try:
        bot = websocket.app.state.bot
        avatar_url = await _get_avatar_url(bot, user_id)
        user_data['avatar_url'] = avatar_url
    except Exception as e:
        logger.error(f"[BJ] Avatar fetch error: {e}")

    await room.add_player(user_id, user_data, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get('action')

                if action == 'bet':
                    amount = float(message.get('amount', 0))
                    success, msg = await room.place_bet(user_id, amount)
                    if not success:
                        await websocket.send_json({"type": "error", "message": msg})

                elif action in ['hit', 'stand', 'double']:
                    await room.process_action(user_id, action)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"[BJ] Process error: {e}")

    except WebSocketDisconnect:
        await room.handle_disconnect(user_id)
    except Exception as e:
        logger.error(f"[BJ] WS Critical Error: {e}", exc_info=True)
        await room.handle_disconnect(user_id)
