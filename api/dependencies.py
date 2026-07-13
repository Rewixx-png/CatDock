from fastapi import Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
import database as db
import logging

api_key_header = APIKeyHeader(name="X-Web-Access-Token", auto_error=False)

async def get_current_user_id(token: str | None = Security(api_key_header)) -> int:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token required"
        )

    user_data = await db.get_user_by_web_token(token)

    if not user_data:
        logging.warning(f"Auth failed for token: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired token"
        )

    if user_data.get('is_blocked'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="USER_BLOCKED"
        )

    return user_data['user_id']

async def get_current_user(user_id: int = Depends(get_current_user_id)):
    user = await db.get_user_profile(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get('is_blocked'):
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="USER_BLOCKED"
        )
        
    return user
