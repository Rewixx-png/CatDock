from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot

def setup_middlewares(app: FastAPI, bot: Bot):
    app.add_middleware(
        CORSMiddleware, 
        allow_origins=["*"], 
        allow_credentials=False,
        allow_methods=["*"], 
        allow_headers=["*"]
    )
