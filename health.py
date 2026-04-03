# -*- coding: utf-8 -*-
"""
Health check server — keeps Render free Web Service alive.
A lightweight HTTP endpoint that responds to pings.
"""
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal handler: responds 200 OK to any GET request."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"JD Trading Bot - Online")

    def log_message(self, format, *args):
        pass  # Silence default logging to keep console clean


def start_health_server():
    """Start HTTP server in a background thread (non-blocking)."""
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return port
