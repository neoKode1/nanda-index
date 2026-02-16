"""Data Access Layer – MongoDB-first reads with in-memory fallback.

When ``USE_MONGO`` is True every read goes directly to MongoDB so the
database is the single source of truth.  The in-memory dicts in
``app.models`` are kept in sync as a **write-through cache** so that
callers migrating incrementally still work.

When ``TEST_MODE`` is active (or MongoDB is unavailable) all operations
fall back to the in-memory dicts – zero behaviour change for the test
suite.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import models
from app.config import TEST_MODE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _use_mongo() -> bool:
    """Return True when MongoDB should be the primary store."""
    return models.USE_MONGO and not TEST_MODE


def _strip_id(doc: Optional[dict]) -> Optional[dict]:
    """Remove MongoDB ``_id`` field from a document."""
    if doc and "_id" in doc:
        doc.pop("_id")
    return doc


def _build_payload(doc: dict) -> Dict[str, Any]:
    """Normalise a raw MongoDB / in-memory doc into the API payload shape."""
    return {
        "agent_id": doc.get("agent_id"),
        "agent_url": doc.get("agent_url"),
        "api_url": doc.get("api_url"),
        "alive": doc.get("alive", False),
        "assigned_to": doc.get("assigned_to"),
        "last_update": doc.get("last_update"),
        "capabilities": doc.get("capabilities", []),
        "tags": doc.get("tags", []),
    }


# ---------------------------------------------------------------------------
# Agent reads
# ---------------------------------------------------------------------------

def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    """Return a single agent payload or ``None``."""
    if _use_mongo() and models.agent_registry_col is not None:
        doc = models.agent_registry_col.find_one({"agent_id": agent_id})
        if doc:
            return _build_payload(_strip_id(doc))
        return None
    # In-memory fallback
    if agent_id in models.registry and agent_id != "agent_status":
        return _build_payload_from_memory(agent_id)
    return None


def list_agents() -> List[Dict[str, Any]]:
    """Return *all* agents as ``[{agent_id, agent_url}, ...]``."""
    if _use_mongo() and models.agent_registry_col is not None:
        docs = models.agent_registry_col.find({}, {"_id": 0, "agent_id": 1, "agent_url": 1})
        return [{"agent_id": d["agent_id"], "agent_url": d.get("agent_url")} for d in docs]
    return [
        {"agent_id": k, "agent_url": v}
        for k, v in models.registry.items()
        if k != "agent_status"
    ]


def search_agents(
    query: str = "",
    capabilities: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Search agents with optional substring, capability, and tag filters."""
    if _use_mongo() and models.agent_registry_col is not None:
        mongo_filter: dict = {}
        if query:
            mongo_filter["agent_id"] = {"$regex": query, "$options": "i"}
        if capabilities:
            mongo_filter["capabilities"] = {"$in": capabilities}
        if tags:
            mongo_filter["tags"] = {"$in": tags}
        docs = models.agent_registry_col.find(mongo_filter)
        return [_build_payload(_strip_id(d)) for d in docs]
    # In-memory fallback
    results: List[Dict[str, Any]] = []
    for aid in models.registry:
        if aid == "agent_status":
            continue
        if query and query not in aid.lower():
            continue
        payload = _build_payload_from_memory(aid)
        if capabilities:
            acaps = payload.get("capabilities") or []
            if not any(c in acaps for c in capabilities):
                continue
        if tags:
            atags = payload.get("tags") or []
            if not any(t in atags for t in tags):
                continue
        results.append(payload)
    return results


def list_mcp_servers() -> List[Dict[str, Any]]:
    """Return agents that are MCP servers (id starts with 'mcp' or has capability)."""
    if _use_mongo() and models.agent_registry_col is not None:
        docs = models.agent_registry_col.find({
            "$or": [
                {"agent_id": {"$regex": "^mcp"}},
                {"capabilities": "mcp-server"},
            ]
        })
        return [_build_payload(_strip_id(d)) for d in docs]
    # In-memory fallback
    results = []
    for aid in models.registry:
        if aid == "agent_status":
            continue
        status = models.registry.get("agent_status", {}).get(aid, {})
        caps = status.get("capabilities") or []
        if aid.startswith("mcp") or "mcp-server" in caps:
            results.append(_build_payload_from_memory(aid))
    return results


