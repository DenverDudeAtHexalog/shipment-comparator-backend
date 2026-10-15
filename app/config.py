"""Central settings, read from environment variables / .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

PROVIDER_TIMEOUT_SECONDS: float = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "10"))
# Simulated demo providers. Turn off (false) once real sources carry the demo.
ENABLE_MOCK_PROVIDERS: bool = os.getenv("ENABLE_MOCK_PROVIDERS", "true").lower() == "true"
# Always-failing demo vendor, to show that one broken provider never breaks the response.
ENABLE_OUTAGE_DEMO: bool = os.getenv("ENABLE_OUTAGE_DEMO", "false").lower() == "true"
MANUAL_QUOTES_FILE: Path = Path(os.getenv("MANUAL_QUOTES_FILE", BASE_DIR / "data" / "manual_quotes.json"))
SEARATES_API_KEY: str | None = os.getenv("SEARATES_API_KEY") or None
# Debug only: include vendors that could not serve the request (no_quote/error/...) in API responses.
SHOW_UNAVAILABLE: bool = os.getenv("SHOW_UNAVAILABLE", "false").lower() == "true"
