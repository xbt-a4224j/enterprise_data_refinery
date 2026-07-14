"""Alerting sink: always logs; optionally posts to a Slack webhook if configured."""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from edr.config import get_settings
from edr.logging import log


def alert(session: Session, message: str, **context) -> None:
    log(session, "error", message, logger="alert", **context)
    webhook = get_settings().slack_webhook
    if webhook:
        try:
            httpx.post(webhook, json={"text": f":rotating_light: {message} — {context}"}, timeout=5)
        except Exception:  # noqa: BLE001  alerting must never break the pipeline
            pass
