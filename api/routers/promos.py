import logging
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from aiogram import Bot

from api.dependencies import get_current_user_id
import database as db
from utils.action_logger import log_action
from aiogram.types import User

router = APIRouter(tags=["Promos"])

@router.post("/activate")
async def activate_promo(
    request: Request,
    payload: dict = Body(...),
    user_id: int = Depends(get_current_user_id)
):
    code = payload.get("code", "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Code required")

    status, amount = await db.activate_promo_code(user_id, code)
    
    bot: Bot = request.app.state.bot
    user_profile = await db.get_user_profile(user_id)
    user_obj = User(id=user_id, is_bot=False, first_name=user_profile.get('first_name', 'WebUser'), username=user_profile.get('username'))

    if status == 'success':
        await log_action(bot, user_obj, f"активировал личный промокод '{code}' (+{amount:.2f} RUB) через Web")
        return {
            "status": "success", 
            "message": f"Промокод активирован! Начислено {amount:.2f} RUB.",
            "new_balance": await db.get_user_balance(user_id)
        }
    
    elif status == 'not_found':
        
        global_promo = await db.find_and_deactivate_global_promo(code, user_id)
        if not global_promo:
            raise HTTPException(status_code=404, detail="Промокод не найден, истек или уже активирован.")

        promo_type = global_promo['promo_type']
        promo_value = global_promo['value']
        
        success_msg = "Промокод активирован!"

        if promo_type == 'MONEY_BONUS':
            await db.update_user_balance(user_id, float(promo_value))
            success_msg = f"Получено {float(promo_value):.2f} RUB!"
            await log_action(bot, user_obj, f"активировал глобальный промокод '{code}' (+{promo_value} RUB)")

        elif promo_type == 'FREE_CONTAINER':
            await db.set_user_free_container_promo(user_id, True, code)
            success_msg = "Доступен бесплатный контейнер (Basic)!"
            await log_action(bot, user_obj, f"активировал глобальный промокод '{code}' (Free Container)")

        elif promo_type == 'GAME_CHECK':
            await db.admin_update_user_checks(user_id, int(promo_value))
            success_msg = f"Получено {int(promo_value)} игровых чеков!"
            await log_action(bot, user_obj, f"активировал глобальный промокод '{code}' (Checks)")

        elif promo_type == 'DEPOSIT_BONUS':
            await db.set_user_deposit_bonus(user_id, int(promo_value), code)
            success_msg = f"Бонус к пополнению: +{int(promo_value)}%!"

        elif promo_type == 'DISCOUNT_BONUS':
            await db.set_user_tariff_discount(user_id, int(promo_value), code)
            success_msg = f"Скидка на покупку: {int(promo_value)}%!"

        return {
            "status": "success", 
            "message": success_msg,
            "new_balance": await db.get_user_balance(user_id)
        }

    else:
        
        msg_map = {
            'already_activated': "Этот код уже использован.",
            'self_activation': "Нельзя активировать свой код.",
            'db_error': "Ошибка базы данных."
        }
        raise HTTPException(status_code=400, detail=msg_map.get(status, "Ошибка активации"))

@router.post("/create")
async def create_promo(
    request: Request,
    payload: dict = Body(...),
    user_id: int = Depends(get_current_user_id)
):
    try:
        amount = float(payload.get("amount", 0))
        if amount <= 0: raise ValueError
    except:
        raise HTTPException(status_code=400, detail="Некорректная сумма")

    new_code = await db.create_promo_code_safe(user_id, amount)

    if new_code:
        bot: Bot = request.app.state.bot
        user_profile = await db.get_user_profile(user_id)
        user_obj = User(id=user_id, is_bot=False, first_name=user_profile.get('first_name', 'WebUser'), username=user_profile.get('username'))
        await log_action(bot, user_obj, f"создал личный промокод '{new_code}' на {amount:.2f} RUB через Web")

        return {
            "status": "success",
            "code": new_code,
            "amount": amount,
            "new_balance": await db.get_user_balance(user_id)
        }
    else:
        
        raise HTTPException(status_code=402, detail="Недостаточно средств на основном балансе.")
