"""FastAPI application factory."""

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from edr.db import get_session
from edr.web.routes import router

BASE_DIR = Path(__file__).parent


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

    app.include_router(router)
    return app


app = create_app()
