import logging
import traceback
import html
from functools import wraps
from fastapi.responses import JSONResponse
from fastapi import Request
import database as db

def handle_api_errors(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            tb = traceback.format_exc()

            logging.error(f"API endpoint crashed: {error_msg}", exc_info=True)

            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request and 'request' in kwargs:
                request = kwargs['request']

            if request:
                try:
                    token = request.headers.get('X-Web-Access-Token')
                    if token:
                        user_by_token = await db.get_user_by_web_token(token)
                        if user_by_token:
                            user_id = user_by_token['user_id']
                            bot = request.app.state.bot
                            if bot:
                                safe_error = html.escape(error_msg)
                                text = (
                                    f"⚠️ <b>CRITICAL WEB ERROR</b>\n\n"
                                    f"При обработке вашего запроса произошел сбой.\n"
                                    f"<b>Error:</b> <code>{safe_error}</code>\n\n"
                                    f"<i>Traceback сохранен в логах.</i>"
                                )
                                await bot.send_message(chat_id=user_id, text=text)
                except Exception as notify_error:
                    logging.error(f"Не удалось отправить уведомление об ошибке пользователю: {notify_error}")

            return JSONResponse(content={
                "status": "error",
                "message": "Internal Server Error",
                "error": error_msg
            }, status_code=500)
    return decorated_function
