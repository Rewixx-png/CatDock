#!/usr/bin/env python3
"""CatDock API server — standalone FastAPI for terminal WebSocket and REST API."""
import asyncio
import sys
import logging
import uvicorn

sys.path.insert(0, '.')

from loader import bot
from broker import broker
from config import SENTRY_DSN
from utils.logger import setup_logger
import database as db


def create_app():
    """Build the standalone terminal application without starting services."""
    from api import setup_api_server

    app = setup_api_server(bot)

    @app.get("/health", tags=["Health"])
    async def service_health():
        return {"status": "ok", "service": "catdock-terminal"}

    return app


async def main():
    setup_logger()

    if SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)

    await db.init_db()
    await broker.startup()

    api_app = create_app()

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8082
    config = uvicorn.Config(app=api_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    logging.info(f"CatDock API on port {port}")
    try:
        await server.serve()
    finally:
        await broker.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
