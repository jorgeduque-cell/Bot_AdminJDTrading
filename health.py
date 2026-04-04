# -*- coding: utf-8 -*-
"""
Health check server — keeps Render free Web Service alive.
Includes a self-ping mechanism to prevent Render from sleeping the service.
"""
import threading
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen
from urllib.error import URLError
import os

logger = logging.getLogger(__name__)

# ── Self-ping interval (seconds) ─────────────────────────────────────────
# Render free tier sleeps after 15 min of inactivity.
# We ping every 10 min to stay well within the window.
PING_INTERVAL_SECONDS = 10 * 60  # 10 minutes


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal handler: responds 200 OK to any GET request."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"JD Trading Bot - Online")

    def log_message(self, format, *args):
        pass  # Silence default logging to keep console clean


def _self_ping_loop(url: str):
    """
    Background loop: hits the health endpoint every PING_INTERVAL_SECONDS
    to prevent Render free tier from sleeping the service.
    """
    while True:
        time.sleep(PING_INTERVAL_SECONDS)
        try:
            response = urlopen(url, timeout=15)
            logger.info(
                "[KeepAlive] Ping OK — status %s", response.status
            )
        except URLError as exc:
            logger.warning("[KeepAlive] Ping failed — %s", exc)
        except Exception as exc:
            logger.warning("[KeepAlive] Unexpected error — %s", exc)


def start_health_server():
    """Start HTTP server + self-ping thread (non-blocking)."""
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)

    # ── Health server thread ──────────────────────────────────────────
    server_thread = threading.Thread(
        target=server.serve_forever, daemon=True
    )
    server_thread.start()

    # ── Self-ping (keep-alive) thread ─────────────────────────────────
    # Build the public URL from Render's env var, fallback to localhost
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        ping_url = render_url.rstrip("/") + "/"
    else:
        ping_url = f"http://localhost:{port}/"

    ping_thread = threading.Thread(
        target=_self_ping_loop, args=(ping_url,), daemon=True
    )
    ping_thread.start()
    logger.info(
        "[KeepAlive] Self-ping activo → %s cada %d min",
        ping_url, PING_INTERVAL_SECONDS // 60,
    )

    return port
