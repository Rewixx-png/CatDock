import logging
from config import WEB_APP_URL

async def _get_avatar_url(bot, user_id: int) -> str:
    """
    Возвращает URL на аватарку пользователя.
    Использует внутренний прокси-метод API для обхода ограничений CORS и Telegram.
    """
    
    base_url = WEB_APP_URL.rstrip('/')
    return f"{base_url}/api/v1/public/user_photo/{user_id}"
