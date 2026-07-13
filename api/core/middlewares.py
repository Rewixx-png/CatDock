from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot
from api.logging_middleware import WebLoggingMiddleware

def setup_middlewares(app: FastAPI, bot: Bot):
    app.add_middleware(
        CORSMiddleware, 
        allow_origins=["*"], 
        allow_credentials=True, 
        allow_methods=["*"], 
        allow_headers=["*"]
    )

    app.add_middleware(WebLoggingMiddleware, bot=bot)
