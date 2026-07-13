import asyncpg
import logging
import os
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASS", "password")
PG_NAME = os.getenv("PG_NAME", "catdock_db")

pool: asyncpg.Pool = None

async def init_db():
    global pool
    try:
        logging.info(f"Подключение к PostgreSQL ({PG_HOST}:{PG_PORT})...")
        pool = await asyncpg.create_pool(
            user=PG_USER,
            password=PG_PASS,
            database=PG_NAME,
            host=PG_HOST,
            port=PG_PORT,
            min_size=10,
            max_size=40 
        )
        logging.info("✅ Успешное подключение к PostgreSQL.")

    except Exception as e:
        logging.critical(f"❌ Критическая ошибка подключения к PostgreSQL: {e}")
        raise e

async def get_db():
    global pool
    if not pool:
        await init_db()
    return pool

async def get_db_size() -> str:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            size = await conn.fetchval("SELECT pg_size_pretty(pg_database_size($1))", PG_NAME)
            return size or "N/A"
    except Exception as e:
        logging.error(f"Ошибка получения размера БД: {e}")
        return "Error"
