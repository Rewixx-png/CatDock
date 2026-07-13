import logging
import html
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from api.dependencies import get_current_user_id
from roles import UserRole
import database as db
from utils.action_logger import log_action

router = APIRouter(prefix="/finance", tags=["Admin Finance"])

async def check_admin_access(user_id: int):
    role = await db.get_user_role(user_id)
    if not role or role < UserRole.SENIOR_ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

@router.get("/request/{request_id}")
async def get_deposit_request(request_id: int, user_id: int = Depends(get_current_user_id)):
    await check_admin_access(user_id)
    
    req = await db.get_payment_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    req['created_at'] = str(req['created_at'])
    return {"status": "success", "data": req}

@router.post("/request/{request_id}/approve")
async def approve_deposit_request(
    request_id: int, 
    request: Request,
    user_id: int = Depends(get_current_user_id)
):
    await check_admin_access(user_id)
    
    req = await db.get_payment_request_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    if req['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Заявка уже обработана")

    bot = request.app.state.bot
    target_user_id = req['user_id']
    amount = req['amount']

    user_profile = await db.get_user_profile(target_user_id)
    final_amount = amount
    
    bonus_percent = user_profile.get('active_deposit_bonus_percent', 0)
    if bonus_percent > 0:
        final_amount += amount * (bonus_percent / 100)
        await db.set_user_deposit_bonus(target_user_id, 0, None)

    await db.update_user_balance(target_user_id, final_amount)
    await db.update_payment_request_status(request_id, 'approved', admin_id=user_id)

    referrer_id = await db.get_referrer_id(target_user_id)
    if referrer_id:
        await db.add_referral_reward(referrer_id, amount)

    try:
        await bot.send_message(
            target_user_id, 
            f"✅ <b>Заявка #{request_id} одобрена!</b>\n"
            f"Баланс пополнен на: <b>{final_amount:.2f} RUB</b>"
        )
    except Exception: pass

    admin_user = await bot.get_chat(user_id)
    target_user_obj = await bot.get_chat(target_user_id)
    await log_action(bot, admin_user, f"одобрил заявку #{request_id} на {amount} RUB (Web)", target_user_obj)

    return {"status": "success", "message": "Одобрено"}

@router.post("/request/{request_id}/decline")
async def decline_deposit_request(
    request_id: int, 
    request: Request,
    payload: dict = Body(...),
    user_id: int = Depends(get_current_user_id)
):
    await check_admin_access(user_id)
    
    raw_reason = payload.get('reason', 'Без причины')
    
    safe_reason = html.escape(raw_reason)
    
    req = await db.get_payment_request_by_id(request_id)
    if not req or req['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Заявка не актуальна")

    await db.update_payment_request_status(request_id, 'declined', admin_id=user_id, reason=safe_reason)

    bot = request.app.state.bot
    try:
        await bot.send_message(
            req['user_id'], 
            f"❌ <b>Заявка #{request_id} отклонена.</b>\nПричина: {safe_reason}"
        )
    except Exception: pass

    return {"status": "success", "message": "Отклонено"}
