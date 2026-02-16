"""Agent CRUD endpoints: register, lookup, list, search, status, delete, mcp_servers, sender."""
import logging
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from app import dal

logger = logging.getLogger(__name__)

agents_bp = Blueprint("agents", __name__)

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


def _paginate(items: list) -> dict:
    """Apply limit/offset pagination from query params and return envelope."""
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        offset = 0
    try:
        limit = min(max(int(request.args.get("limit", DEFAULT_PAGE_LIMIT)), 1), MAX_PAGE_LIMIT)
    except (ValueError, TypeError):
        limit = DEFAULT_PAGE_LIMIT
    total = len(items)
    page = items[offset : offset + limit]
    return {"data": page, "total": total, "offset": offset, "limit": limit}


@agents_bp.route("/search", methods=["GET"])
def search_agents():
    """Search agents.
    ---
    tags:
      - Agents
    parameters:
      - name: q
        in: query
        type: string
        description: Substring to match against agent_id
      - name: capabilities
        in: query
        type: string
        description: Comma-separated capabilities filter
      - name: tags
        in: query
        type: string
        description: Comma-separated tags filter
      - name: offset
        in: query
        type: integer
        default: 0
      - name: limit
        in: query
        type: integer
        default: 50
    responses:
      200:
        description: Paginated list of matching agents
    """
    query = request.args.get("q", "").strip().lower()
    capabilities_filter = request.args.get("capabilities")
    tags_filter = request.args.get("tags")
    capabilities_list = [c.strip() for c in capabilities_filter.split(",")] if capabilities_filter else None
    tags_list = [t.strip() for t in tags_filter.split(",")] if tags_filter else None

    results = dal.search_agents(query=query, capabilities=capabilities_list, tags=tags_list)
    return jsonify(_paginate(results))


@agents_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id):
    """Get agent by ID.
    ---
    tags:
      - Agents
    parameters:
      - name: agent_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Agent details
      404:
        description: Agent not found
    """
    agent = dal.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    return jsonify(agent)


@agents_bp.route("/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    """Delete an agent.
    ---
    tags:
      - Agents
    parameters:
      - name: agent_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Agent deleted
      404:
        description: Agent not found
    """
    if not dal.agent_exists(agent_id):
        return jsonify({"error": "Agent not found"}), 404
    dal.delete_agent(agent_id)
    return jsonify({"status": "deleted", "agent_id": agent_id})


@agents_bp.route("/agents/<agent_id>/status", methods=["PUT"])
def update_agent_status(agent_id):
    """Update agent status fields.
    ---
    tags:
      - Agents
    parameters:
      - name: agent_id
        in: path
        type: string
        required: true
      - name: body
        in: body
        schema:
          type: object
          properties:
            alive:
              type: boolean
            assigned_to:
              type: string
            capabilities:
              type: array
              items:
                type: string
            tags:
              type: array
              items:
                type: string
    responses:
      200:
        description: Agent status updated
      404:
        description: Agent not found
    """
    if not dal.agent_exists(agent_id):
        return jsonify({"error": "Agent not found"}), 404
    data = request.json or {}
    updated = dal.update_agent_status(agent_id, data)
    return jsonify({"status": "updated", "agent": updated})


@agents_bp.route("/mcp_servers", methods=["GET"])
def list_mcp_servers():
    """List MCP servers.
    ---
    tags:
      - MCP
    parameters:
      - name: offset
        in: query
        type: integer
        default: 0
      - name: limit
        in: query
        type: integer
        default: 50
    responses:
      200:
        description: Paginated list of MCP servers
    """
    results = dal.list_mcp_servers()
    return jsonify(_paginate(results))


@agents_bp.route("/register", methods=["POST"])
def register():
    """Register a new agent.
    ---
    tags:
      - Agents
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - agent_id
            - agent_url
          properties:
            agent_id:
              type: string
              example: agentm-chat-1
            agent_url:
              type: string
              example: https://bridge.example.com/agentm-chat-1
            api_url:
              type: string
              example: https://api.example.com/agentm-chat-1
    responses:
      200:
        description: Agent registered successfully
      400:
        description: Missing required fields
    """
    data = request.json
    if not data or "agent_id" not in data or "agent_url" not in data:
        return jsonify({"error": "Missing agent_id or agent_url"}), 400
    dal.register_agent(data["agent_id"], data["agent_url"], data.get("api_url", ""))
    return jsonify({"status": "success", "message": f"Agent {data['agent_id']} registered successfully"})


@agents_bp.route("/lookup/<id>", methods=["GET"])
def lookup(id):
    """Lookup by agent_id or client_name.
    ---
    tags:
      - Agents
    parameters:
      - name: id
        in: path
        type: string
        required: true
        description: Agent ID or client name
    responses:
      200:
        description: Lookup result with agent_url and api_url
      404:
        description: ID not found
    """
    result = dal.lookup(id)
    if result:
        return jsonify(result)
    return jsonify({"error": f"ID '{id}' not found"}), 404


@agents_bp.route("/sender/<agent_id>", methods=["GET"])
def resolve_sender(agent_id):
    """Resolve the client assigned to an agent.
    ---
    tags:
      - Agents
    parameters:
      - name: agent_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Sender name returned
      400:
        description: Unassigned agent
      404:
        description: No client alive for this agent
    """
    assigned_to = dal.get_agent_status_field(agent_id, "assigned_to")
    if assigned_to is None:
        if not dal.agent_exists(agent_id):
            return jsonify({"error": "Unassigned agent"}), 400
        return jsonify({"error": "No client alive for this agent"}), 404
    return jsonify({"sender_name": assigned_to})


@agents_bp.route("/list", methods=["GET"])
def list_agents():
    """List all registered agents.
    ---
    tags:
      - Agents
    parameters:
      - name: offset
        in: query
        type: integer
        default: 0
      - name: limit
        in: query
        type: integer
        default: 50
    responses:
      200:
        description: Paginated list of agents
    """
    items = dal.list_agents()
    return jsonify(_paginate(items))


@agents_bp.route("/status/<agent_id>", methods=["GET"])
def agent_status(agent_id):
    """Get alive status of an agent.
    ---
    tags:
      - Agents
    parameters:
      - name: agent_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Boolean alive status
    """
    alive = dal.get_agent_status_field(agent_id, "alive", False)
    return jsonify(alive)

