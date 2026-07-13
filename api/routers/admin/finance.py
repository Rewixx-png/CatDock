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
    
    req, result = await db.approve_payment_request(request_id, user_id)
    if result == 'not_found':
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if result == 'already_processed':
        raise HTTPException(status_code=400, detail="Заявка уже обработана")
    if result != 'ok' or not req:
        raise HTTPException(status_code=500, detail="Не удалось обработать заявку")

    bot = request.app.state.bot
    target_user_id = req['user_id']
    amount = req['amount']

    final_amount = req['final_amount']

    try:
        await bot.send_message(
            target_user_id, 
            f"✅ <b>Заявка #{request_id} одобрена!</b>\n"
            f"Баланс пополнен на: <b>{final_amount:.2f} RUB</b>"
        )
    except Exception: pass

    try:
        admin_user = await bot.get_chat(user_id)
        target_user_obj = await bot.get_chat(target_user_id)
        await log_action(bot, admin_user, f"одобрил заявку #{request_id} на {amount} RUB (Web)", target_user_obj)
    except Exception:
        pass

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
    
    req, result = await db.decline_payment_request(request_id, user_id, safe_reason)
    if result != 'ok' or not req:
        raise HTTPException(status_code=400, detail="Заявка не актуальна")

    bot = request.app.state.bot
    try:
        await bot.send_message(
            req['user_id'], 
            f"❌ <b>Заявка #{request_id} отклонена.</b>\nПричина: {safe_reason}"
        )
    except Exception: pass

    return {"status": "success", "message": "Отклонено"}
