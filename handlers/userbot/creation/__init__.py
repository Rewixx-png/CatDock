from aiogram import Router
from .menu import router as menu_router
from .confirmation import router as confirmation_router
from .execution import router as execution_router
from .manual import router as manual_router

router = Router()

router.include_router(menu_router)
router.include_router(manual_router)
router.include_router(confirmation_router)
router.include_router(execution_router)
