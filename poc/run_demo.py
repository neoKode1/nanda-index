"""
End-to-end demo orchestrator.
Starts the registry + agent service, registers, allocates, and runs a test conversation.
Usage: ANTHROPIC_API_KEY=sk-... python poc/run_demo.py
"""
import os
import sys
import time
import subprocess
import signal
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import requests

REGISTRY_URL = "http://localhost:6900"
AGENT_URL = "http://localhost:5001"
AGENT_ID = "agentm-claude-1"
CLIENT_NAME = "demo-user"

processes = []


def start_process(cmd, name, env=None):
    """Start a subprocess and track it."""
    full_env = {**os.environ, **(env or {})}
    p = subprocess.Popen(cmd, env=full_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    processes.append((name, p))
    print(f"[demo] Started {name} (PID {p.pid})")
    return p


def cleanup(*_):
    """Kill all subprocesses."""
    for name, p in processes:
        try:
            p.terminate()
            p.wait(timeout=3)
            print(f"[demo] Stopped {name}")
        except Exception:
            p.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def wait_for(url, label, timeout=10):
    """Wait for a service to be healthy."""
    for i in range(timeout):
        try:
            r = requests.get(url, timeout=2)
            if r.ok:
                print(f"[demo] {label} is up")
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    print(f"[demo] TIMEOUT waiting for {label}")
    return False


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("[demo] ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(project_root, ".venv", "bin", "python")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    # 1. Start NANDA Index registry
    print("\n=== Step 1: Start NANDA Index registry ===")
    start_process(
        [venv_python, "registry.py"],
        "NANDA Index (port 6900)",
        env={"TEST_MODE": "1"},
    )
    if not wait_for(f"{REGISTRY_URL}/health", "Registry"):
        cleanup()

    # 2. Start agent service (auto-registers with registry)
    print("\n=== Step 2: Start agent service ===")
    start_process(
        [venv_python, "poc/agent_service.py"],
        f"Agent '{AGENT_ID}' (port 5001)",
    )
    if not wait_for(f"{AGENT_URL}/health", "Agent service"):
        cleanup()

    # 3. Verify registration
    print("\n=== Step 3: Verify agent registered ===")
    r = requests.get(f"{REGISTRY_URL}/lookup/{AGENT_ID}", timeout=5)
    print(f"  Lookup '{AGENT_ID}': {r.json()}")

    r = requests.get(f"{REGISTRY_URL}/stats", timeout=5)
    print(f"  Registry stats: {r.json()}")

    # 4. Allocate agent to client
    print("\n=== Step 4: Allocate agent to client ===")
    r = requests.post(f"{REGISTRY_URL}/api/allocate", json={
        "client_id": CLIENT_NAME,
        "userProfile": {"name": CLIENT_NAME},
    }, timeout=5)
    alloc = r.json()
    print(f"  Allocation: {alloc}")
    api_url = alloc.get("api_url")

    # 5. Send test messages through the pipeline
    print("\n=== Step 5: End-to-end conversation ===")
    test_messages = [
        "Hello! What are you?",
        "What is the NANDA Index?",
        "Thanks, goodbye!",
    ]
    for msg in test_messages:
        print(f"\n  You: {msg}")
        r = requests.post(api_url, json={"message": msg}, timeout=30)
        if r.ok:
            print(f"  Agent: {r.json()['response']}")
        else:
            print(f"  ERROR: {r.status_code} {r.text}")

    print("\n=== Demo complete! ===")
    print(f"  Registry: {REGISTRY_URL}/apidocs/")
    print(f"  Agent:    {AGENT_URL}/health")
    print(f"\nPress Ctrl+C to stop all services, or run the interactive client:")
    print(f"  python poc/client.py")

    # Keep running until Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()

