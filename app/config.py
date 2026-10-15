"""Central settings, read from environment variables / .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

PROVIDER_TIMEOUT_SECONDS: float = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "10"))
# Simulated demo providers. Turn off (false) once real sources carry the demo.
ENABLE_MOCK_PROVIDERS: bool = os.getenv("ENABLE_MOCK_PROVIDERS", "true").lower() == "true"
MANUAL_QUOTES_FILE: Path = Path(os.getenv("MANUAL_QUOTES_FILE", BASE_DIR / "data" / "manual_quotes.json"))
SEARATES_API_KEY: str | None = os.getenv("SEARATES_API_KEY") or None
