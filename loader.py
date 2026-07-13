from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import TOKEN, REDIS_HOST, REDIS_PORT, REDIS_DB

redis_client = Redis(
    host=REDIS_HOST, 
    port=REDIS_PORT, 
    db=REDIS_DB
)

storage = RedisStorage(
    redis=redis_client, 
    key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True)
)

default_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=TOKEN, default=default_properties)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

dp = Dispatcher(storage=storage)

dp['scheduler'] = scheduler
