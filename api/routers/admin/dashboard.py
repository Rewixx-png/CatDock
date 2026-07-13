from fastapi import APIRouter, Depends
import logging
import traceback
import database.admin_queries as admin_db
from .dependencies import get_current_admin

router = APIRouter()

@router.get("/verify-access")
async def admin_verify_access(admin: dict = Depends(get_current_admin)):
    return {"status": "success", "message": "Admin access confirmed"}

@router.get("/dashboard/stats")
async def get_admin_dashboard_stats(admin: dict = Depends(get_current_admin)):
    try:
        stats, db_error = await admin_db.get_dashboard_stats()

        try:
            logs = await admin_db.get_recent_admin_logs(5)
        except Exception as log_e:
            logging.error(f"Error fetching logs: {log_e}")
            logs = []

        if db_error:
            return {
                "status": "warning",
                "message": "Данные загружены частично",
                "error_detail": db_error,
                "data": {
                    "stats": stats,
                    "recent_logs": logs
                }
            }

        return {
            "status": "success",
            "data": {
                "stats": stats,
                "recent_logs": logs
            }
        }

    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"CRITICAL DASHBOARD ERROR: {e}\n{tb}")
        return {
            "status": "error",
            "message": "Internal Server Error",
            "error_detail": f"{str(e)}\n\nTraceback:\n{tb}",
            "data": {
                "stats": {"total_users": 0, "active_containers": 0, "revenue_24h": 0, "open_tickets": 0},
                "recent_logs": []
            }
        }
