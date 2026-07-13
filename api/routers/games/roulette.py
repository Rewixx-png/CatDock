import random
import time
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from aiogram import Bot, types

from api.dependencies import get_current_user_id
import database as db
import utils.docker as dm
from config import TARIFFS, IMAGES
from utils.action_logger import log_action
from utils.leveling import process_spending_xp

router = APIRouter()

ROULETTE_COST = 12
WEEKLY_SPIN_COOLDOWN = 7 * 24 * 60 * 60

PRIZES = [
    {'type': 'nothing', 'text': 'Ничего', 'weight': 80},
    {'type': 'money', 'value': 10, 'text': '10 ₽', 'weight': 110},
    {'type': 'free_spin', 'text': 'Фри спин', 'weight': 45},
    {'type': 'money', 'value': 12, 'text': '12 ₽', 'weight': 80},
    {'type': 'time_bonus', 'text': 'Часы', 'weight': 45}, 
    {'type': 'container', 'value': 'basic', 'text': 'Контейнер', 'weight': 5},
    {'type': 'money', 'value': 30, 'text': '30 ₽', 'weight': 15}, 
    {'type': 'money', 'value': 20, 'text': '20 ₽', 'weight': 35},
]

async def _perform_single_spin(user_id: int, user_profile: dict) -> dict:
    total_spins = user_profile.get('roulette_spins_total', 0) + 1

    is_guaranteed = False
    chosen_prize = None

    if total_spins % 100 == 0:
        is_guaranteed = True
        chosen_prize = {'type': 'guaranteed_container', 'value': 'medium', 'text': 'Контейнер Medium'}
    elif total_spins % 10 == 0:
        is_guaranteed = True
        guaranteed_money = random.randint(20, 40)
        chosen_prize = {'type': 'money', 'value': guaranteed_money, 'text': f'{guaranteed_money} ₽'}
    else:
        population = PRIZES
        weights = [p['weight'] for p in PRIZES]
        chosen_prize = random.choices(population, weights, k=1)[0]

    if is_guaranteed: 
        chosen_prize['is_guaranteed'] = True

    result = 'loss'
    prize_value = 'nothing'
    balance_change = 0
    is_refund = False

    final_prize = chosen_prize.copy()

    try:
        if final_prize['type'] == 'money':
            balance_change = final_prize['value']
            result = 'win'
            prize_value = str(balance_change)

        elif final_prize['type'] == 'time_bonus':
            eligible = [c for c in await db.get_user_containers(user_id) if c['tariff_id'] != 'free' and not c['is_frozen']]
            if eligible:
                target = eligible[0]
                hours = random.randint(1, 6)
                await db.add_container_time(target['id'], hours * 3600)
                result = 'win'
                prize_value = f"{hours}h"
                final_prize['value'] = hours
                final_prize['text'] = f"+{hours} ч. ({target['container_name']})"
            else:
                is_refund = True
                final_prize['type'] = 'no_container_for_time'
                final_prize['text'] = 'Возврат (нет ботов)'

        elif final_prize['type'] in ['container', 'guaranteed_container']:
            tid = 'medium' if final_prize.get('is_guaranteed') else 'basic'
            days = 30 if final_prize.get('is_guaranteed') else 2
            sid = await dm.find_optimal_server(tid, user_id)
            if sid:
                cname, port, url = await dm.create_container(user_id, user_profile.get('username'), sid, TARIFFS[tid], IMAGES['hikka'])
                if cname:
                    await db.add_user_container(user_id, sid, cname, 'hikka', tid, port, url)
                    nc = await db.get_container_by_name(cname)
                    await db.admin_set_container_time(nc['id'], days)
                    result = 'win'
                    prize_value = 'container'
                    final_prize['text'] = f"Бот {cname}"
                else: 
                    is_refund = True
            else: 
                is_refund = True
                final_prize['text'] = 'Возврат (нет мест)'

        elif final_prize['type'] == 'free_spin':
            result = 'win'
            prize_value = 'free_spin'

    except Exception as e:
        logging.error(f"Roulette Logic Error: {e}")
        is_refund = True
        final_prize['type'] = 'error'
        final_prize['text'] = 'Ошибка (Возврат)'

    return {
        'prize': final_prize,
        'balance_change': balance_change,
        'is_refund': is_refund,
        'result': result,
        'prize_value': prize_value
    }

