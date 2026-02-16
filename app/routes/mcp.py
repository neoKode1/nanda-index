"""MCP registry endpoint: /get_mcp_registry."""
import logging

from flask import Blueprint, jsonify, request

from app.config import TEST_MODE
from app import models

logger = logging.getLogger(__name__)

mcp_bp = Blueprint("mcp", __name__)


@mcp_bp.route("/get_mcp_registry", methods=["GET"])
def get_mcp_server_details():
    """Get MCP server details by provider and qualified name.
    ---
    tags:
      - MCP
    parameters:
      - name: registry_provider
        in: query
        type: string
        required: true
        description: Registry provider (e.g. smithery, composio)
      - name: qualified_name
        in: query
        type: string
        required: true
        description: Fully qualified server name
    responses:
      200:
        description: MCP server document
      400:
        description: Missing required query parameters
      404:
        description: MCP server not found
      500:
        description: Internal error
    """
    registry_provider = request.args.get("registry_provider")
    qualified_name = request.args.get("qualified_name")

    if not registry_provider or not qualified_name:
        return jsonify({
            "error": "Missing required query parameters: registry_provider and qualified_name"
        }), 400

    try:
        mcp_doc = None
        if models.USE_MONGO and not TEST_MODE and models.mcp_registry_col is not None:
            mcp_doc = models.mcp_registry_col.find_one({
                "registry_provider": registry_provider,
                "qualified_name": qualified_name,
            })

        if not mcp_doc:
            return jsonify({
                "error": f"MCP server not found for registry_provider: {registry_provider}, qualified_name: {qualified_name}"
            }), 404

        if "_id" in mcp_doc:
            del mcp_doc["_id"]
        return jsonify(mcp_doc)

    except Exception as e:
        logger.error("Error retrieving MCP server details: %s", e)
        return jsonify({"error": f"Error retrieving MCP server details: {str(e)}"}), 500

