import pytest

def test_critical_imports():
    try:
        from bot import main
        from api import setup_api_server
        from handlers import routers_list
        
        from keyboards.admin import get_admin_main_menu
        from keyboards.common_keyboards import get_main_menu_keyboard
        from keyboards.profile_keyboards import get_profile_keyboard
        from keyboards.userbot import get_my_userbots_keyboard
        from utils import worker_tasks
        
    except ImportError as e:
        pytest.fail(f"Критическая ошибка импорта, бот не сможет запуститься: {e}")

    assert True
