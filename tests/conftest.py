import pytest
import os
import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db

PROD_DB_NAME = "catdock_db"

@pytest.fixture(scope="function", autouse=True)
async def setup_test_database(monkeypatch):
    """
    Безопасная настройка БД для тестов.
    Если обнаружена продовая БД, мы МОКАЕМ подключение, чтобы не стереть данные.
    """
    current_db = os.getenv("PG_NAME", PROD_DB_NAME)

    if current_db == PROD_DB_NAME:
        print(f"\n🛡️  SAFETY LOCK: Обнаружена прод-база '{current_db}'. Подключение заблокировано.")
        print("   Все запросы к БД будут перехвачены (Mock).")

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()

        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        monkeypatch.setattr("database.core.init_db", AsyncMock())

        monkeypatch.setattr("database.core.pool", mock_pool)
        monkeypatch.setattr("database.core.get_db", AsyncMock(return_value=mock_pool))

        mock_conn.execute = AsyncMock()
        
    else:
        
        await db.init_db()

        pool = await db.get_db()
        async with pool.acquire() as conn:
            await conn.execute("""
                TRUNCATE users, user_containers, promo_codes, 
                support_tickets, support_messages, active_games, 
                game_history, payment_requests CASCADE
            """)

    yield

    if current_db != PROD_DB_NAME:
        pool = await db.get_db()
        if pool:
            await pool.close()

@pytest.fixture
def mock_bot():
    """Фикстура для мока объекта бота Aiogram"""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.get_chat = AsyncMock(return_value=MagicMock(username="TestUser", full_name="Test User"))
    return bot

@pytest.fixture
def mock_docker(mocker):
    """Фикстура для мока Docker утилит"""
    dm = mocker.patch('utils.docker')
    dm.create_container = AsyncMock(return_value=('test-container', 10001, 'http://login'))
    dm.delete_container = AsyncMock(return_value=None)
    dm.start_container = AsyncMock(return_value=None)
    dm.stop_container = AsyncMock(return_value=None)
    dm.get_container_status = AsyncMock(return_value='running')
    return dm
