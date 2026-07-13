from fastapi import APIRouter, Depends, HTTPException, Request, Body
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

import database as db
from config import WEB_APP_URL
from api.utils import _get_avatar_url
from .dependencies import get_current_admin

router = APIRouter(prefix="/support")

@router.get("/tickets")
async def admin_get_tickets(admin: dict = Depends(get_current_admin)):
    open_t = await db.get_all_tickets_by_status('open')
    progress_t = await db.get_all_tickets_by_status('in_progress')
    all_t = open_t + progress_t
    all_t.sort(key=lambda x: str(x.get('last_message_time') or ''), reverse=True)
    return {'status': 'success', 'data': all_t}

@router.get("/ticket/{ticket_id}")
async def admin_get_ticket_details(ticket_id: int, admin: dict = Depends(get_current_admin)):
    t = await db.get_ticket_by_id(ticket_id)
    if not t: raise HTTPException(status_code=404, detail="Not found")
    return {'status': 'success', 'data': t}

@router.get("/ticket/{ticket_id}/messages")
async def admin_get_ticket_messages(ticket_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    bot: Bot = request.app.state.bot
    msgs = await db.get_messages_for_ticket(ticket_id)
    for m in msgs: m['avatar_url'] = await _get_avatar_url(bot, m['sender_id'])
    await db.mark_ticket_as_read_for_admin(ticket_id)
    return {'status': 'success', 'data': msgs}

@router.post("/ticket/{ticket_id}/mark-read")
async def admin_mark_read(ticket_id: int, admin: dict = Depends(get_current_admin)):
    await db.mark_ticket_as_read_for_admin(ticket_id)
    return {'status': 'success'}

@router.post("/ticket/{ticket_id}/take")
async def admin_take_ticket(ticket_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    bot: Bot = request.app.state.bot
    admin_id = admin['user_id']
    if not await db.assign_ticket_to_admin(ticket_id, admin_id):
        return {'status': 'error', 'message': 'Тикет уже занят.'}
    ticket = await db.get_ticket_by_id(ticket_id)
    await db.add_message_to_ticket(ticket_id, admin_id, "System", f"Администратор {admin.get('first_name', 'Admin')} подключился.", is_admin=True)
    if ticket:
        try: await bot.send_message(ticket['user_id'], f"Администратор <b>{admin.get('first_name', 'Admin')}</b> взял ваш тикет в работу.")
        except: pass
    return {'status': 'success', 'message': 'Taken.'}

@router.post("/ticket/{ticket_id}/reply")
async def admin_reply_ticket(ticket_id: int, request: Request, payload: dict = Body(...), admin: dict = Depends(get_current_admin)):
    text = payload.get('text')
    if not text: raise HTTPException(status_code=400, detail="Text required")
    bot: Bot = request.app.state.bot
    ticket = await db.get_ticket_by_id(ticket_id)
    if not ticket or ticket.get('status') == 'closed': raise HTTPException(status_code=404, detail="Invalid ticket")
    await db.add_message_to_ticket(ticket_id, admin['user_id'], admin.get('first_name', 'Admin'), text, is_admin=True)
    try:
        await db.create_notification(ticket['user_id'], f"💬 Ответ в тикете #{ticket_id}", "/templates/support.html")
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💬 Открыть тикет", url=f"{WEB_APP_URL}/templates/support.html"))
        await bot.send_message(ticket['user_id'], f"📨 <b>Ответ в тикете #{ticket_id}</b>", reply_markup=builder.as_markup())
    except: pass
    return {'status': 'success', 'message': 'Sent'}

@router.post("/ticket/{ticket_id}/close")
async def admin_close_ticket(ticket_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    ticket = await db.get_ticket_by_id(ticket_id)
    if not ticket: raise HTTPException(status_code=404, detail="Not found")
    await db.close_ticket(ticket_id)
    try: await db.create_notification(ticket['user_id'], f"✅ Тикет #{ticket_id} закрыт.", "/templates/support.html")
    except: pass
    return {'status': 'success', 'message': 'Closed'}
