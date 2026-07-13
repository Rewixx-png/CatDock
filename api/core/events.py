import logging
from fastapi import FastAPI
from aiogram import Bot

logger = logging.getLogger("API")


def setup_event_handlers(app: FastAPI, bot: Bot):
    @app.on_event("startup")
    async def on_startup():
        logger.info("CatDock API Server Started.")
