import json
import random
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from aiogram import Bot, types

from api.dependencies import get_current_user_id
import database as db
from utils.action_logger import log_action
from utils.leveling import process_spending_xp

router = APIRouter()

CHECK_VALUE = 50.0

TOWERS_CONFIG = [
    {'cols': 4, 'bombs': 1},
    {'cols': 4, 'bombs': 1},
    {'cols': 4, 'bombs': 1},
    {'cols': 3, 'bombs': 1},
    {'cols': 3, 'bombs': 1},
    {'cols': 3, 'bombs': 1},
    {'cols': 2, 'bombs': 1},
    {'cols': 2, 'bombs': 1},
    {'cols': 2, 'bombs': 1},
]
HOUSE_EDGE = 0.04

def calculate_towers_multipliers():
    multipliers = []
    current_multi = 1.0
    for row in TOWERS_CONFIG:
        safe_prob = (row['cols'] - row['bombs']) / row['cols']
        current_multi = current_multi * (1 / safe_prob) * (1 - HOUSE_EDGE)
        multipliers.append(round(current_multi, 2))
    return multipliers

TOWERS_MULTIPLIERS = calculate_towers_multipliers()

@router.get("/towers/status")
async def towers_status(user_id: int = Depends(get_current_user_id)):
    pool = await db.get_db()
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM active_games WHERE user_id=$1 AND game_type='towers'", user_id)

        profile = await db.get_user_profile(user_id)
        checks = profile.get('game_checks', 0)

        if not game: 
            return {"status": "no_game", "checks_available": checks}

        state = json.loads(game['state'])
        is_check_game = state.get('is_check_game', False)

        if 'config' not in state or len(state['config']) != len(TOWERS_CONFIG):
             if is_check_game:
                 await db.admin_update_user_checks(user_id, 1)
             else:
                 await db.update_user_balance(user_id, game['bet_amount'])

             await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
             return {"status": "no_game", "message": "Game config updated, bet refunded.", "checks_available": checks}

        current_row = state['current_row']
        history = state.get('history', []) 

        return {
            "status": "active",
            "bet": game['bet_amount'],
            "current_row": current_row,
            "history": history,
            "multipliers": TOWERS_MULTIPLIERS,
            "current_multiplier": TOWERS_MULTIPLIERS[current_row - 1] if current_row > 0 else 1.0,
            "next_multiplier": TOWERS_MULTIPLIERS[current_row] if current_row < len(TOWERS_CONFIG) else TOWERS_MULTIPLIERS[-1],
            "config": TOWERS_CONFIG,
            "checks_available": checks,
            "is_check_game": is_check_game
        }

@router.post("/towers/start")
async def towers_start(request: Request, payload: dict = Body(...), user_id: int = Depends(get_current_user_id)):
    bot: Bot = request.app.state.bot

    use_check = payload.get('use_check', False)

    if use_check:
        bet = CHECK_VALUE
    else:
        bet = float(payload.get('bet', 10))
        if bet <= 0: raise HTTPException(status_code=400, detail="Invalid bet")

    profile = await db.get_user_profile(user_id)

    if use_check:
        if profile.get('game_checks', 0) < 1:
            raise HTTPException(status_code=402, detail="No checks available")
        await db.admin_update_user_checks(user_id, -1)
    else:
        
        if not await db.try_deduct_user_balance(user_id, bet):
             raise HTTPException(status_code=402, detail="Insufficient funds")
        
        asyncio.create_task(process_spending_xp(bot, user_id, bet))

    grid = []
    for level in TOWERS_CONFIG:
        row = [0] * level['cols']
        bomb_indices = random.sample(range(level['cols']), level['bombs'])
        for idx in bomb_indices: row[idx] = 1 
        grid.append(row)

    state = {
        'grid': grid,
        'current_row': 0, 
        'history': [],
        'config': TOWERS_CONFIG,
        'is_check_game': use_check
    }

    pool = await db.get_db()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
        await conn.execute("INSERT INTO active_games (user_id, game_type, bet_amount, state) VALUES ($1, 'towers', $2, $3)", user_id, bet, json.dumps(state))

    profile = await db.get_user_profile(user_id)
    user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])

    bet_info = "1 CHECK" if use_check else f"{bet} RUB"
    await log_action(bot, user_obj, f"🗼 <b>Towers Start</b>\nСтавка: {bet_info}", log_type="game", db_only=True)

    return {
        "status": "success", 
        "balance": profile['balance'],
        "checks": profile.get('game_checks', 0),
        "multipliers": TOWERS_MULTIPLIERS,
        "config": TOWERS_CONFIG
    }

