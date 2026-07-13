from fastapi import APIRouter
from .roulette import router as roulette_router
from .mines import router as mines_router
from .towers import router as towers_router
from .history import router as history_router
from .plinko import router as plinko_router

router = APIRouter()

router.include_router(roulette_router) 

router.include_router(plinko_router, prefix="/plinko")

router.include_router(mines_router)
router.include_router(towers_router)
router.include_router(history_router)
