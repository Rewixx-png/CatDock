from fastapi import APIRouter
from .dashboard import router as dashboard_router
from .users import router as users_router
from .containers import router as containers_router
from .support import router as support_router
from .logs import router as logs_router
from .system import router as system_router
from .marketing import router as marketing_router
from .servers import router as servers_router
from .finance import router as finance_router 

router = APIRouter()

router.include_router(dashboard_router)
router.include_router(users_router)
router.include_router(containers_router)
router.include_router(support_router)
router.include_router(logs_router)
router.include_router(system_router)
router.include_router(marketing_router)
router.include_router(servers_router)
router.include_router(finance_router) 

__all__ = ["router"]
