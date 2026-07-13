from .main_menu import router as main_menu_router
from .users import router as user_management_router
from .container_management import router as container_management_router
from .give_container import router as give_container_router
from .give_admin_container import router as give_admin_container_router
from .chat_info_handler import router as chat_info_router
from .terminal_handler import router as terminal_router
from .diagnostics_handler import router as diagnostics_router
from .change_container_server import router as change_container_server_router
from .broadcast_handler import router as broadcast_router
from .image_updater import router as image_updater_router
from .orphaned_container_handler import router as orphaned_container_router
from .chat_give_container import router as chat_give_container_router
from .chat_balance import router as chat_balance_router
from .server_management import router as server_management_router
from .check_container_handler import router as check_container_router
from .upgrade_cpu_admin import router as upgrade_cpu_admin_router
from .mass_unfreeze_handler import router as mass_unfreeze_router
from .fixloop_handler import router as fixloop_router
from .session_cleaner import router as session_cleaner_router
from .htop_handler import router as htop_router
from .drestart import router as drestart_router
from .dstats_handler import router as dstats_router

all_routers = [
    main_menu_router,
    user_management_router,
    container_management_router,
    give_container_router,
    give_admin_container_router,
    chat_info_router,
    terminal_router,
    diagnostics_router,
    change_container_server_router,
    broadcast_router,
    image_updater_router,
    orphaned_container_router,
    chat_give_container_router,
    chat_balance_router,
    server_management_router,
    check_container_router,
    upgrade_cpu_admin_router,
    mass_unfreeze_router,
    fixloop_router,
    session_cleaner_router,
    htop_router,
    drestart_router,
    dstats_router,
]