def agent_exists(agent_id: str) -> bool:
    """Check whether an agent is registered."""
    if _use_mongo() and models.agent_registry_col is not None:
        return models.agent_registry_col.count_documents({"agent_id": agent_id}, limit=1) > 0
    return agent_id in models.registry and agent_id != "agent_status"


def get_agent_status_field(agent_id: str, field: str, default=None):
    """Read a single status field for an agent."""
    agent = get_agent(agent_id)
    if agent:
        return agent.get(field, default)
    return default


# ---------------------------------------------------------------------------
# Agent writes
# ---------------------------------------------------------------------------

def register_agent(agent_id: str, agent_url: str, api_url: str) -> None:
    """Register a new agent (write-through: MongoDB + in-memory cache)."""
    now = datetime.now().isoformat()
    doc = {
        "agent_id": agent_id,
        "agent_url": agent_url,
        "api_url": api_url,
        "alive": False,
        "assigned_to": None,
        "last_update": now,
    }
    if _use_mongo() and models.agent_registry_col is not None:
        models.agent_registry_col.update_one(
            {"agent_id": agent_id}, {"$set": doc}, upsert=True,
        )
    # Keep in-memory cache in sync
    models.registry[agent_id] = agent_url
    models.registry.setdefault("agent_status", {})[agent_id] = {
        "alive": False,
        "assigned_to": None,
        "api_url": api_url,
        "last_update": now,
    }


def update_agent_status(agent_id: str, data: dict) -> Dict[str, Any]:
    """Update status fields for an agent and return the updated payload."""
    now = datetime.now().isoformat()
    update_fields: dict = {"last_update": now}
    if "alive" in data:
        update_fields["alive"] = bool(data["alive"])
    if "assigned_to" in data:
        update_fields["assigned_to"] = data["assigned_to"]
    if "capabilities" in data and isinstance(data["capabilities"], list):
        update_fields["capabilities"] = data["capabilities"]
    if "tags" in data and isinstance(data["tags"], list):
        update_fields["tags"] = data["tags"]

    if _use_mongo() and models.agent_registry_col is not None:
        models.agent_registry_col.update_one(
            {"agent_id": agent_id}, {"$set": update_fields},
        )
    # Keep in-memory cache in sync
    status = models.registry.setdefault("agent_status", {}).setdefault(agent_id, {})
    status.update(update_fields)

    return get_agent(agent_id)


def delete_agent(agent_id: str) -> None:
    """Remove an agent and unlink any clients assigned to it."""
    if _use_mongo() and models.agent_registry_col is not None:
        models.agent_registry_col.delete_one({"agent_id": agent_id})
    if _use_mongo() and models.client_registry_col is not None:
        models.client_registry_col.delete_many({"agent_id": agent_id})
    # In-memory cache
    models.registry.pop(agent_id, None)
    if "agent_status" in models.registry:
        models.registry["agent_status"].pop(agent_id, None)
    to_remove = [
        cn for cn, mapped in models.client_registry.get("agent_map", {}).items()
        if mapped == agent_id
    ]
    for cn in to_remove:
        models.client_registry.pop(cn, None)
        models.client_registry.get("agent_map", {}).pop(cn, None)


# ---------------------------------------------------------------------------
# Client reads
# ---------------------------------------------------------------------------

def list_clients() -> List[Dict[str, str]]:
    """Return all clients as ``[{client_name, status}, ...]``."""
    if _use_mongo() and models.client_registry_col is not None:
        docs = models.client_registry_col.find({}, {"_id": 0, "client_name": 1})
        return [{"client_name": d["client_name"], "status": "alive"} for d in docs]
    return [
        {"client_name": k, "status": "alive"}
        for k in models.client_registry
        if k != "agent_map"
    ]


