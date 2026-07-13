from fastapi import FastAPI
from api.routers import (
    users, containers, auth, system, admin,
    public, support, billing
)
from api.routers.system import terminal_websocket_handler


def setup_routes(app: FastAPI):
    app.include_router(auth, prefix="/api/v1/auth")
    app.include_router(public, prefix="/api/v1/public")
    app.include_router(public, prefix="")

    app.include_router(users, prefix="/api/v1/user")
    app.include_router(containers, prefix="/api/v1/user")
    app.include_router(support, prefix="/api/v1/user/support")
    app.include_router(billing, prefix="/api/v1/user")

    app.include_router(system, prefix="/api/v1/terminal")
    app.include_router(admin, prefix="/api/v1/admin")

    app.add_api_websocket_route("/ws", terminal_websocket_handler)
