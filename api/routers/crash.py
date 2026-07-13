from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, Body, HTTPException
from api.dependencies import get_current_user_id
import database as db
from api.game_logic.crash import crash_game
import json
import logging

router = APIRouter(tags=["Crash"])

@router.websocket("/ws")
async def crash_ws(websocket: WebSocket, token: str = Query(...)):
    await websocket.accept()

    user_data = await db.get_user_by_web_token(token)
    if not user_data:
        await websocket.close(code=4003)
        return

    user_id = user_data['user_id']

    if not crash_game.bot:
        crash_game.init_bot(websocket.app.state.bot)

    await crash_game.add_player(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get('action')

            if action == 'bet':
                amount = float(msg.get('amount', 0))
                auto_cashout = float(msg.get('auto_cashout', 0)) 
                if amount > 0:
                    success, text = await crash_game.place_bet(user_id, amount, auto_cashout)
                    await websocket.send_json({"type": "action_result", "success": success, "message": text})

            elif action == 'cashout':
                success, val = await crash_game.cashout(user_id)
                if not success:
                    await websocket.send_json({"type": "action_result", "success": False, "message": str(val)})

    except WebSocketDisconnect:
        if user_id in crash_game.players:
            crash_game.players[user_id]['ws'] = None
    except Exception as e:
        logging.error(f"Crash WS Error: {e}")
