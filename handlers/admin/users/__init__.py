from aiogram import Router
from .list import router as list_router
from .profile import router as profile_router
from .edit import router as edit_router
from .delete import router as delete_router
from .containers import router as containers_router

router = Router()

router.include_router(list_router)
router.include_router(profile_router)
router.include_router(edit_router)
router.include_router(delete_router)
router.include_router(containers_router)
