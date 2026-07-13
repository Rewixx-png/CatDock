from .deposit import router as deposit_user_router
from .deposit_admin_actions import router as deposit_admin_router
from .profile_handlers import router as profile_router
from .withdrawal_handlers import router as withdrawal_router

from .session_generator import router as session_router
from .login_command_handler import router as login_router
from .settings_handler import router as settings_router

all_routers = [
    deposit_user_router,
    deposit_admin_router,
    profile_router,
    withdrawal_router,
    
    session_router,
    login_router,
    settings_router,
]
