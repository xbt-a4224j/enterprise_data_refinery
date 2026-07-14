"""FastAPI application factory."""

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from edr.db import get_session

BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise Data Refinery", version="0.1.0")

    static_dir = BASE_DIR / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    def health(session: Session = Depends(get_session)) -> JSONResponse:
        db_ok = True
        try:
            session.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return JSONResponse({"status": "ok", "db": db_ok})

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "base.html", {"title": "Overview"})

    return app


app = create_app()
