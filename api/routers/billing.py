import html
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from api.dependencies import get_current_user_id
import database as db
from config import ADMIN_ID, WEB_APP_URL, DEV_ID
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

router = APIRouter(tags=["Billing"])

@router.get("/finance/history")
async def get_payment_history(user_id: int = Depends(get_current_user_id)):
    history = await db.get_user_payment_history(user_id)
    
    for item in history:
        item['created_at'] = str(item['created_at'])
    return {"status": "success", "data": history}

@router.post("/deposit/create")
async def create_deposit_request(
    request: Request,
    payload: dict = Body(...), 
    user_id: int = Depends(get_current_user_id)
):
    amount = float(payload.get('amount', 0))
    method = payload.get('method', 'Unknown') 
    details = payload.get('details', {}) 

    if amount <= 0: 
        raise HTTPException(status_code=400, detail="Некорректная сумма")

    request_id = await db.create_payment_request(user_id, amount, method, details)
    if not request_id:
        raise HTTPException(status_code=500, detail="Ошибка базы данных")

    bot = request.app.state.bot
    user_profile = await db.get_user_profile(user_id)

    admin_url = f"{WEB_APP_URL}/admin/process-deposit/{request_id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Обработать (Web)", web_app=WebAppInfo(url=admin_url))]
    ])

    safe_first_name = html.escape(user_profile.get('first_name', 'User'))
    safe_username = html.escape(user_profile.get('username') or 'No Username')
    safe_method = html.escape(method)
    safe_bank = html.escape(details.get('bank_name', 'Не указан'))

    text = (
        f"💸 <b>Новая заявка на пополнение #{request_id}</b>\n\n"
        f"👤 <b>Юзер:</b> {safe_first_name} (@{safe_username})\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💰 <b>Сумма:</b> <code>{amount} RUB</code>\n"
        f"💳 <b>Метод:</b> {safe_method}\n"
        f"🏦 <b>Банк:</b> {safe_bank}"
    )

    target_chat_id = ADMIN_ID
    if user_id == DEV_ID:
        target_chat_id = DEV_ID

    try:
        await bot.send_message(target_chat_id, text, reply_markup=keyboard)
    except Exception as e:
        
        pass 

    return {"status": "success", "message": "Заявка создана", "request_id": request_id}
