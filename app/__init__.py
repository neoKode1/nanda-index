"""Flask application factory."""
import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import ENABLE_FEDERATION, TEST_MODE


def _setup_logging():
    """Configure structured logging for the application."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format=fmt)


SWAGGER_TEMPLATE = {
    "info": {
        "title": "NANDA Index API",
        "description": "Unified agent registry for discovery and interoperability across agent ecosystems.",
        "version": "1.0.0",
        "contact": {"name": "My-Agent-Too", "url": "https://github.com/neoKode1/nanda-index"},
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "tags": [
        {"name": "Health", "description": "Health checks and statistics"},
        {"name": "Agents", "description": "Agent registration, lookup, search, and management"},
        {"name": "Clients", "description": "Client allocation and listing"},
        {"name": "Users", "description": "User management (signup, setup)"},
        {"name": "MCP", "description": "MCP registry lookups"},
        {"name": "Skills", "description": "Skill taxonomy mapping"},
    ],
}

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}


def create_app() -> Flask:
    """Create and configure the Flask application."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    application = Flask(__name__)
    CORS(application)

    # Rate limiting – disabled in TEST_MODE to keep tests fast
    default_limit = os.getenv("RATE_LIMIT_DEFAULT", "200 per minute")
    limiter = Limiter(
        get_remote_address,
        app=application,
        default_limits=[default_limit],
        storage_uri="memory://",
        enabled=not TEST_MODE,
    )
    application.limiter = limiter  # expose for per-route overrides

    # OpenAPI / Swagger documentation
    from flasgger import Swagger
    Swagger(application, template=SWAGGER_TEMPLATE, config=SWAGGER_CONFIG)

    # Initialize database / in-memory state
    from app.models import init_db
    init_db()

    # Request logging middleware
    from app.middleware import register_request_logging
    register_request_logging(application)

    # Register route blueprints
    from app.routes import register_routes
    register_routes(application)

    # Optional: Switchboard federation
    if ENABLE_FEDERATION:
        try:
            from switchboard.switchboard_routes import register_switchboard_routes
            register_switchboard_routes(application)
            logger.info("Switchboard enabled")
            logger.info("  AGNTCY_ADS_URL: %s", os.getenv("AGNTCY_ADS_URL", "not set"))
            logger.info("  OASF_SCHEMA_DIR: %s", os.getenv("OASF_SCHEMA_DIR", "auto-detect"))
        except ImportError as e:
            logger.warning("Switchboard disabled: %s", e)
            logger.info("  To enable: uv sync")
        except Exception as e:
            logger.warning("Switchboard initialization failed: %s", e)
            import traceback
            traceback.print_exc()
    else:
        logger.info("Switchboard disabled (set ENABLE_FEDERATION=true to enable)")

    return application

