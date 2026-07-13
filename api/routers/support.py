import logging
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from api.dependencies import get_current_user_id, get_current_user
from api.utils import _get_avatar_url
import database as db

router = APIRouter(tags=["Support"])

@router.get("/tickets")
async def user_get_tickets(user_id: int = Depends(get_current_user_id)):
    tickets = await db.get_user_tickets(user_id)
    return {"status": "success", "data": tickets}

@router.get("/ticket/{ticket_id}")
async def user_get_ticket_details(ticket_id: int, user_id: int = Depends(get_current_user_id)):
    ticket = await db.get_ticket_by_id(ticket_id)
    if not ticket or ticket['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"status": "success", "data": ticket}

@router.get("/ticket/{ticket_id}/messages")
async def user_get_ticket_messages(ticket_id: int, request: Request, user_id: int = Depends(get_current_user_id)):
    ticket = await db.get_ticket_by_id(ticket_id)
    if not ticket or ticket['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = await db.get_messages_for_ticket(ticket_id)
    bot = request.app.state.bot

    for msg in messages:
        msg['avatar_url'] = await _get_avatar_url(bot, msg['sender_id'])

    await db.mark_ticket_as_read_for_user(ticket_id, user_id)
    return {"status": "success", "data": messages}

@router.post("/ticket/{ticket_id}/mark-read")
async def user_mark_read(ticket_id: int, user_id: int = Depends(get_current_user_id)):
    await db.mark_ticket_as_read_for_user(ticket_id, user_id)
    return {"status": "success"}

@router.post("/create-ticket")
async def user_create_ticket(
    request: Request,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    subject = payload.get('subject')
    text = payload.get('text')
    if not text or not subject:
        raise HTTPException(status_code=400, detail="Subject and text required")

    ticket_id = await db.create_support_ticket(user['user_id'], user.get('username'), subject, text)
    if not ticket_id:
        raise HTTPException(status_code=500, detail="Failed to create ticket")

    try:
        admin_ids = await db.get_admin_ids()
        notif_text = f"📮 Новый тикет #{ticket_id} от @{user.get('username')}"
        for aid in admin_ids:
            await db.create_notification(aid, notif_text, "/admin/support")
    except Exception: pass

    return {"status": "success", "message": "Ticket created", "ticket_id": ticket_id}

@router.post("/ticket/{ticket_id}/reply")
async def user_reply_ticket(ticket_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    text = payload.get('text')
    if not text: raise HTTPException(status_code=400, detail="Text required")

    ticket = await db.get_ticket_by_id(ticket_id)
    if not ticket or ticket['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="Access denied")

    if ticket['status'] == 'closed':
        raise HTTPException(status_code=400, detail="Ticket is closed")

    await db.add_message_to_ticket(
        ticket_id, user['user_id'], user.get('first_name', 'User'), text, is_admin=False
    )
    return {"status": "success", "message": "Sent"}

@router.post("/ticket/{ticket_id}/close")
async def user_close_ticket(ticket_id: int, user_id: int = Depends(get_current_user_id)):
    ticket = await db.get_ticket_by_id(ticket_id)
    if not ticket or ticket['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.close_ticket(ticket_id)
    return {"status": "success"}

@router.post("/ticket/{ticket_id}/hide")
async def user_hide_ticket(ticket_id: int, user_id: int = Depends(get_current_user_id)):
    await db.hide_ticket_for_user(ticket_id, user_id)
    return {"status": "success"}
