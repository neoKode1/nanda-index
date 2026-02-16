# Local Development Guide (Registry & Interop)

Relocated from `nanda-index/LOCAL_DEVELOPMENT.md` to group local setup with interoperability tooling.

---

## Registry Quick Start (No SSL)
```bash
cd nanda-index
python3 -m venv .venv && source .venv/bin/activate
pip install flask flask-cors pymongo requests httpx pytest jsonschema PyJWT python-dotenv Flask-Limiter
export PORT=6900
python registry.py
```

The registry starts in **in-memory mode** by default — no MongoDB required.
MongoDB is only used when `MONGODB_URI` is set and reachable.

## Running Tests
```bash
TEST_MODE=1 python -m pytest agntcy-interop/tests/test_registry.py \
  agntcy-interop/tests/test_registry_new_endpoints.py \
  switchboard/tests/test_integration.py -v
```

`TEST_MODE=1` enables in-memory storage and disables auth/rate-limiting so tests run fast with no external dependencies.

## Smoke Test Endpoints
```bash
curl -X POST http://localhost:6900/register \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"agentm-local-1","agent_url":"https://bridge.local/agentm-local-1","api_url":"https://api.local/agentm-local-1"}'

curl http://localhost:6900/lookup/agentm-local-1
curl http://localhost:6900/list
curl http://localhost:6900/health
curl http://localhost:6900/stats
curl http://localhost:6900/search?q=local
```

All endpoints are also available under `/api/v1/` (e.g. `/api/v1/list`).

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `6900` | Server port |
| `MONGODB_URI` | *(none)* | MongoDB connection string. Omit to run in-memory. |
| `TEST_MODE` | `0` | `1` = in-memory storage, auth disabled, rate-limiting disabled |
| `AUTH_DISABLED` | `0` | `1` = skip JWT/API-key auth (useful for local dev) |
| `JWT_SECRET` | `dev-secret-change-me` | Secret key for signing JWT tokens |
| `RATE_LIMIT_DEFAULT` | `200/minute` | Default rate limit per client |
| `ENABLE_FEDERATION` | `0` | `1` = enable Switchboard cross-registry routes |

## Project Structure (Post–Phase 0 Hardening)

```
nanda-index/
├── registry.py                 # Thin entry point → delegates to app/
├── app/
│   ├── __init__.py             # Flask application factory (create_app)
│   ├── config.py               # Env-based configuration
│   ├── models.py               # Shared state: in-memory dicts + MongoDB refs
│   ├── dal.py                  # Data Access Layer (MongoDB-first, in-memory fallback)
│   ├── auth.py                 # JWT + API-key auth, @require_auth decorator
│   ├── middleware.py            # Request/response logging
│   ├── persistence.py           # [DEPRECATED] Legacy save helpers — replaced by DAL
│   └── routes/
│       ├── __init__.py          # Blueprint registration + /api/v1/ versioning
│       ├── agents.py            # Agent CRUD: register, lookup, list, search, delete
│       ├── clients.py           # Client allocation and listing
│       ├── health.py            # /health + /stats
│       ├── mcp.py               # MCP-related routes
│       ├── skills.py            # /skills/map endpoint
│       └── users.py             # /api/check-user, /api/signup, /api/setup
├── switchboard/                 # Cross-registry federation
└── agntcy-interop/              # Batch import/export tooling
```

## Interoperability Scripts
- Export: `agntcy-interop/export_nanda_to_agntcy.py`
- Sync (import): `agntcy-interop/sync_agntcy_dir.py`

Use `--dry-run` for safe previews. Wrapper scripts at root provide backward compatibility.

## Tips
- Disable SSL verification only for development.
- Keep agent IDs consistent (`agentm-*`).
- Register several agents before allocation tests.
- Use `AUTH_DISABLED=1` for local dev to skip token requirements.

---

## Developer Decision Log

### Docker — Deferred (2026-02-16)

**Decision:** Skip Docker/docker-compose for local development. Revisit when deploying to a cloud host.

**Rationale:**
- Docker Desktop on macOS runs a full Linux VM (~2-4 GB RAM idle) plus MongoDB image (~700 MB). Too heavy for a dev/testing machine that doesn't need it.
- The registry already runs natively with `python registry.py` — no containers needed.
- The Data Access Layer (`app/dal.py`) falls back to in-memory storage automatically when MongoDB is unavailable. This means the full API works without Docker or Mongo installed.
- All 16 tests pass in `TEST_MODE=1` with zero infrastructure dependencies.

**When to revisit:**
- When deploying to a cloud host (AWS, Railway, Fly.io, etc.) — write a Dockerfile targeting that environment.
- When onboarding other developers who need a reproducible one-command setup.
- When MongoDB persistence needs to be tested locally (a managed cloud Mongo like Atlas free tier is lighter than running Docker locally).

---
Maintained with interoperability documentation.