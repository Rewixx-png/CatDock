import pytest
import importlib

ALL_HANDLER_MODULES = [
    "handlers.admin.broadcast_handler",
    "handlers.admin.change_container_server",
    "handlers.admin.chat_info_handler",
    "handlers.admin.container_management",
    "handlers.admin.diagnostics_handler",
    "handlers.admin.give_container",
    "handlers.admin.image_updater",
    "handlers.admin.main_menu",
    "handlers.admin.terminal_handler",
    
    "handlers.admin.users.list",
    "handlers.admin.users.profile",
    "handlers.admin.users.edit",
    "handlers.admin.users.delete",
    "handlers.admin.users.containers",
    
    "handlers.common.chosen_inline_result_handler",
    "handlers.common.errors_handler",
    "handlers.common.inline_query_handler",
    "handlers.common.base.main_flow",
    "handlers.common.base.navigation",
    "handlers.common.base.info",
    "handlers.common.base.settings",
    
    "handlers.moderation.captcha",
    "handlers.moderation.commands",
    "handlers.payments.crypto_pay_handler",
    "handlers.payments.star_payment_handler",
    
    "handlers.profile.bonus_handler",
    "handlers.profile.deposit_admin_actions",
    "handlers.profile.profile_handlers",
    "handlers.profile.session_generator",
    "handlers.profile.withdrawal_handlers",
    "handlers.userbot.change_image",
    "handlers.userbot.change_name",
    "handlers.userbot.change_server",
    "handlers.userbot.extend_handlers",
    "handlers.userbot.interactive_login",
    "handlers.userbot.logs_handler",
    "handlers.userbot.manager.list",
    "handlers.userbot.manager.menu",
    "handlers.userbot.manager.power",
    "handlers.userbot.manager.deletion",
    "handlers.userbot.reinstall",
]

@pytest.mark.parametrize("module_path", ALL_HANDLER_MODULES)
def test_handler_module_imports_correctly(module_path):
    try:
        importlib.import_module(module_path)
    except (ImportError, NameError, SyntaxError) as e:
        pytest.fail(
            f"Критическая ошибка при импорте модуля '{module_path}'. "
            f"Это означает, что в файле есть синтаксическая ошибка или "
            f"неправильный импорт. Ошибка: {e}"
        )
