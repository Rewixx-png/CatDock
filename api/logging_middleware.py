import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import database as db
from utils.action_logger import log_action
from aiogram import types

PATH_TRANSLATIONS = {
    "/api/v1/user/games/mines/start": "💣 <b>Mines:</b> Начало новой игры",
    "/api/v1/user/games/mines/click": "💣 <b>Mines:</b> Ход (открытие ячейки)",
    "/api/v1/user/games/mines/cashout": "💰 <b>Mines:</b> Вывод денег (Cashout)",

    "/api/v1/user/games/towers/start": "🗼 <b>Towers:</b> Начало новой игры",
    "/api/v1/user/games/towers/step": "🗼 <b>Towers:</b> Подъем на уровень",
    "/api/v1/user/games/towers/cashout": "💰 <b>Towers:</b> Вывод денег (Cashout)",

    "/api/v1/user/games/roulette/spin": "🎰 <b>Рулетка:</b> Спин",
    "/api/v1/user/games/roulette/spin-multiple": "🎰 <b>Рулетка:</b> Мульти-спин (x10)",

    "/api/v1/user/tariffs/purchase": "🛒 <b>Магазин:</b> Покупка контейнера",
    "/api/v1/user/deposit/manual": "💳 <b>Финансы:</b> Создание заявки на пополнение",
    "/api/v1/user/referrals/upgrade": "🚀 <b>Рефералка:</b> Покупка PRO уровня",

    "/api/v1/user/keys/generate": "🔑 <b>API:</b> Создание нового ключа",
    "/api/v1/user/keys/revoke": "🗑️ <b>API:</b> Отзыв всех ключей",

    "/api/v1/user/support/create-ticket": "📨 <b>Поддержка:</b> Создание тикета",

    "/api/v1/user/profile/avatar": "🖼️ <b>Профиль:</b> Загрузка аватара",
}

class WebLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, bot):
        super().__init__(app)
        self.bot = bot

    async def dispatch(self, request: Request, call_next):
        
        print(f"🔥 [HTTP] {request.method} {request.url.path}")
        
        token = request.headers.get('X-Web-Access-Token')
        user_id = None

        if token:
            try:
                user_data = await db.get_user_by_web_token(token)
                if user_data:
                    request.state.user_data = user_data 
                    user_id = user_data['user_id']
            except Exception:
                pass

        response = await call_next(request)

        should_log = request.method in ["POST", "DELETE", "PUT"] or "action" in request.url.path

        if "check-token" in request.url.path or "notifications/unread-count" in request.url.path:
            should_log = False

        if should_log and response.status_code < 500:
            if user_id:
                try:
                    user_obj = types.User(
                        id=user_id, 
                        is_bot=False, 
                        first_name=request.state.user_data.get('first_name', 'WebUser'),
                        username=request.state.user_data.get('username')
                    )

                    path = request.url.path
                    log_text = ""

                    if path in PATH_TRANSLATIONS:
                        log_text = PATH_TRANSLATIONS[path]

                    elif "/container/" in path:
                        if "/action" in path:
                            log_text = "⚙️ <b>Контейнер:</b> Питание (Старт/Стоп/Рестарт)"
                        elif "/rename" in path:
                            log_text = "📝 <b>Контейнер:</b> Смена имени"
                        elif "/reinstall" in path:
                            log_text = "🔩 <b>Контейнер:</b> Переустановка"
                        elif "/delete" in path:
                            log_text = "🗑️ <b>Контейнер:</b> Удаление"
                        else:
                            log_text = f"📦 <b>Контейнер:</b> Действие ({request.method})"

                    elif "/support/ticket/" in path:
                        if "/reply" in path:
                            log_text = "💬 <b>Поддержка:</b> Ответ в тикет"
                        elif "/close" in path:
                            log_text = "🔒 <b>Поддержка:</b> Закрытие тикета"

                    else:
                        log_text = f"🌐 <b>WEB:</b> {request.method} <code>{path}</code>"

                    await log_action(self.bot, user_obj, log_text, log_type="web_interaction", db_only=True)

                except Exception as e:
                    logging.error(f"Middleware Log Error: {e}")

        return response
