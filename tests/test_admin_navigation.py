import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

import database as db
from states.user_states import AdminUserState, UserBotManageState
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from config import ALL_ADMIN_IDS

from handlers.admin.users.list import manage_users_menu
from handlers.admin.users.profile import select_user_from_list
from handlers.admin.users.containers import view_user_containers
from handlers.admin.container_management import admin_manage_bot_entry
from roles import UserRole

@pytest.mark.asyncio
async def test_admin_full_navigation_flow():
    storage = MemoryStorage()
    admin_id = 1
    target_user_id = 2

    await db.add_user(admin_id, "test_admin", "Test Admin")
    await db.set_user_role(admin_id, UserRole.ADMIN.name)

    await db.add_user(target_user_id, "test_user", "Test User")
    await db.add_user_container(target_user_id, 'de-1', 'user-container', 'hikka', 'basic', 12345, 'http://test.url')

    container = (await db.get_user_containers(target_user_id))[0]
    container_id = container['id']

    mock_event = AsyncMock()
    mock_event.from_user.id = admin_id

    mock_event.message.edit_caption = AsyncMock()
    mock_event.message.edit_media = AsyncMock()
    mock_event.message.delete = AsyncMock()
    mock_event.message.answer_photo = AsyncMock()

    mock_event.answer_photo = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.get_chat.return_value = AsyncMock(id=target_user_id, username="test_user")
    mock_event.bot = mock_bot
    mock_event.message.bot = mock_bot

    state = FSMContext(storage=storage, key=MagicMock(chat_id=admin_id, user_id=admin_id))
    mock_event.data = "manage_users"

    await manage_users_menu(mock_event, state)

    assert await state.get_state() == AdminUserState.managing_user
    print("Шаг 1 OK: Перешли в список пользователей.")

    mock_event.data = f"admin_select_user:{target_user_id}:0"

    await select_user_from_list(mock_event, state)

    assert await state.get_state() == "AdminUserState:managing_user"
    data = await state.get_data()
    assert data['target_user_id'] == target_user_id
    assert data['from_page'] == 0
    print("Шаг 2 OK: Перешли в профиль пользователя.")

    mock_event.data = f"admin_view_user_containers:{target_user_id}:0"

    await view_user_containers(mock_event, state, mock_event.bot)

    assert await state.get_state() == AdminUserState.managing_user
    print("Шаг 3 OK: Перешли в список контейнеров пользователя.")

    mock_event.data = f"manage_bot:{container_id}:user:{target_user_id}:0"

    await admin_manage_bot_entry(mock_event, state, mock_event.bot)

    assert await state.get_state() == UserBotManageState.managing
    print("Шаг 4 OK: Перешли в меню управления контейнером. Состояние сменилось.")

    mock_event.data = f"admin_view_user_containers:{target_user_id}:0"

    await view_user_containers(mock_event, state, mock_event.bot)

    assert await state.get_state() == AdminUserState.managing_user
    print("Шаг 5 OK: Вернулись в список контейнеров. Состояние восстановлено.")

    mock_event.data = f"admin_select_user:{target_user_id}:0"

    await select_user_from_list(mock_event, state)

    assert await state.get_state() == "AdminUserState:managing_user"
    print("Шаг 6 OK: Вернулись в профиль пользователя.")

@pytest.mark.asyncio
async def test_get_admin_ids_logic():
    await db.add_user(1, "user", "User")
    await db.add_user(2, "admin", "Admin")
    await db.add_user(3, "owner", "OwnerDB")

    await db.set_user_role(2, UserRole.ADMIN.name)
    await db.set_user_role(3, UserRole.OWNER.name)

    admin_ids_from_db = {admin['user_id'] for admin in await db.get_all_admins()}

    admin_ids_from_config = await db.get_admin_ids()

    assert {2, 3}.issubset(admin_ids_from_db)

    assert 2 in admin_ids_from_config
    assert 3 in admin_ids_from_config

    assert 1 not in admin_ids_from_db
    assert 1 not in admin_ids_from_config
