"""Health and statistics endpoints."""
from flask import Blueprint, jsonify
from app.config import TEST_MODE
from app import models, dal

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Health check.
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
            mongo:
              type: boolean
              example: false
    """
    return jsonify({"status": "ok", "mongo": models.USE_MONGO and not TEST_MODE})


@health_bp.route("/stats", methods=["GET"])
def stats():
    """Registry statistics.
    ---
    tags:
      - Health
    responses:
      200:
        description: Aggregate counts
        schema:
          type: object
          properties:
            total_agents:
              type: integer
              example: 5
            alive_agents:
              type: integer
              example: 2
            total_clients:
              type: integer
              example: 3
    """
    return jsonify(dal.stats())

