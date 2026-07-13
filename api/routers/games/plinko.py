import random
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from aiogram import Bot, types

from api.dependencies import get_current_user_id
import database as db
from api.game_logic.plinko.constants import MULTIPLIERS
from utils.action_logger import log_action
from utils.leveling import process_spending_xp

router = APIRouter(tags=["Plinko"])

@router.post("/play")
async def plinko_play(
    request: Request,
    payload: dict = Body(...),
    user_id: int = Depends(get_current_user_id)
):
    try:
        bet_per_ball = float(payload.get('bet', 10))
        rows = int(payload.get('rows', 16))
        risk = payload.get('risk', 'medium')
        balls_count = int(payload.get('balls', 1))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid input")

    if bet_per_ball <= 0:
        raise HTTPException(status_code=400, detail="Invalid bet")

    if rows not in [8, 10, 12, 14, 16]:
        raise HTTPException(status_code=400, detail="Invalid rows count")

    if risk not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=400, detail="Invalid risk level")

    if balls_count < 1 or balls_count > 100:
        raise HTTPException(status_code=400, detail="Balls count must be between 1 and 100")

    total_bet = bet_per_ball * balls_count

    if not await db.try_deduct_user_balance(user_id, total_bet):
        raise HTTPException(status_code=402, detail=f"Insufficient funds. Need {total_bet:.2f} RUB")

    profile = await db.get_user_profile(user_id)
    bot: Bot = request.app.state.bot
    asyncio.create_task(process_spending_xp(bot, user_id, total_bet))

    multipliers_row = MULTIPLIERS.get((rows, risk))
    if not multipliers_row:
        
        await db.update_user_balance(user_id, total_bet)
        raise HTTPException(status_code=500, detail="Config error")

    results = []
    total_win = 0.0

    for _ in range(balls_count):
        
        path = [random.choice([0, 1]) for _ in range(rows)]
        destination_index = sum(path)

        multiplier = multipliers_row[destination_index]
        win = bet_per_ball * multiplier

        total_win += win

        results.append({
            "path": path,
            "multiplier": multiplier,
            "win": win
        })

    if total_win > 0:
        await db.update_user_balance(user_id, total_win)

    result_status = 'win' if total_win > total_bet else ('loss' if total_win < total_bet else 'draw')
    await db.add_game_history_record(user_id, f'plinko_x{balls_count}', total_bet, result_status, 'money', total_win)

    if total_win >= total_bet * 10 and total_bet > 100:
        user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])
        await log_action(bot, user_obj, f"💰 <b>Plinko Series Win!</b>\nШаров: {balls_count} | Ставка: {total_bet:.2f} | Выигрыш: {total_win:.2f}", log_type="game", db_only=False)

    new_balance = await db.get_user_balance(user_id)

    return {
        "status": "success",
        "results": results,
        "total_win": total_win,
        "balance": new_balance
    }
