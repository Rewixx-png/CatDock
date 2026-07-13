import logging
from functools import wraps
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import database as db
from roles import UserRole
from config import ALL_ADMIN_IDS

def auth_required(admin_only=False):
    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request and 'request' in kwargs:
                request = kwargs['request']

            if not request:
                logging.warning("auth_required decorator used without Request object")
                return await f(*args, **kwargs)

            token = request.headers.get('X-Web-Access-Token')

            if not token:
                return JSONResponse({'status': 'error', 'message': 'Token not provided'}, status_code=401)

            try:
                user_data = await db.get_user_by_web_token(token)
            except Exception as e:
                logging.error(f"[WEB AUTH] Database error during token check: {e}", exc_info=True)
                return JSONResponse({'status': 'error', 'message': 'Auth Database Error'}, status_code=500)

            if not user_data:
                return JSONResponse({'status': 'error', 'message': 'Invalid or expired token'}, status_code=403)

            user_id = user_data['user_id']

            if admin_only:
                if user_id not in ALL_ADMIN_IDS:
                    user_role = await db.get_user_role(user_id)
                    if not user_role or user_role < UserRole.ADMIN:
                        logging.warning(f"SECURITY: User {user_id} attempted ADMIN access but lacked permissions.")
                        return JSONResponse({'status': 'error', 'message': 'Permission denied'}, status_code=403)

            request.state.user_data = user_data

            return await f(*args, **kwargs)
        return decorated_function
    return decorator
