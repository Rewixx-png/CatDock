from aiogram import Router
from .list import router as list_router
from .menu import router as menu_router
from .power import router as power_router
from .deletion import router as deletion_router

router = Router()

router.include_router(list_router)
router.include_router(menu_router)
router.include_router(power_router)
router.include_router(deletion_router)
