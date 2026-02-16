"""Register all route blueprints with the Flask app.

Each blueprint is registered twice:
  1. Under ``/api/v1/`` – the canonical, versioned path.
  2. At the root ``/``   – legacy backward-compatible paths so that
     existing tests and clients continue to work without changes.
"""
from flask import Flask

API_V1_PREFIX = "/api/v1"


def register_routes(app: Flask):
    """Import and register every blueprint (versioned + legacy)."""
    from app.routes.health import health_bp
    from app.routes.agents import agents_bp
    from app.routes.clients import clients_bp
    from app.routes.users import users_bp
    from app.routes.mcp import mcp_bp
    from app.routes.skills import skills_bp

    blueprints = [health_bp, agents_bp, clients_bp, users_bp, mcp_bp, skills_bp]

    for bp in blueprints:
        # Versioned endpoint (canonical)
        app.register_blueprint(bp, url_prefix=API_V1_PREFIX, name=f"v1_{bp.name}")
        # Legacy endpoint (backward compat – no prefix)
        app.register_blueprint(bp)

