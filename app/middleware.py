"""Request/response logging middleware."""
import logging
import time

from flask import Flask, g, request

logger = logging.getLogger(__name__)


def register_request_logging(app: Flask):
    """Add before/after request hooks that log every HTTP request."""

    @app.before_request
    def _log_request_start():
        g.start_time = time.time()

    @app.after_request
    def _log_request_end(response):
        duration_ms = (time.time() - getattr(g, "start_time", time.time())) * 1000
        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response

