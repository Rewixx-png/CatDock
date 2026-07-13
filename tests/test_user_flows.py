import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

import database as db
from states.user_states import UserBotCreateState, UserBotManageState
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from config import TARIFFS

from handlers.common.base.main_flow import cmd_start
from handlers.common.base.settings import set_user_lang

from handlers.userbot.creation.menu import start_creation_hub, select_category, set_option_and_return_to_hub
from handlers.userbot.creation.confirmation import show_final_confirmation
from handlers.userbot.creation.execution import confirm_creation_handler as confirm_creation

from handlers.userbot.manager.list import my_userbots_menu_handler as my_userbots_menu
from handlers.userbot.manager.menu import manage_bot_entry
from handlers.userbot.manager.power import restart_bot_handler

from pytest_mock import MockerFixture
from utils import bot_state

@pytest.fixture
def user_session():
    storage = MemoryStorage()
    user_id = 1001

    mock_event = AsyncMock()
    mock_event.from_user.id = user_id
    mock_event.from_user.username = "test_user"
    mock_event.from_user.first_name = "Test"

    mock_event.message.edit_text = AsyncMock()
    mock_event.message.edit_caption = AsyncMock()
    mock_event.message.delete = AsyncMock()
    mock_event.message.answer = AsyncMock()
    mock_event.answer = AsyncMock()
    mock_event.delete = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.get_me.return_value.username = "TestBot"

    mock_event.bot = mock_bot
    mock_event.message.bot = mock_bot

    state = FSMContext(storage=storage, key=MagicMock(chat_id=user_id, user_id=user_id))

    return mock_event, state, user_id

@pytest.mark.asyncio
async def test_new_user_purchase_flow(user_session, mocker: MockerFixture):
    mock_event, state, user_id = user_session

    bot_state.servers_cache['de-1'] = {'name': 'Test Server DE-1', 'ip': '1.1.1.1', 'active': True}

    mocker.patch('utils.docker.create_container', return_value=('new-test-container', 12345, 'http://new.test'))
    mocker.patch('utils.docker.find_optimal_server', return_value='de-1')
    mocker.patch('utils.network_checker.get_server_ram_usage', return_value=50)

    mocker.patch('utils.worker_tasks.task_create_container.kiq', new_callable=AsyncMock)

    await cmd_start(mock_event, state)

    print("Шаг 1 OK: /start выполнен.")

    mock_event.data = "set_lang:ru"
    await set_user_lang(mock_event, state, mock_event.bot)
    lang = await db.get_user_language(user_id)
    assert lang == 'ru'
    print("Шаг 2 OK: Язык установлен.")

    mock_event.data = "tariffs"
    await start_creation_hub(mock_event, state, mock_event.bot)
    assert await state.get_state() == UserBotCreateState.hub_selection
    print("Шаг 3 OK: Перешли к конструктору.")

    mock_event.data = "create_select:tariff"
    await select_category(mock_event, state)
    assert await state.get_state() == UserBotCreateState.choosing_tariff
    print("Шаг 4 OK: Перешли к выбору тарифа.")

    mock_event.data = "create_set:tariff:basic"
    await db.update_user_balance(user_id, 100.0)
    await set_option_and_return_to_hub(mock_event, state, mock_event.bot)
    assert await state.get_state() == UserBotCreateState.hub_selection
    assert (await state.get_data())['tariff_id'] == 'basic'
    print("Шаг 5 OK: Выбрали тариф, вернулись в хаб.")

    mock_event.data = "create_select:image"
    await select_category(mock_event, state)
    assert await state.get_state() == UserBotCreateState.choosing_image
    print("Шаг 6 OK: Перешли к выбору образа.")

    mock_event.data = "create_set:image:hikka"
    await set_option_and_return_to_hub(mock_event, state, mock_event.bot)
    assert await state.get_state() == UserBotCreateState.hub_selection
    assert (await state.get_data())['image_id'] == 'hikka'
    print("Шаг 7 OK: Выбрали образ, вернулись в хаб.")

    mock_event.data = "create_hub:confirm"
    await show_final_confirmation(mock_event, state)
    assert await state.get_state() == UserBotCreateState.confirming_creation
    print("Шаг 8 OK: Перешли к подтверждению.")

    mock_event.data = "confirm_creation"
    await confirm_creation(mock_event, state, mock_event.bot)

    assert await state.get_state() is None

    balance = await db.get_user_balance(user_id)
    expected_price = TARIFFS['basic']['price_rub'] * (1 - 0.10)
    assert round(balance, 2) == round(100.0 - expected_price, 2)

    print(f"Шаг 9 OK: Баланс списан корректно (100 - {expected_price} = {balance}).")

@pytest.mark.asyncio
async def test_container_management_flow(user_session, mocker: MockerFixture):
    mock_event, state, user_id = user_session

    bot_state.servers_cache['de-1'] = {'name': 'Test Server DE-1', 'ip': '1.1.1.1', 'active': True}

    await db.add_user(user_id, "test_user", "Test User")
    await db.add_user_container(user_id, 'de-1', 'manage-test', 'hikka', 'basic', 54321, 'http://manage.test')
    container_id = (await db.get_user_containers(user_id))[0]['id']

    mocker.patch('utils.docker.get_container_status', return_value='running')
    mocker.patch('utils.docker.get_container_stats', return_value={'cpu_raw': '1%', 'ram_raw': '10MiB / 10%'})
    mocker.patch('utils.docker.get_session_status', return_value='active')

    mocker.patch('utils.worker_tasks.task_container_power_action.kiq', new_callable=AsyncMock)

    mock_event.data = "my_userbots"
    await my_userbots_menu(mock_event, state)
    print("Шаг 1 OK: Открыли список юзерботов.")

    mock_event.data = f"manage_bot:{container_id}"
    await manage_bot_entry(mock_event, state, mock_event.bot)
    assert await state.get_state() == UserBotManageState.managing
    print("Шаг 2 OK: Перешли в меню управления.")

    mock_event.data = f"restart_bot:{container_id}"
    await restart_bot_handler(mock_event, state, mock_event.bot)

    assert await state.get_state() == UserBotManageState.managing
    print("Шаг 3 OK: Команда рестарта вызвана. Тест пройден!")
