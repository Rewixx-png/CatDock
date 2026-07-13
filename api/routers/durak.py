import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from api.dependencies import get_current_user_id
import database as db
from api.game_logic.durak import durak_manager
import json
from api.utils import _get_avatar_url
from aiogram import Bot

router = APIRouter(tags=["Durak"])
logger = logging.getLogger("DurakAPI")

@router.get("/rooms")
async def get_rooms(user_id: int = Depends(get_current_user_id)):
    """Получение списка публичных комнат через REST."""
    return {"status": "success", "data": durak_manager.get_public_rooms()}

@router.get("/active-session")
async def check_active_session(user_id: int = Depends(get_current_user_id)):
    """Проверяет, находится ли игрок уже в игре."""
    room_id = durak_manager.find_player_room(user_id)
    if room_id:
        return {"status": "success", "room_id": room_id}
    return {"status": "success", "room_id": None}

@router.post("/rooms/create")
async def create_room(
    user_id: int = Depends(get_current_user_id),
    payload: dict = Body(...)
):
    try:
        bet = float(payload.get('bet', 10))
        players = int(payload.get('players', 2))
        password = payload.get('password')
        deck_size = int(payload.get('deck_size', 24))
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат данных")

    if bet < 10: 
        raise HTTPException(status_code=400, detail="Мин ставка 10 RUB")
    if players < 2 or players > 6: 
        raise HTTPException(status_code=400, detail="Игроков от 2 до 6")
    if deck_size not in [24, 36, 52]: 
        raise HTTPException(status_code=400, detail="Колода может быть 24, 36 или 52 карты")

    if durak_manager.find_player_room(user_id):
        raise HTTPException(status_code=400, detail="Вы уже находитесь в игре!")

    room_id = durak_manager.create_room(
        bet=bet, max_players=players, is_private=True, password=password, deck_size=deck_size
    )
    return {"status": "success", "room_id": room_id}

@router.post("/rooms/create_pve")
async def create_pve_room(
    user_id: int = Depends(get_current_user_id),
    payload: dict = Body(...)
):
    try:
        bet = float(payload.get('bet', 10))
        deck_size = int(payload.get('deck_size', 24))
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат данных")
    
    if bet < 10: 
        raise HTTPException(status_code=400, detail="Мин ставка 10 RUB")
    
    if deck_size not in [24, 36, 52]: 
        raise HTTPException(status_code=400, detail="Колода может быть 24, 36 или 52 карты")

    if durak_manager.find_player_room(user_id):
        raise HTTPException(status_code=400, detail="Вы уже находитесь в игре!")
    
    room_id = durak_manager.create_room(
        bet=bet, max_players=2, is_private=True, deck_size=deck_size, is_pve=True
    )
    return {"status": "success", "room_id": room_id}

@router.websocket("/ws/lobby")
async def durak_lobby_ws(websocket: WebSocket):
    await durak_manager.connect_lobby(websocket)

@router.get("/ws/lobby")
async def durak_lobby_http_fallback():
    return JSONResponse(status_code=426, content={"status": "error", "message": "Upgrade Required"})

@router.websocket("/ws/{room_id}")
async def durak_ws(
    websocket: WebSocket, 
    room_id: str, 
    token: str = Query(None), 
    password: str = Query(None)
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
    room = durak_manager.get_room(room_id)

    if not room:
        await websocket.send_json({"type": "error", "message": "Комната не найдена"})
        await websocket.close(code=1000)
        return

    if room.password and room.password != password:
        
        player_in_room = next((p for p in room.players if p.user_id == user_id), None)
        if not player_in_room:
            await websocket.send_json({"type": "error", "message": "Неверный пароль"})
            await websocket.close(code=4003, reason="Wrong password")
            return

    if not durak_manager.bot:
        if hasattr(websocket.app.state, 'bot'):
            durak_manager.init_bot(websocket.app.state.bot)

    try:
        bot = websocket.app.state.bot
        avatar_url = await _get_avatar_url(bot, user_id)
        user_data['avatar_url'] = avatar_url
    except Exception: 
        pass

    await room.add_player(user_id, user_data, websocket)
    asyncio.create_task(durak_manager.broadcast_lobby())

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get('action')
                if action in ['attack', 'defend']:
                    cards_data = msg.get('cards_data')
                    await room.process_move(user_id, action, cards_data=cards_data)
                elif action in ['pass', 'take', 'surrender', 'finish_turn']:
                    await room.process_move(user_id, action)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"Error processing move: {e}")

    except WebSocketDisconnect:
        await room.handle_disconnect(user_id)
        asyncio.create_task(durak_manager.broadcast_lobby())
    except Exception as e:
        logger.error(f"WS Critical Error: {e}", exc_info=True)
        await room.handle_disconnect(user_id)
        asyncio.create_task(durak_manager.broadcast_lobby())

@router.get("/ws/{room_id}")
async def durak_game_http_fallback(room_id: str):
    return JSONResponse(status_code=426, content={"status": "error", "message": "Upgrade Required"})
