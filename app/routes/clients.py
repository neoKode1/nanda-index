"""Client endpoints: /clients, /api/allocate."""
import logging
import random

from flask import Blueprint, jsonify, request

from app import dal

logger = logging.getLogger(__name__)

clients_bp = Blueprint("clients", __name__)


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


@clients_bp.route("/clients", methods=["GET"])
def list_clients():
    """List all clients.
    ---
    tags:
      - Clients
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
        description: Paginated list of clients
    """
    items = dal.list_clients()
    return jsonify(_paginate(items))


@clients_bp.route("/api/allocate", methods=["POST"])
def allocate_agent():
    """Allocate an available agent to a client.
    ---
    tags:
      - Clients
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - client_id
            - userProfile
          properties:
            client_id:
              type: string
            userProfile:
              type: object
              properties:
                name:
                  type: string
                  example: Jane Doe
    responses:
      200:
        description: Agent allocated (or already allocated) to client
      400:
        description: Missing client_name
      503:
        description: No available agents
    """
    data = request.json
    if not data or "client_id" not in data:
        return jsonify({"error": "Missing client_name"}), 400

    str_name = data["userProfile"]["name"]
    client_name = str_name.replace(" ", "").lower()
    logger.debug("Client Name: %s", client_name)

    # Check if this client already has an agent
    existing = dal.get_client(client_name)
    if existing:
        agent_id = existing.get("agent_id")
        api_url = existing.get("api_url")
        agent = dal.get_agent(agent_id) if agent_id else None
        agent_url = agent["agent_url"] if agent else None
        return jsonify({
            "status": "allocated",
            "message": f"Client {client_name} is already allocated.. try a different name",
            "agent_url": agent_url,
            "api_url": api_url,
        })

    # Find available agents
    available = dal.get_available_agents(prefix="agentm")
    if not available:
        return jsonify({"error": "No available agents at this time"}), 503

    selected = random.choice(available)
    selected_agent_id = selected["agent_id"]
    selected_agent_url = selected["agent_url"]
    api_url = selected.get("api_url")

    logger.debug("Selected Agent URL (bridge): %s", selected_agent_url)
    logger.debug("API URL for client: %s", api_url)

    # Allocate client → agent
    dal.allocate_client(client_name, selected_agent_id, api_url)

    logger.debug("Selected Agent ID: %s", selected_agent_id)

    # Mark agent as alive and assigned
    dal.update_agent_status(selected_agent_id, {
        "alive": True,
        "assigned_to": client_name,
    })

    return jsonify({
        "status": "success",
        "agent_url": selected_agent_url,
        "api_url": api_url,
        "message": f"Agent {selected_agent_id} assigned to {client_name}",
    })

