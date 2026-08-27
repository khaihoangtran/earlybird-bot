"""
Flask health-check server.

Render (and most PaaS providers) require Web Services to bind `$PORT` and
respond to HTTP requests, even though this bot's real work happens via
Telegram polling. This module runs a minimal Flask app on a background
daemon thread purely to satisfy that requirement.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Flask, jsonify

from app.logging_config import get_logger

logger = get_logger()


def create_health_app() -> Flask:
    """Build the Flask app exposing `/health` and `/` endpoints."""
    flask_app = Flask(__name__)

    @flask_app.get("/health")
    def health() -> tuple:
        return jsonify(
            status="ok",
            service="checkin-bot",
            time=datetime.now(timezone.utc).isoformat(),
        ), 200

    @flask_app.get("/")
    def index() -> tuple:
        return jsonify(status="alive", message="Telegram check-in bot is running"), 200

    return flask_app


def run_health_server(port: int) -> None:
    """Run the Flask health server. Intended to be called on a daemon thread."""
    flask_app = create_health_app()
    try:
        flask_app.run(host="0.0.0.0", port=port, use_reloader=False)
    except Exception:
        logger.exception("Flask health server crashed")
