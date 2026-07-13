from fastapi import FastAPI
from api.routers import public, system
from api.routers.system import terminal_websocket_handler


def setup_routes(app: FastAPI):
    app.include_router(public, prefix="/api/v1/public")
    app.include_router(public, prefix="")

    app.include_router(system, prefix="/api/v1/terminal")

    # Legacy endpoint for links created by early CatDock builds.
    app.add_api_websocket_route("/ws", terminal_websocket_handler)
