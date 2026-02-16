"""
Minimal client — discovers its agent via NANDA Index, then chats.
Demonstrates the full registry → lookup → agent call flow.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import requests

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:6900")
CLIENT_NAME = os.getenv("CLIENT_NAME", "demo-user")


def discover_agent() -> dict:
    """Look up our assigned agent through NANDA Index."""
    r = requests.get(f"{REGISTRY_URL}/lookup/{CLIENT_NAME}", timeout=5)
    if r.ok:
        return r.json()

    # Not allocated yet — list available agents
    print(f"[client] No allocation found for '{CLIENT_NAME}', checking available agents...")
    r = requests.get(f"{REGISTRY_URL}/list", timeout=5)
    if not r.ok:
        print("[client] Registry unreachable.")
        sys.exit(1)

    agents = r.json().get("data", [])
    if not agents:
        print("[client] No agents registered.")
        sys.exit(1)

    # Pick the first agent and allocate
    agent = agents[0]
    agent_id = agent["agent_id"]
    print(f"[client] Found agent '{agent_id}', allocating...")
    alloc = requests.post(
        f"{REGISTRY_URL}/api/allocate",
        json={
            "client_id": CLIENT_NAME,
            "userProfile": {"name": CLIENT_NAME},
        },
        timeout=5,
    )
    if not alloc.ok:
        print(f"[client] Allocation failed: {alloc.text}")
        sys.exit(1)

    result = alloc.json()
    print(f"[client] Allocated: {result.get('message')}")
    return {
        "agent_url": result.get("agent_url"),
        "api_url": result.get("api_url"),
    }


def chat(api_url: str, message: str) -> str:
    """Send a message to the agent and return the response."""
    r = requests.post(api_url, json={"message": message}, timeout=30)
    if not r.ok:
        return f"[error] Agent returned {r.status_code}: {r.text}"
    return r.json().get("response", "[no response]")


def main():
    print(f"[client] Discovering agent via NANDA Index ({REGISTRY_URL})...")
    agent_info = discover_agent()
    api_url = agent_info.get("api_url")
    agent_url = agent_info.get("agent_url")

    if not api_url:
        print("[client] No api_url found — using agent_url/chat")
        api_url = f"{agent_url}/chat"

    print(f"[client] Connected to agent at {api_url}")
    print(f"[client] Type 'quit' to exit.\n")

    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[client] Goodbye.")
            break
        if not prompt or prompt.lower() in ("quit", "exit", "q"):
            print("[client] Goodbye.")
            break
        response = chat(api_url, prompt)
        print(f"Agent: {response}\n")


if __name__ == "__main__":
    main()

