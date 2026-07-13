from aiogram import Router
from .main_flow import router as main_flow_router
from .navigation import router as navigation_router
from .info import router as info_router
from .settings import router as settings_router

router = Router()

router.include_router(main_flow_router)
router.include_router(navigation_router)
router.include_router(info_router)
router.include_router(settings_router)
