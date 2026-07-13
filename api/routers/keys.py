from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import get_current_user_id
import database as db

router = APIRouter(tags=["Keys"])

@router.post("/generate")
async def generate_key(user_id: int = Depends(get_current_user_id)):
    token = await db.create_web_token(user_id)
    if not token: raise HTTPException(status_code=500)
    return {"status": "success", "token": token}

@router.post("/revoke")
async def revoke_keys(user_id: int = Depends(get_current_user_id)):
    await db.revoke_all_web_tokens(user_id)
    return {"status": "success", "message": "Keys revoked"}
