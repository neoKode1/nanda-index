"""JWT + API-key authentication and authorization helpers.

Auth modes
----------
* **JWT Bearer** – ``Authorization: Bearer <token>``
  Used by end-user clients (signup/setup flows will eventually issue JWTs).
* **API Key** – ``X-API-Key: <key>``
  Used for service-to-service calls (agent registrations, switchboard, etc.).

During testing (``TEST_MODE=1``) or when ``AUTH_DISABLED=1`` auth is
completely bypassed so the existing test suite keeps passing.
"""
import functools
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from flask import g, jsonify, request

from app.config import TEST_MODE

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "0") == "1"

# Simple API-key store.  In production, load from a DB or Vault.
# Format: comma-separated keys in env var.
_raw_keys = os.getenv("API_KEYS", "")
API_KEYS: set[str] = {k.strip() for k in _raw_keys.split(",") if k.strip()}

# Paths that never require authentication
PUBLIC_PATHS: set[str] = {"/health", "/api/v1/health"}


# ── JWT helpers ──────────────────────────────────────────────────────────

def create_jwt(subject: str, role: str = "user", extra: dict | None = None) -> str:
    """Issue a signed JWT for *subject* (user-id / email)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and verify a JWT.  Raises ``jwt.PyJWTError`` on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── API Key helpers ──────────────────────────────────────────────────────

def generate_api_key() -> str:
    """Generate a cryptographically-secure API key."""
    return secrets.token_urlsafe(32)


def _verify_api_key(key: str) -> bool:
    """Constant-time comparison of an API key against known keys."""
    return any(hmac.compare_digest(key, k) for k in API_KEYS)


# ── Decorator ────────────────────────────────────────────────────────────

def require_auth(f=None, *, roles: list[str] | None = None):
    """Decorator that protects an endpoint with JWT or API-key auth.

    Usage::

        @agents_bp.route("/register", methods=["POST"])
        @require_auth
        def register(): ...

        @agents_bp.route("/admin/purge", methods=["POST"])
        @require_auth(roles=["admin"])
        def purge(): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Skip auth in test mode or if globally disabled
            if TEST_MODE or AUTH_DISABLED:
                g.auth_user = {"sub": "test", "role": "admin"}
                return fn(*args, **kwargs)

            # Try Bearer token first
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    claims = decode_jwt(token)
                except jwt.ExpiredSignatureError:
                    return jsonify({"error": "Token expired"}), 401
                except jwt.PyJWTError as e:
                    return jsonify({"error": f"Invalid token: {e}"}), 401

                if roles and claims.get("role") not in roles:
                    return jsonify({"error": "Insufficient permissions"}), 403
                g.auth_user = claims
                return fn(*args, **kwargs)

            # Try API key
            api_key = request.headers.get("X-API-Key", "")
            if api_key and _verify_api_key(api_key):
                g.auth_user = {"sub": "service", "role": "service"}
                return fn(*args, **kwargs)

            return jsonify({"error": "Authentication required"}), 401
        return wrapper

    if f is not None:
        # @require_auth without parentheses
        return decorator(f)
    return decorator

