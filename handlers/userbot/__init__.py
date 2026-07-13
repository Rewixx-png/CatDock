from .creation import router as creation_router
from .manager import router as management_router
from .change_image import router as change_image_router
from .change_server import router as change_server_router
from .reinstall import router as reinstall_router
from .extend_handlers import router as extend_router
from .change_name import router as change_name_router
from .logs_handler import router as logs_router
from .interactive_login import router as interactive_login_router
from .transfer_handlers import router as transfer_router

all_routers = [
    creation_router,
    management_router,
    change_image_router,
    change_server_router,
    reinstall_router,
    extend_router,
    change_name_router,
    logs_router,
    interactive_login_router,
    transfer_router,
]
