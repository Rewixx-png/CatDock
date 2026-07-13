#!/usr/bin/env python3
"""CatDock API server — standalone FastAPI for terminal WebSocket and REST API."""
import asyncio
import sys
import logging
import uvicorn

sys.path.insert(0, '.')

from loader import bot
from broker import broker
from config import TOKEN, SENTRY_DSN
from utils.logger import setup_logger
import database as db


async def main():
    setup_logger()

    if SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)

    await db.init_db()
    await broker.startup()

    from api import setup_api_server
    api_app = setup_api_server(bot)

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8082
    config = uvicorn.Config(app=api_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    logging.info(f"CatDock API on port {port}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
