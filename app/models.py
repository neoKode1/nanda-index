"""Shared state: in-memory registries and MongoDB collection references."""
import logging
from app.config import TEST_MODE, MONGO_URI, MONGO_DBNAME

logger = logging.getLogger(__name__)

if not TEST_MODE:
    from pymongo import MongoClient

# ---- MongoDB state ----
USE_MONGO = False
agent_registry_col = None
client_registry_col = None
users_col = None
mcp_registry_col = None
messages_col = None

# ---- In-memory registries ----
registry: dict = {"agent_status": {}}
client_registry: dict = {"agent_map": {}}


def init_db():
    """Initialize MongoDB connection and load data into in-memory registries."""
    global USE_MONGO, agent_registry_col, client_registry_col
    global users_col, mcp_registry_col, messages_col
    global registry, client_registry

    if TEST_MODE:
        logger.info("TEST_MODE enabled – using in-memory registries (no MongoDB).")
        return

    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command("ping")
        mongo_db = mongo_client[MONGO_DBNAME]
        agent_registry_col = mongo_db.get_collection("agent_registry")
        client_registry_col = mongo_db.get_collection("client_registry")
        users_col = mongo_db.get_collection("users")
        mcp_registry_col = mongo_db.get_collection("mcp_registry")
        messages_col = mongo_db.get_collection("messages")
        USE_MONGO = True
        logger.info("Connected to MongoDB successfully – using MongoDB for persistence.")
    except Exception as e:
        USE_MONGO = False
        logger.warning("MongoDB unavailable (%s); continuing in in-memory mode.", e)
        return

    # Load agent registry from MongoDB
    try:
        for doc in agent_registry_col.find():
            agent_id = doc.get("agent_id")
            if not agent_id:
                continue
            registry[agent_id] = doc.get("agent_url")
            registry["agent_status"][agent_id] = {
                "alive": doc.get("alive", False),
                "assigned_to": doc.get("assigned_to"),
                "last_update": doc.get("last_update"),
                "api_url": doc.get("api_url"),
            }
        logger.info("Loaded %d agents from MongoDB", len(registry) - 1)
    except Exception as e:
        logger.error("Error loading agent registry from MongoDB: %s", e)
        registry = {"agent_status": {}}

    # Load client registry from MongoDB
    try:
        for doc in client_registry_col.find():
            client_name = doc.get("client_name")
            if not client_name:
                continue
            client_registry[client_name] = doc.get("api_url")
            client_registry["agent_map"][client_name] = doc.get("agent_id")
        logger.info("Loaded %d clients from MongoDB", len(client_registry) - 1)
    except Exception as e:
        logger.error("Error loading client registry from MongoDB: %s", e)
        client_registry = {"agent_map": {}}