@router.post("/towers/step")
async def towers_step(request: Request, payload: dict = Body(...), user_id: int = Depends(get_current_user_id)):
    bot: Bot = request.app.state.bot
    col_idx = int(payload.get('column'))

    pool = await db.get_db()
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM active_games WHERE user_id=$1 AND game_type='towers'", user_id)
        if not game: raise HTTPException(status_code=404, detail="No game")

        state = json.loads(game['state'])
        current_row = state['current_row']
        grid = state['grid']
        config = state['config']

        profile = await db.get_user_profile(user_id)
        user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])

        if current_row >= len(config):
             raise HTTPException(status_code=400, detail="Game finished")

        max_cols = config[current_row]['cols']
        if not (0 <= col_idx < max_cols):
             raise HTTPException(status_code=400, detail="Invalid column index")

        is_bomb = (grid[current_row][col_idx] == 1)

        if is_bomb:
            await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
            await db.add_game_history_record(user_id, 'towers', game['bet_amount'], 'loss', 'bomb', 0)

            await log_action(bot, user_obj, f"🗼 <b>Towers Loss</b>\nСтупень: {current_row+1} | Взрыв. Проигрыш: {game['bet_amount']} RUB", log_type="game", db_only=False)

            return {
                "status": "game_over", 
                "full_grid": grid, 
                "row_index": current_row,
                "col_index": col_idx
            }

        state['history'].append(col_idx)
        state['current_row'] += 1

        current_multi = TOWERS_MULTIPLIERS[current_row]
        current_win = game['bet_amount'] * current_multi

        await log_action(bot, user_obj, f"🗼 <b>Towers Step</b>\nСтупень: {current_row} пройден | Кэф: x{current_multi:.2f}", log_type="game", db_only=True)

        if state['current_row'] >= len(config):
            await db.update_user_balance(user_id, current_win)
            await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
            await db.add_game_history_record(user_id, 'towers', game['bet_amount'], 'win', 'money', current_win)
            new_bal = await db.get_user_balance(user_id)

            await log_action(bot, user_obj, f"🏆 <b>Towers TOP!</b>\nПрошел всю башню! Выигрыш: {current_win:.2f} RUB", log_type="game", db_only=False)

            return {
                "status": "win_finish",
                "win_amount": current_win,
                "balance": new_bal,
                "full_grid": grid
            }

        await conn.execute("UPDATE active_games SET state=$1 WHERE user_id=$2", json.dumps(state), user_id)

        return {
            "status": "safe",
            "current_row": state['current_row'],
            "current_multiplier": current_multi,
            "next_multiplier": TOWERS_MULTIPLIERS[state['current_row']],
            "current_win": current_win
        }

@router.post("/towers/cashout")
async def towers_cashout(request: Request, user_id: int = Depends(get_current_user_id)):
    bot: Bot = request.app.state.bot
    pool = await db.get_db()
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM active_games WHERE user_id=$1 AND game_type='towers'", user_id)
        if not game: raise HTTPException(status_code=404)

        state = json.loads(game['state'])
        current_row = state['current_row']
        is_check_game = state.get('is_check_game', False)

        profile = await db.get_user_profile(user_id)
        user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])

        if current_row == 0:
             if is_check_game:
                 await db.admin_update_user_checks(user_id, 1)
                 refund_msg = "1 CHECK"
             else:
                 await db.update_user_balance(user_id, game['bet_amount'])
                 refund_msg = f"{game['bet_amount']} RUB"

             await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
             await log_action(bot, user_obj, f"🗼 <b>Towers Refund</b>\nОтменил игру.", log_type="game", db_only=True)

             new_profile = await db.get_user_profile(user_id)
             return {
                 "status": "success", 
                 "win_amount": game['bet_amount'] if not is_check_game else 0, 
                 "balance": new_profile['balance'], 
                 "checks": new_profile.get('game_checks', 0),
                 "full_grid": state['grid']
             }

        win_multi = TOWERS_MULTIPLIERS[current_row - 1]
        win_amount = game['bet_amount'] * win_multi

        await db.update_user_balance(user_id, win_amount)
        await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
        await db.add_game_history_record(user_id, 'towers', game['bet_amount'], 'win', 'money', win_amount)

        await log_action(bot, user_obj, f"💰 <b>Towers Cashout</b>\nЗабрал на {current_row} ступени. Сумма: {win_amount:.2f} RUB", log_type="game", db_only=False)

        new_bal = await db.get_user_balance(user_id)
        return {"status": "success", "win_amount": win_amount, "balance": new_bal, "full_grid": state['grid']}
