from fastapi import APIRouter, Depends
from api.dependencies import get_current_user_id
import database as db

router = APIRouter()

@router.get("/history")
async def game_history(user_id: int = Depends(get_current_user_id)):
    hist = await db.get_user_game_history(user_id, limit=50)
    return {"status": "success", "data": hist}
