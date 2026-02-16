"""Persistence helpers – write in-memory state to MongoDB.

.. deprecated::
    All persistence is now handled by the Data Access Layer (``app.dal``).
    This module is kept for backward compatibility but is no longer imported
    by any route handler.
"""
import logging
from typing import Any, Dict

from app.config import TEST_MODE
from app import models

logger = logging.getLogger(__name__)


def save_client_registry():
    """Persist the client registry to MongoDB only (no-op in TEST_MODE)."""
    if TEST_MODE or not models.USE_MONGO or models.client_registry_col is None:
        return
    try:
        for client_name, api_url in models.client_registry.items():
            if client_name == "agent_map":
                continue
            agent_id = models.client_registry.get("agent_map", {}).get(client_name)
            models.client_registry_col.update_one(
                {"client_name": client_name},
                {"$set": {"api_url": api_url, "agent_id": agent_id}},
                upsert=True,
            )
    except Exception as e:
        logger.error("Error saving client registry to MongoDB: %s", e)


def save_registry():
    """Persist the agent registry to MongoDB only (no-op in TEST_MODE)."""
    if TEST_MODE or not models.USE_MONGO or models.agent_registry_col is None:
        return
    try:
        for agent_id, agent_url in models.registry.items():
            if agent_id == "agent_status":
                continue
            status = models.registry.get("agent_status", {}).get(agent_id, {})
            mongo_doc = {"agent_id": agent_id, "agent_url": agent_url, **status}
            models.agent_registry_col.update_one(
                {"agent_id": agent_id},
                {"$set": mongo_doc},
                upsert=True,
            )
    except Exception as e:
        logger.error("Error saving agent registry to MongoDB: %s", e)


def build_agent_payload(agent_id: str) -> Dict[str, Any]:
    """Construct a richer agent payload used by search and agent detail endpoints."""
    agent_url = models.registry.get(agent_id)
    status_obj = models.registry.get("agent_status", {}).get(agent_id, {})
    return {
        "agent_id": agent_id,
        "agent_url": agent_url,
        "api_url": status_obj.get("api_url"),
        "alive": status_obj.get("alive", False),
        "assigned_to": status_obj.get("assigned_to"),
        "last_update": status_obj.get("last_update"),
        "capabilities": status_obj.get("capabilities", []),
        "tags": status_obj.get("tags", []),
    }

