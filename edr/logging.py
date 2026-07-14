"""Structured logging: JSON to stdout + persistence to the log_events table so the
admin UI can stream logs."""

import json
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from edr.models import LogEvent

LEVELS = ("debug", "info", "warning", "error")


def _emit_stdout(level: str, logger: str, message: str, context: dict) -> None:
    line = {
        "ts": datetime.now(UTC).isoformat(),
        "level": level,
        "logger": logger,
        "message": message,
        **({"context": context} if context else {}),
    }
    sys.stdout.write(json.dumps(line) + "\n")
    sys.stdout.flush()


def log(session: Session, level: str, message: str, *, logger: str = "edr", **context) -> LogEvent:
    """Emit a structured log to stdout and persist it for the UI stream."""
    level = level.lower()
    if level not in LEVELS:
        level = "info"
    _emit_stdout(level, logger, message, context)
    ev = LogEvent(level=level, logger=logger, message=message[:2048], context=context)
    session.add(ev)
    session.flush()
    return ev


def recent_logs(
    session: Session, *, level: str | None = None, logger: str | None = None, limit: int = 200
) -> list[LogEvent]:
    stmt = select(LogEvent).order_by(LogEvent.ts.desc())
    if level:
        stmt = stmt.where(LogEvent.level == level.lower())
    if logger:
        stmt = stmt.where(LogEvent.logger == logger)
    return list(session.scalars(stmt.limit(limit)))