def get_client(client_name: str) -> Optional[dict]:
    """Return a client doc or None."""
    if _use_mongo() and models.client_registry_col is not None:
        doc = models.client_registry_col.find_one({"client_name": client_name})
        return _strip_id(doc)
    if client_name in models.client_registry and client_name != "agent_map":
        agent_id = models.client_registry.get("agent_map", {}).get(client_name)
        return {"client_name": client_name, "api_url": models.client_registry[client_name], "agent_id": agent_id}
    return None


# ---------------------------------------------------------------------------
# Client writes
# ---------------------------------------------------------------------------

def allocate_client(client_name: str, agent_id: str, api_url: str) -> None:
    """Assign a client to an agent (write-through)."""
    if _use_mongo() and models.client_registry_col is not None:
        models.client_registry_col.update_one(
            {"client_name": client_name},
            {"$set": {"client_name": client_name, "api_url": api_url, "agent_id": agent_id}},
            upsert=True,
        )
    # In-memory cache
    models.client_registry[client_name] = api_url
    models.client_registry.setdefault("agent_map", {})[client_name] = agent_id


# ---------------------------------------------------------------------------
# Stats / lookup helpers
# ---------------------------------------------------------------------------

def stats() -> Dict[str, int]:
    """Return aggregate counts for the /stats endpoint."""
    if _use_mongo() and models.agent_registry_col is not None:
        total_agents = models.agent_registry_col.count_documents({})
        alive_agents = models.agent_registry_col.count_documents({"alive": True})
        total_clients = models.client_registry_col.count_documents({}) if models.client_registry_col else 0
        return {"total_agents": total_agents, "alive_agents": alive_agents, "total_clients": total_clients}
    # In-memory
    agents = [a for a in models.registry if a != "agent_status"]
    alive = sum(
        1 for a in agents
        if models.registry.get("agent_status", {}).get(a, {}).get("alive")
    )
    clients = [c for c in models.client_registry if c != "agent_map"]
    return {"total_agents": len(agents), "alive_agents": alive, "total_clients": len(clients)}


def lookup(identifier: str) -> Optional[Dict[str, Any]]:
    """Lookup by agent_id or client_name. Returns payload dict or None."""
    # Try agent first
    agent = get_agent(identifier)
    if agent:
        return {"agent_id": agent["agent_id"], "agent_url": agent["agent_url"], "api_url": agent["api_url"]}
    # Try client
    client = get_client(identifier)
    if client:
        aid = client.get("agent_id")
        agent = get_agent(aid) if aid else None
        return {
            "agent_id": aid,
            "agent_url": agent["agent_url"] if agent else None,
            "api_url": client.get("api_url"),
        }
    return None


def get_available_agents(prefix: str = "agentm") -> List[Dict[str, Any]]:
    """Return agents that start with *prefix* and are not assigned to any client."""
    if _use_mongo() and models.agent_registry_col is not None:
        # Get assigned agent ids
        assigned = set()
        if models.client_registry_col is not None:
            for doc in models.client_registry_col.find({}, {"agent_id": 1}):
                if doc.get("agent_id"):
                    assigned.add(doc["agent_id"])
        docs = models.agent_registry_col.find({"agent_id": {"$regex": f"^{prefix}"}})
        return [
            _build_payload(_strip_id(d))
            for d in docs
            if d.get("agent_id") not in assigned
        ]
    # In-memory
    assigned = set(models.client_registry.get("agent_map", {}).values())
    return [
        _build_payload_from_memory(aid)
        for aid in models.registry
        if aid != "agent_status" and aid.startswith(prefix) and aid not in assigned
    ]


# ---------------------------------------------------------------------------
# In-memory payload builder (used only when MongoDB is unavailable)
# ---------------------------------------------------------------------------

def _build_payload_from_memory(agent_id: str) -> Dict[str, Any]:
    """Build an agent payload from the in-memory registry dicts."""
    agent_url = models.registry.get(agent_id)
    status = models.registry.get("agent_status", {}).get(agent_id, {})
    return {
        "agent_id": agent_id,
        "agent_url": agent_url,
        "api_url": status.get("api_url"),
        "alive": status.get("alive", False),
        "assigned_to": status.get("assigned_to"),
        "last_update": status.get("last_update"),
        "capabilities": status.get("capabilities", []),
        "tags": status.get("tags", []),
    }

