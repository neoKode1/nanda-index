"""Configuration constants loaded from environment variables."""
import os

TEST_MODE = os.getenv("TEST_MODE") == "1"
DEFAULT_PORT = 6900
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGODB_DB", "iot_agents_db")
ENABLE_FEDERATION = os.getenv("ENABLE_FEDERATION", "false").lower() == "true"
DEFAULT_OASF_SCHEMA_DIR = os.environ.get(
    "OASF_SCHEMA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agntcy", "oasf", "schema"),
)

