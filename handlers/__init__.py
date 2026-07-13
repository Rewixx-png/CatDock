from aiogram import Router
import logging

from .admin import all_routers as admin_routers
from .common import all_routers as common_routers
from .profile import all_routers as profile_routers
from .userbot import all_routers as userbot_routers
from .support_handlers import router as support_router


def check_routers(router_list, package_name):
    for i, r in enumerate(router_list):
        if not isinstance(r, Router):
            error_message = (
                f"\n\n==================== CRITICAL ROUTER ERROR ====================\n"
                f"ERROR: Invalid object in router list from '{package_name}'.\n"
                f"Index #{i} is NOT a Router instance.\n"
                f"Object: {r}\n"
                f"Type: {type(r)}\n\n"
                f"ACTION: Check /handlers/{package_name}/__init__.py\n"
                f"================================================================\n"
            )
            logging.critical(error_message)
            raise TypeError(error_message)
    return router_list


checked_admin_routers = check_routers(admin_routers, "admin")
checked_common_routers = check_routers(common_routers, "common")
checked_profile_routers = check_routers(profile_routers, "profile")
checked_userbot_routers = check_routers(userbot_routers, "userbot")

routers_list = [
    *checked_admin_routers,
    support_router,
    *checked_profile_routers,
    *checked_userbot_routers,
    *checked_common_routers,
]
