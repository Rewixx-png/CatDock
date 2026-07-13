import logging
import json
from typing import Any, Optional
from redis.asyncio import Redis
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True 
)

async def cache_get(key: str) -> Optional[Any]:
    try:
        val = await redis_client.get(key)
        return val
    except Exception as e:
        logging.warning(f"[Cache] Get error for key {key}: {e}")
        return None

async def cache_set(key: str, value: Any, ttl: int = 60):
    try:
        
        if not isinstance(value, (str, int, float)):
            value = str(value)
        await redis_client.set(key, value, ex=ttl)
    except Exception as e:
        logging.warning(f"[Cache] Set error for key {key}: {e}")

async def cache_delete(key: str):
    try:
        await redis_client.delete(key)
    except Exception as e:
        logging.warning(f"[Cache] Delete error for key {key}: {e}")
