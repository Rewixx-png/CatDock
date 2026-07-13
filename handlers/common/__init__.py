from .base import router as common_router
from .inline_query_handler import router as inline_query_router
from .chosen_inline_result_handler import router as chosen_inline_result_router
from .unhandled import router as unhandled_router
from .permission_error import router as permission_error_router 

all_routers = [
    inline_query_router,
    chosen_inline_result_router,
    common_router,
    permission_error_router, 
    unhandled_router, 
]
