"""
Minimal LLM agent service — wraps Anthropic Claude.
Registers itself with NANDA Index on startup.
Runs on port 5001.
"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
import anthropic

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("agent-service")

app = Flask(__name__)
CORS(app)

# --- Configuration ---
AGENT_ID = os.getenv("AGENT_ID", "agentm-claude-1")
AGENT_PORT = int(os.getenv("AGENT_PORT", "5001"))
AGENT_URL = os.getenv("AGENT_URL", f"http://localhost:{AGENT_PORT}")
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:6900")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful AI assistant registered in the NANDA agent registry. "
    "Keep responses concise (2-3 sentences) unless asked for detail.",
)

# Anthropic client — reads ANTHROPIC_API_KEY from env automatically
client = anthropic.Anthropic()


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({"status": "ok", "agent_id": AGENT_ID, "model": CLAUDE_MODEL})


@app.route("/chat", methods=["POST"])
def chat():
    """Accept a prompt, return Claude's response.
    ---
    Expects JSON: {"message": "...", "conversation_id": "optional"}
    Returns JSON: {"response": "...", "agent_id": "...", "model": "..."}
    """
    data = request.json or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Missing 'message' field"}), 400

    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        reply = resp.content[0].text
        logger.info("Prompt: %s | Response: %s", message[:80], reply[:80])
        return jsonify({
            "response": reply,
            "agent_id": AGENT_ID,
            "model": CLAUDE_MODEL,
        })
    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        return jsonify({"error": f"LLM API error: {str(e)}"}), 502


def register_with_registry():
    """Register this agent with NANDA Index on startup."""
    payload = {
        "agent_id": AGENT_ID,
        "agent_url": AGENT_URL,
        "api_url": f"{AGENT_URL}/chat",
    }
    try:
        r = requests.post(f"{REGISTRY_URL}/register", json=payload, timeout=5)
        if r.ok:
            logger.info("Registered '%s' with NANDA Index at %s", AGENT_ID, REGISTRY_URL)
        else:
            logger.warning("Registration failed: %s %s", r.status_code, r.text)
    except requests.ConnectionError:
        logger.warning("NANDA Index not reachable at %s — skipping registration", REGISTRY_URL)


if __name__ == "__main__":
    register_with_registry()
    logger.info("Agent '%s' starting on port %d (model: %s)", AGENT_ID, AGENT_PORT, CLAUDE_MODEL)
    app.run(host="0.0.0.0", port=AGENT_PORT, debug=False)

