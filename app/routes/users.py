"""User management endpoints: /api/check-user, /api/signup, /api/setup."""
import logging
import random

from flask import Blueprint, jsonify, request

from app.config import TEST_MODE
from app import models, dal

logger = logging.getLogger(__name__)

users_bp = Blueprint("users", __name__)


@users_bp.route("/api/check-user", methods=["POST"])
def check_user():
    """Check if a user exists by email.
    ---
    tags:
      - Users
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - email
          properties:
            email:
              type: string
              example: user@example.com
    responses:
      200:
        description: User existence check result
      400:
        description: Missing email
      500:
        description: MongoDB not available
    """
    data = request.json
    email = data.get("email")
    if not email:
        return jsonify({"error": "Missing email"}), 400

    if models.USE_MONGO and not TEST_MODE and models.users_col is not None:
        user = models.users_col.find_one({"email": email})
        if user:
            return jsonify({"exists": True, "user": {"email": user["email"], "username": user.get("username")}})
        return jsonify({"exists": False})
    return jsonify({"error": "MongoDB not available"}), 500


@users_bp.route("/api/signup", methods=["POST"])
def signup():
    """Sign up a new user and allocate an agent.
    ---
    tags:
      - Users
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - email
            - username
          properties:
            email:
              type: string
              example: user@example.com
            username:
              type: string
              example: janedoe
    responses:
      200:
        description: User created and agent allocated
      400:
        description: Missing fields or user already exists
      500:
        description: MongoDB not available
      503:
        description: No available agents
    """
    data = request.json
    email = data.get("email")
    username = data.get("username")

    if not email or not username:
        return jsonify({"status": "error", "message": "Missing email or username"}), 400

    if not models.USE_MONGO or TEST_MODE:
        return jsonify({"status": "error", "message": "MongoDB not available"}), 500

    if models.USE_MONGO and not TEST_MODE and models.users_col is not None:
        user = models.users_col.find_one({"email": email})
    else:
        user = None
    if user:
        return jsonify({"status": "error", "message": "User already exists"}), 400

    # Find an available agent
    available = dal.get_available_agents(prefix="agentm")
    if not available:
        return jsonify({"status": "error", "message": "No available agents"}), 503
    selected = random.choice(available)
    selected_agent_id = selected["agent_id"]
    agent_url = selected["agent_url"]
    api_url = selected.get("api_url")

    user_doc = {
        "email": email,
        "username": username,
        "agent_id": selected_agent_id,
        "agent_url": agent_url,
        "api_url": api_url,
    }
    if models.USE_MONGO and not TEST_MODE and models.users_col is not None:
        models.users_col.insert_one(user_doc)
    user_doc.pop("_id", None)

    # Allocate client and update agent status via DAL
    dal.allocate_client(username, selected_agent_id, api_url)
    dal.update_agent_status(selected_agent_id, {"alive": True, "assigned_to": username})

    return jsonify({"status": "success", "user": user_doc, "agent_url": agent_url, "api_url": api_url})




@users_bp.route("/api/setup", methods=["POST"])
def setup():
    """Setup a user with a specific agent.
    ---
    tags:
      - Users
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - email
            - username
            - agent_id
          properties:
            email:
              type: string
              example: user@example.com
            username:
              type: string
              example: janedoe
            agent_id:
              type: string
              example: agentm-chat-1
    responses:
      200:
        description: User created and agent assigned
      400:
        description: Missing fields, agent not found, or agent already assigned
      500:
        description: MongoDB not available
    """
    data = request.json
    email = data.get("email")
    user_selected_agent_id = data.get("agent_id")
    username = data.get("username")

    if not email or not username or not user_selected_agent_id:
        return jsonify({"status": "error", "message": "Missing email or username or agent_id"}), 400

    if not dal.agent_exists(user_selected_agent_id):
        return jsonify({"status": "error", "message": "Agent not found"}), 400

    # Check if agent is already assigned
    available = dal.get_available_agents(prefix="")
    available_ids = {a["agent_id"] for a in available}
    if user_selected_agent_id not in available_ids:
        return jsonify({"status": "error", "message": "Agent already assigned to a user"}), 400

    if not models.USE_MONGO or TEST_MODE:
        return jsonify({"status": "error", "message": "MongoDB not available"}), 500

    if models.USE_MONGO and not TEST_MODE and models.users_col is not None:
        user = models.users_col.find_one({"email": email})
    else:
        user = None
    if user:
        return jsonify({"status": "error", "message": "User already exists"}), 400

    agent = dal.get_agent(user_selected_agent_id)
    agent_url = agent["agent_url"] if agent else None
    api_url = agent.get("api_url") if agent else None

    user_doc = {
        "email": email,
        "username": username,
        "agent_id": user_selected_agent_id,
        "agent_url": agent_url,
        "api_url": api_url,
    }
    if models.USE_MONGO and not TEST_MODE and models.users_col is not None:
        models.users_col.insert_one(user_doc)
    user_doc.pop("_id", None)

    # Allocate client and update agent status via DAL
    dal.allocate_client(username, user_selected_agent_id, api_url)
    dal.update_agent_status(user_selected_agent_id, {"alive": True, "assigned_to": username})

    return jsonify({"status": "success", "user": user_doc, "agent_url": agent_url, "api_url": api_url})
