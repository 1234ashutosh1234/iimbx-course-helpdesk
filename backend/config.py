"""Global application configuration backed by environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSE_DOCS_DIR = PROJECT_ROOT / "course_docs"

# Database Configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "database" / "iimbx.db"))
DATABASE_BUSY_TIMEOUT_MS = int(os.getenv("DATABASE_BUSY_TIMEOUT_MS", "5000"))

# Cache & Idempotency TTL Settings
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "604800"))  # 7 days
IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))  # 24 hours
INFLIGHT_LEASE_SECONDS = int(os.getenv("INFLIGHT_LEASE_SECONDS", "45"))  # 45 seconds lease

# Gemini Client & Inference Hyperparameters
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "400"))
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30.0"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))

# Prompt and Schema Versioning for Cache Key Derivation
PROMPT_VERSION = "v1.0"
SCHEMA_VERSION = "v1.0"
