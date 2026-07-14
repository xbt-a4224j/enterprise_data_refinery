"""Shared Jinja environment + a helper that injects common context."""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def page(request: Request, name: str, *, title: str, active: str, **ctx):
    return TEMPLATES.TemplateResponse(
        request, name, {"title": title, "active": active, **ctx}
    )
