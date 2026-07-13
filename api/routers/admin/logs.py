import math
from fastapi import APIRouter, Depends
import database as db
from .dependencies import get_current_admin

router = APIRouter()

@router.get("/logs")
async def admin_get_logs(page: int = 0, actor_id: int = None, target_id: int = None, type: str = None, mode: str = 'all', admin: dict = Depends(get_current_admin)):
    page_size = 50
    only_admins = (mode == 'admins')
    logs, total_count = await db.get_system_logs(page, page_size, actor_id, target_id, type, only_admins)
    total_pages = math.ceil(total_count / page_size)
    return {'status': 'success', 'data': {'logs': logs, 'pagination': {'current_page': page, 'total_pages': total_pages}}}
