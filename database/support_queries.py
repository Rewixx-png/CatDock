import logging
from .core import get_db

async def create_support_ticket(user_id: int, username: str, subject: str, question: str) -> int | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                ticket_id = await conn.fetchval(
                    """INSERT INTO support_tickets 
                       (user_id, username, subject, question_text, last_message_time, last_message_text, admin_has_unread) 
                       VALUES ($1, $2, $3, $4, NOW(), $5, TRUE) RETURNING id""",
                    user_id, username, subject, question, question
                )

                sender_name = username if username else f"User {user_id}"

                await conn.execute(
                    """INSERT INTO support_messages (ticket_id, sender_id, sender_name, message_text, is_admin_message) 
                       VALUES ($1, $2, $3, $4, $5)""",
                    ticket_id, user_id, sender_name, question, False
                )

                bot_reply_text = "Здравствуйте! Нам очень жаль, что у вас возникла проблема. Администратор скоро подключится к диалогу."
                await conn.execute(
                    """INSERT INTO support_messages (ticket_id, sender_id, sender_name, message_text, is_admin_message)
                       VALUES ($1, $2, $3, $4, $5)""",
                    ticket_id, 1, "CatDock", bot_reply_text, True
                )

            return ticket_id
    except Exception as e:
        logging.error(f"Ошибка при создании тикета для {user_id}: {e}", exc_info=True)
        return None

async def get_ticket_by_id(ticket_id: int) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM support_tickets WHERE id = $1", ticket_id)
            return dict(row) if row else None
    except Exception:
        return None

async def add_message_to_ticket(ticket_id: int, sender_id: int, sender_name: str, text: str, is_admin: bool):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO support_messages (ticket_id, sender_id, sender_name, message_text, is_admin_message) 
                       VALUES ($1, $2, $3, $4, $5)""",
                    ticket_id, sender_id, sender_name, text, is_admin
                )

                if is_admin:
                    await conn.execute(
                        "UPDATE support_tickets SET last_message_time = NOW(), last_message_text = $1, status = 'in_progress', user_has_unread = TRUE WHERE id = $2 AND status != 'closed'",
                        text, ticket_id
                    )
                else:
                    await conn.execute(
                        "UPDATE support_tickets SET last_message_time = NOW(), last_message_text = $1, status = 'in_progress', admin_has_unread = TRUE WHERE id = $2 AND status != 'closed'",
                        text, ticket_id
                    )
    except Exception as e:
        logging.error(f"Ошибка при добавлении сообщения в тикет {ticket_id}: {e}")

async def get_all_tickets_by_status(status: str) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM support_tickets WHERE status = $1 ORDER BY last_message_time DESC", status)
            return [dict(row) for row in rows]
    except Exception:
        return []

async def get_messages_for_ticket(ticket_id: int) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM support_messages WHERE ticket_id = $1 ORDER BY timestamp ASC", ticket_id)
            return [dict(row) for row in rows]
    except Exception:
        return []

async def assign_ticket_to_admin(ticket_id: int, admin_id: int) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE support_tickets SET assigned_admin_id = $1, status = 'in_progress' WHERE id = $2 AND (assigned_admin_id IS NULL OR status = 'open')",
                admin_id, ticket_id
            )
            return "UPDATE 0" not in result
    except Exception:
        return False

async def get_user_tickets(user_id: int) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM support_tickets WHERE user_id = $1 AND hidden_by_user = FALSE ORDER BY last_message_time DESC", user_id)
            return [dict(row) for row in rows]
    except Exception:
        return []

async def close_ticket(ticket_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE support_tickets SET status = 'closed', close_date = NOW() WHERE id = $1",
                ticket_id
            )
    except Exception as e:
        logging.error(f"Ошибка при закрытии тикета {ticket_id}: {e}")

async def hide_ticket_for_user(ticket_id: int, user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE support_tickets SET hidden_by_user = TRUE WHERE id = $1 AND user_id = $2",
                ticket_id, user_id
            )
    except Exception as e:
        logging.error(f"Ошибка при скрытии тикета {ticket_id} для юзера {user_id}: {e}")

async def rate_ticket(ticket_id: int, user_id: int, rating: int) -> bool:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE support_tickets SET rating = $1 WHERE id = $2 AND user_id = $3 AND rating IS NULL",
                rating, ticket_id, user_id
            )
            return "UPDATE 0" not in result
    except Exception as e:
        logging.error(f"Ошибка при оценке тикета {ticket_id}: {e}")
        return False

async def mark_ticket_as_read_for_user(ticket_id: int, user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE support_tickets SET user_has_unread = FALSE WHERE id = $1 AND user_id = $2", ticket_id, user_id)
    except Exception as e:
        logging.error(f"Ошибка при пометке тикета {ticket_id} как прочитанного для юзера {user_id}: {e}")

async def mark_ticket_as_read_for_admin(ticket_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE support_tickets SET admin_has_unread = FALSE WHERE id = $1", ticket_id)
    except Exception as e:
        logging.error(f"Ошибка при пометке тикета {ticket_id} как прочитанного для админа: {e}")
