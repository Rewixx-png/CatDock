import logging
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import database as db
from config import LOG_CHAT_ID

async def global_exception_handler(request: Request, exc: Exception):
    
    if isinstance(exc, StarletteHTTPException):
        
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code,
                content={"status": "error", "message": str(exc.detail)}
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": "Page not found (Backend 404)"}
        )

    error_msg = str(exc)
    tb = traceback.format_exc()
    logging.error(f"🔥 WEB EXCEPTION: {error_msg}\n{tb}")

    try:
        user_id = None
        if hasattr(request.state, 'user_data'):
            user_id = request.state.user_data.get('user_id')
        
        actor_id = user_id if user_id else 0
        await db.add_system_log(
            actor_id=actor_id,
            target_id=None,
            action_type="web_error",
            message=f"CRITICAL: {error_msg}",
            is_admin_action=False
        )

        bot = request.app.state.bot
        if bot and LOG_CHAT_ID:
            await bot.send_message(
                LOG_CHAT_ID, 
                f"🔥 <b>WEB 500 ERROR</b>\nPath: {request.url.path}\nError: {error_msg}"
            )
    except Exception:
        pass

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal Server Error",
            "detail": error_msg
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation Error",
            "errors": exc.errors()
        }
    )