async def _process_spin(user_id: int, count: int, bot: Bot):
    profile = await db.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    user_obj = types.User(id=user_id, is_bot=False, first_name=profile['first_name'], username=profile['username'])

    spins_to_perform = []
    now = int(time.time())

    free_spins_available = profile.get('free_spins', 0)
    weekly_spin_available = (now - profile.get('last_weekly_roulette_ts', 0) > WEEKLY_SPIN_COOLDOWN)

    actual_paid_spins = 0
    used_free_spins = 0
    used_weekly_spin = False

    for _ in range(count):
        if weekly_spin_available:
            weekly_spin_available = False 
            used_weekly_spin = True
            spins_to_perform.append({'is_free': True, 'source': 'weekly'})
        elif free_spins_available > 0:
            free_spins_available -= 1
            used_free_spins += 1
            spins_to_perform.append({'is_free': True, 'source': 'ticket'})
        else:
            actual_paid_spins += 1
            spins_to_perform.append({'is_free': False, 'source': 'balance'})

    total_cost = actual_paid_spins * ROULETTE_COST

    if total_cost > 0:
        if not await db.try_deduct_user_balance(user_id, total_cost):
             raise HTTPException(status_code=402, detail=f"Insufficient funds. Need {total_cost} RUB.")
        asyncio.create_task(process_spending_xp(bot, user_id, total_cost))

    if used_free_spins > 0:
        for _ in range(used_free_spins):
             await db.use_user_free_spin(user_id)

    if used_weekly_spin:
        await db.set_user_last_weekly_spin(user_id, now)

    results = []
    total_balance_change = 0
    total_refund = 0

    for spin_info in spins_to_perform:
        spin_res = await _perform_single_spin(user_id, profile)

        await db.increment_user_roulette_spins(user_id)

        if spin_res['prize']['type'] == 'free_spin':
            await db.add_user_free_spins(user_id, 1)
            spin_res['result'] = 'win'

        if spin_res['balance_change'] > 0:
            total_balance_change += spin_res['balance_change']

        if spin_res['is_refund'] and not spin_info['is_free']:
            total_refund += ROULETTE_COST

        cost_logged = 0 if spin_info['is_free'] else ROULETTE_COST
        await db.add_game_history_record(user_id, 'roulette', cost_logged, spin_res['result'], spin_res['prize']['type'], spin_res['prize_value'])

        results.append(spin_res)
        profile['roulette_spins_total'] += 1

    net_change = total_balance_change + total_refund
    if net_change > 0:
        await db.update_user_balance(user_id, net_change)

    if count == 1:
        prize_text = results[0]['prize']['text']
        log_text = f"🎰 <b>Roulette Spin</b>\n💸 Ставка: {0 if spins_to_perform[0]['is_free'] else ROULETTE_COST} RUB\n🎁 Результат: <b>{prize_text}</b>"
    else:
        log_text = f"🎰 <b>Roulette x{count}</b>\n💸 Общая ставка: {total_cost} RUB\n🎁 Выигрыш: {total_balance_change} RUB"

    await log_action(bot, user_obj, log_text, log_type="game")

    new_bal = await db.get_user_balance(user_id)

    pool = await db.get_db()
    async with pool.acquire() as conn:
        current_free_spins = await conn.fetchval("SELECT free_spins FROM users WHERE user_id=$1", user_id)
    current_free_spins = current_free_spins or 0

    if count == 1:
        return {"status": "success", "prize": results[0]['prize'], "new_balance": new_bal, "free_spins_left": current_free_spins}
    else:
        return {
            "status": "success", 
            "results": [r['prize'] for r in results], 
            "new_balance": new_bal,
            "total_win": total_balance_change,
            "free_spins_left": current_free_spins
        }

@router.post("/roulette/spin")
async def spin_roulette(request: Request, user_id: int = Depends(get_current_user_id)):
    try:
        body = await request.json()
        count = int(body.get('count', 1))
    except Exception:
        count = 1

    if count not in [1, 10]:
        raise HTTPException(status_code=400, detail="Invalid spin count (1 or 10 allowed)")

    return await _process_spin(user_id, count, request.app.state.bot)

@router.post("/roulette/spin-multiple")
async def spin_roulette_multiple(request: Request, user_id: int = Depends(get_current_user_id)):
    return await _process_spin(user_id, 10, request.app.state.bot)
