from aiogram import Router
from .hub import router as hub_router
from .methods import router as methods_router
from .amount import router as amount_router
from .confirmation import router as confirmation_router
from .manual import router as manual_router

router = Router()

router.include_router(hub_router)
router.include_router(methods_router)
router.include_router(amount_router)
router.include_router(confirmation_router)
router.include_router(manual_router)
