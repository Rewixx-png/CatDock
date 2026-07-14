import logging
import os
import json
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from roles import UserRole
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
API_SECRET_KEY = os.getenv("WEB_API_SECRET_KEY", "default_secret")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")

SENTRY_DSN = os.getenv("SENTRY_DSN")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

def _get_ids_from_env(key: str) -> list[int]:
    ids_str = os.getenv(key, "")
    if not ids_str:
        return []
    return [int(admin_id) for admin_id in ids_str.split(',') if admin_id.strip().isdigit()]

def _get_int_from_env(key: str) -> int | None:
    val = os.getenv(key)
    if val and val.strip():
        try:
            return int(val.strip())
        except ValueError:
            logging.warning(f"Не удалось преобразовать в число значение {key}={val} из .env.")
    return None

def _get_float_from_env(key: str, default: float) -> float:
    val = os.getenv(key)
    if val:
        try:
            return float(val)
        except (ValueError, TypeError):
            logging.warning(f"Не удалось преобразовать в число {key}={val}. Используется значение по умолчанию {default}.")
    return default

ADMIN_LEVELS = {
    UserRole.OWNER: _get_ids_from_env("OWNER_IDS"),
    UserRole.CO_OWNER: _get_ids_from_env("CO_OWNER_IDS"),
    UserRole.SENIOR_ADMIN: _get_ids_from_env("SENIOR_ADMIN_IDS"),
    UserRole.ADMIN: _get_ids_from_env("ADMIN_IDS"),
    UserRole.JUNIOR_ADMIN: _get_ids_from_env("JUNIOR_ADMIN_IDS"),
}
ALL_ADMIN_IDS = {admin_id for ids in ADMIN_LEVELS.values() for admin_id in ids}
# Backward-compatible name used by the legacy filter module.
ADMIN_IDS = ALL_ADMIN_IDS

BOT_USERNAME = os.getenv("BOT_USERNAME", "CatDockBot")
WEB_APP_URL = os.getenv("WEB_APP_URL", "http://localhost:8082")
INFO_CHAT_ID = _get_int_from_env("INFO_CHAT_ID")
MODERATION_CHAT_ID = _get_int_from_env("MODERATION_CHAT_ID")
CAPTCHA_TOPIC_ID = _get_int_from_env("CAPTCHA_TOPIC_ID")
LOG_CHAT_ID = _get_int_from_env("LOG_CHAT_ID")

DEV_ID = _get_int_from_env("DEV_ID") or (ADMIN_LEVELS[UserRole.OWNER][0] if ADMIN_LEVELS[UserRole.OWNER] else 0)

SERVER_REPORT_TOPIC_ID = None
SERVER_REPORT_CHAT_ID = _get_int_from_env("SERVER_REPORT_CHAT_ID") or INFO_CHAT_ID

ADMIN_ID = ADMIN_LEVELS[UserRole.OWNER][0] if ADMIN_LEVELS[UserRole.OWNER] else None
PAYMENT_PHONE = os.getenv("PAYMENT_PHONE")
DEFAULT_CPU_LIMIT = _get_float_from_env("DEFAULT_CPU_LIMIT", 0.2)
CPU_UPGRADE_PRICE = _get_float_from_env("CPU_UPGRADE_PRICE", 10.0)
RAM_UPGRADE_PRICE = _get_float_from_env("RAM_UPGRADE_PRICE", 15.0)

SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/CatDockSupport")
SUPPORT_CHAT_URL = os.getenv("SUPPORT_CHAT_URL", SUPPORT_URL)

try:
    card_details_json = os.getenv("CARD_PAYMENT_DETAILS", '{}')
    raw_card_details = json.loads(card_details_json)
    if not isinstance(raw_card_details, dict):
        raise ValueError("CARD_PAYMENT_DETAILS must be a JSON object")
    CARD_PAYMENT_DETAILS = {
        str(country): [
            {'bank': str(card['bank']), 'number': str(card['number'])}
            for card in cards
            if isinstance(card, dict) and card.get('bank') and card.get('number')
        ]
        for country, cards in raw_card_details.items()
        if isinstance(cards, list)
    }
except (json.JSONDecodeError, ValueError):
    logging.error("КРИТИЧЕСКАЯ ОШИБКА: Не удалось прочитать CARD_PAYMENT_DETAILS из .env. Проверьте JSON-формат.")
    CARD_PAYMENT_DETAILS = {}

def get_version(file_path="VERSION"):
    absolute_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path)
    try:
        with open(absolute_file_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.warning(f"Файл {absolute_file_path} не найден. Используется версия по умолчанию '0.0.0'")
        return "0.0.0"

BOT_VERSION = get_version()

def get_bot_username():
    return BOT_USERNAME



SUBSCRIPTION_PLANS = [
    {'months': 1, 'discount_percent': 0},
    {'months': 3, 'discount_percent': 10},
    {'months': 6, 'discount_percent': 15},
]

REFERRAL_PERCENTAGE = 0.20
ADVANCED_REFERRAL_PERCENTAGE = 0.40
MIN_WITHDRAWAL_AMOUNT = 10.0
STAR_TO_RUB_RATE = 2.0
REFERRAL_PERCENTAGE = 0.10
DEFAULT_BOT_PROPERTIES = DefaultBotProperties(parse_mode=ParseMode.HTML)

from utils import bot_state

class DynamicServers(dict):
    def __getitem__(self, item):
        return bot_state.servers_cache[item]
    def get(self, item, default=None):
        return bot_state.servers_cache.get(item, default)
    def items(self):
        return bot_state.servers_cache.items()
    def keys(self):
        return bot_state.servers_cache.keys()
    def values(self):
        return bot_state.servers_cache.values()
    def __contains__(self, item):
        return item in bot_state.servers_cache
    def __len__(self):
        return len(bot_state.servers_cache)
    def __iter__(self):
        return iter(bot_state.servers_cache)

SERVERS = DynamicServers()
TARIFFS = {
    'lite': {'name': '💡 Lite', 'ram_mb': 512, 'disk_gb': 5, 'price_rub': 59},
    'pro':  {'name': '🚀 Pro',  'ram_mb': 1024, 'disk_gb': 10, 'price_rub': 129},
}

IMAGES = {
    'hikka':  {'name': '🌕 Hikka', 'image_name': 'hikariatama/hikka:latest'},
    'heroku': {'name': '🪐 Heroku', 'image_name': 'hikariatama/hikka:latest'},
}
