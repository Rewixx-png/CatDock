from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from aiogram import Bot
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
import os

from api.core.routes import setup_routes
from api.core.middlewares import setup_middlewares
from api.core.events import setup_event_handlers
from api.exception_handlers import global_exception_handler, validation_exception_handler

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (StarletteHTTPException, OSError):
            if path.startswith("api"):
                raise StarletteHTTPException(status_code=404)
            return await super().get_response("index.html", scope)

def setup_api_server(bot: Bot) -> FastAPI:
    app = FastAPI(
        title="CatDock API Platform",
        description="Professional API for managing Telegram UserBots containers and infrastructure.",
        version="5.0.0",
        docs_url=None, 
        redoc_url=None,
        openapi_url="/api/openapi.json"
    )
    app.state.bot = bot

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    setup_middlewares(app, bot)
    setup_routes(app)
    setup_event_handlers(app, bot)

    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.get("/api/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        html_response = get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title="CatDock API Reference",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_ui_parameters={
                "defaultModelsExpandDepth": -1, 
                "docExpansion": "none",         
                "filter": True,                 
                "syntaxHighlight.theme": "obsidian" 
            }
        )

        custom_css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Fira+Code:wght@400;500&display=swap');

            body, .swagger-ui {
                background-color: #0f172a !important;
                color: #cbd5e1 !important;
                font-family: 'Inter', sans-serif !important;
            }

            /* FIX: Убираем белый блок авторизации и делаем его темным */
            .swagger-ui .scheme-container {
                background-color: #1e293b !important;
                box-shadow: none !important;
                border-bottom: 1px solid #334155 !important;
                padding: 10px 0 !important;
            }

            .swagger-ui .dialog-ux .modal-ux {
                background-color: #1e293b !important;
                border: 1px solid #334155 !important;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
                color: #e2e8f0 !important;
            }

            .swagger-ui .dialog-ux .modal-ux-header {
                border-bottom: 1px solid #334155 !important;
            }

            .swagger-ui .dialog-ux .modal-ux-header h3 {
                color: #f8fafc !important;
            }

            .swagger-ui .dialog-ux .modal-ux-content {
                color: #cbd5e1 !important;
            }
            
            .swagger-ui .auth-container {
                border-bottom: 1px solid #334155 !important;
            }

            .swagger-ui .auth-container input[type=text], 
            .swagger-ui .auth-container input[type=password] {
                background-color: #0f172a !important;
                border: 1px solid #334155 !important;
                color: #fff !important;
            }

            .swagger-ui .auth-btn-wrapper .btn-done {
                background-color: #22c55e !important;
                border-color: #22c55e !important;
                color: #fff !important;
            }
            
            .swagger-ui .auth-wrapper .authorize {
                border-color: #22c55e !important;
                color: #22c55e !important;
            }
            
            .swagger-ui .auth-wrapper .authorize svg {
                fill: #22c55e !important;
            }

            /* Topbar */
            .swagger-ui .topbar { display: none !important; }

            /* Текст заголовков и описаний */
            .swagger-ui .info .title, .swagger-ui .info h1, .swagger-ui .info h2, .swagger-ui .info h3 {
                color: #f8fafc !important;
            }
            .swagger-ui .info p, .swagger-ui .info li {
                color: #94a3b8 !important;
            }

            /* Блоки методов */
            .swagger-ui .opblock {
                background-color: #1e293b !important;
                border: 1px solid #334155 !important;
                border-radius: 8px !important;
                box-shadow: none !important;
                margin-bottom: 10px !important;
            }

            .swagger-ui .opblock .opblock-summary {
                border-bottom: none !important;
            }

            /* FIX: Цвет пути метода (чтобы не сливался) */
            .swagger-ui .opblock .opblock-summary-path {
                color: #e2e8f0 !important;
                font-family: 'Fira Code', monospace !important;
                font-weight: 600 !important;
            }

            .swagger-ui .opblock .opblock-summary-description {
                color: #94a3b8 !important;
            }

            /* Инпут поиска/фильтра */
            .swagger-ui .filter .operation-filter-input {
                background-color: #020617 !important;
                color: #fff !important;
                border: 1px solid #334155 !important;
                padding: 8px !important;
                border-radius: 6px !important;
            }

            /* Кнопка Authorize */
            .swagger-ui .btn.authorize {
                color: #22c55e !important;
                border-color: #22c55e !important;
                background-color: transparent !important;
            }
            .swagger-ui .btn.authorize svg {
                fill: #22c55e !important;
            }

            /* Методы (Badge) */
            .swagger-ui .opblock.opblock-post .opblock-summary-method { background: #3b82f6 !important; }
            .swagger-ui .opblock.opblock-get .opblock-summary-method { background: #22c55e !important; }
            .swagger-ui .opblock.opblock-delete .opblock-summary-method { background: #ef4444 !important; }
            .swagger-ui .opblock.opblock-put .opblock-summary-method { background: #f59e0b !important; }

            /* Раскрытый блок */
            .swagger-ui .opblock.is-open .opblock-summary {
                border-bottom: 1px solid #334155 !important;
            }
            .swagger-ui .opblock-body {
                background-color: #0f172a !important; /* Внутри метода темнее */
                border-top: 1px solid #334155 !important;
            }

            /* Таблицы параметров */
            .swagger-ui table thead tr td, .swagger-ui table thead tr th {
                color: #e2e8f0 !important;
                border-bottom: 1px solid #334155 !important;
            }
            .swagger-ui .parameters-col_description {
                color: #cbd5e1 !important;
            }
            .swagger-ui input[type=text], .swagger-ui textarea, .swagger-ui select {
                background-color: #1e293b !important;
                color: #fff !important;
                border: 1px solid #334155 !important;
            }

            /* Убираем белые треугольники */
            .swagger-ui .opblock-summary-control-sign {
                filter: invert(1);
                opacity: 0.7;
            }
            .swagger-ui .expand-methods svg {
                fill: #94a3b8 !important;
            }
        </style>
        """

        content = html_response.body.decode("utf-8")
        content = content.replace("</head>", f"{custom_css}</head>")
        return HTMLResponse(content=content)

    async def terminal_response() -> HTMLResponse:
        terminal_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "terminal.html")
        if not os.path.exists(terminal_path):
            raise StarletteHTTPException(status_code=404, detail="Terminal template not found")
        with open(terminal_path, "r", encoding="utf-8") as terminal_file:
            return HTMLResponse(content=terminal_file.read())

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def terminal_root():
        return await terminal_response()

    @app.get("/terminal.html", response_class=HTMLResponse, include_in_schema=False)
    async def terminal_page():
        return await terminal_response()

    @app.get("/setup.html", response_class=HTMLResponse, include_in_schema=False)
    async def setup_page():
        setup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "setup.html")
        if not os.path.exists(setup_path):
            raise StarletteHTTPException(status_code=404, detail="Setup template not found")
        with open(setup_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return app
