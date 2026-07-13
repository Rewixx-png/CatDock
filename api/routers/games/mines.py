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

def calculate_mines_multiplier(mines: int, diamonds_found: int) -> float:
    if diamonds_found == 0: return 1.0
    prob = 1.0
    for i in range(diamonds_found):
        prob *= (25 - mines - i) / (25 - i)
    if prob == 0: return 0
    return round(0.95 / prob, 2)

@router.get("/mines/status")
async def mines_status(user_id: int = Depends(get_current_user_id)):
    pool = await db.get_db()
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM active_games WHERE user_id=$1 AND game_type='mines'", user_id)

        profile = await db.get_user_profile(user_id)
        checks = profile.get('game_checks', 0)

        if not game: 
            return {"status": "no_game", "checks_available": checks}

        state = json.loads(game['state'])
        mines = state['mines_count']
        opened = len(state['revealed'])
        current_multi = calculate_mines_multiplier(mines, opened)
        next_multi = calculate_mines_multiplier(mines, opened + 1)

        is_check_game = state.get('is_check_game', False)

        return {
            "status": "active", 
            "bet": game['bet_amount'], 
            "revealed": state['revealed'], 
            "mines": mines, 
            "multiplier": current_multi, 
            "current_win": game['bet_amount'] * current_multi, 
            "next_multiplier": next_multi,
            "checks_available": checks,
            "is_check_game": is_check_game
        }

@router.post("/mines/start")
async def mines_start(request: Request, payload: dict = Body(...), user_id: int = Depends(get_current_user_id)):
    bot: Bot = request.app.state.bot

    use_check = payload.get('use_check', False) 

    if use_check:
        bet = CHECK_VALUE 
    else:
        bet = float(payload.get('bet', 10))
        if bet <= 0: raise HTTPException(status_code=400, detail="Invalid bet")

    mines = int(payload.get('mines', 3))
    if not (1 <= mines <= 24): raise HTTPException(status_code=400, detail="Invalid mines count")

    profile = await db.get_user_profile(user_id)

    if use_check:
        if profile.get('game_checks', 0) < 1:
            raise HTTPException(status_code=402, detail="No checks available")
        await db.admin_update_user_checks(user_id, -1)
    else:
        
        if not await db.try_deduct_user_balance(user_id, bet):
             raise HTTPException(status_code=402, detail="Insufficient funds")
        
        asyncio.create_task(process_spending_xp(bot, user_id, bet))

    grid = [0]*25
    mine_indices = random.sample(range(25), mines)
    for i in mine_indices: grid[i] = 1

    state = {
        'grid': grid, 
        'revealed': [], 
        'mines_count': mines,
        'is_check_game': use_check 
    }

    pool = await db.get_db()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id) 
        await conn.execute("INSERT INTO active_games (user_id, game_type, bet_amount, state) VALUES ($1, 'mines', $2, $3)", user_id, bet, json.dumps(state))

    profile = await db.get_user_profile(user_id) 
    user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])

    bet_info = "1 CHECK" if use_check else f"{bet} RUB"
    await log_action(bot, user_obj, f"💣 <b>Mines Start</b>\nСтавка: {bet_info} | Мин: {mines}", log_type="game", db_only=True)

    return {"status": "success", "balance": profile['balance'], "checks": profile.get('game_checks', 0)}

@router.post("/mines/click")
async def mines_click(request: Request, payload: dict = Body(...), user_id: int = Depends(get_current_user_id)):
    bot: Bot = request.app.state.bot
    idx = int(payload.get('index'))
    pool = await db.get_db()
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM active_games WHERE user_id=$1 AND game_type='mines'", user_id)
        if not game: raise HTTPException(status_code=404, detail="No game")

        state = json.loads(game['state'])
        if idx in state['revealed']: raise HTTPException(status_code=400, detail="Clicked")

        profile = await db.get_user_profile(user_id)
        user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])

        if state['grid'][idx] == 1:
            await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
            await db.add_game_history_record(user_id, 'mines', game['bet_amount'], 'loss', 'bomb', 0)
            await log_action(bot, user_obj, f"💣 <b>Mines Loss</b>\nВзрыв на клетке {idx}. Проигрыш: {game['bet_amount']} RUB", log_type="game", db_only=False)
            return {"status": "game_over", "grid": state['grid'], "message": "BOOM!"}

        state['revealed'].append(idx)
        await conn.execute("UPDATE active_games SET state=$1 WHERE user_id=$2", json.dumps(state), user_id)

        mines = state['mines_count']
        opened = len(state['revealed'])
        multi = calculate_mines_multiplier(mines, opened)
        next_multi = calculate_mines_multiplier(mines, opened + 1)
        win = game['bet_amount'] * multi

        await log_action(bot, user_obj, f"💣 <b>Mines Step</b>\nКлетка: {idx} | Кэф: x{multi:.2f} | Выигрыш: {win:.2f}", log_type="game", db_only=True)

        if opened == (25 - mines):
            await db.update_user_balance(user_id, win)
            await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
            await db.add_game_history_record(user_id, 'mines', game['bet_amount'], 'win', 'money', win)
            new_bal = await db.get_user_balance(user_id)
            await log_action(bot, user_obj, f"🏆 <b>Mines FULL CLEAR</b>\nЗабрал все алмазы! Выигрыш: {win:.2f} RUB", log_type="game", db_only=False)
            return {"status": "win_finish", "balance": new_bal, "current_win": win}

        return {"status": "safe", "multiplier": multi, "current_win": win, "next_multiplier": next_multi}

@router.post("/mines/cashout")
async def mines_cashout(request: Request, user_id: int = Depends(get_current_user_id)):
    bot: Bot = request.app.state.bot
    pool = await db.get_db()
    async with pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM active_games WHERE user_id=$1 AND game_type='mines'", user_id)
        if not game: raise HTTPException(status_code=404)

        state = json.loads(game['state'])
        mines = state['mines_count']
        opened = len(state['revealed'])
        is_check_game = state.get('is_check_game', False)

        profile = await db.get_user_profile(user_id)
        user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])

        if opened == 0:
             if is_check_game:
                 await db.admin_update_user_checks(user_id, 1)
                 refund_msg = "1 CHECK"
             else:
                 await db.update_user_balance(user_id, game['bet_amount'])
                 refund_msg = f"{game['bet_amount']} RUB"

             await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
             await log_action(bot, user_obj, f"💣 <b>Mines Refund</b>\nВозврат: {refund_msg}", log_type="game", db_only=True)

             new_profile = await db.get_user_profile(user_id)
             return {
                 "status": "success", 
                 "win_amount": game['bet_amount'] if not is_check_game else 0, 
                 "balance": new_profile['balance'],
                 "checks": new_profile.get('game_checks', 0),
                 "grid": state['grid']
             }

        multi = calculate_mines_multiplier(mines, opened)
        win = game['bet_amount'] * multi

        await db.update_user_balance(user_id, win)
        await conn.execute("DELETE FROM active_games WHERE user_id=$1", user_id)
        await db.add_game_history_record(user_id, 'mines', game['bet_amount'], 'win', 'money', win)

        await log_action(bot, user_obj, f"💰 <b>Mines Cashout</b>\nЗабрал: {win:.2f} RUB (x{multi:.2f})", log_type="game", db_only=False)

        new_profile = await db.get_user_profile(user_id)
        return {
            "status": "success", 
            "win_amount": win, 
            "balance": new_profile['balance'], 
            "checks": new_profile.get('game_checks', 0),
            "grid": state['grid']
        }
