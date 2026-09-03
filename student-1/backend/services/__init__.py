"""
Outbound service clients and AI-Mode helpers for student-1-backend.

.env is loaded HERE, at package import, rather than inside an individual
module. database_api.py reads its service URLs at module level, so if the
file were loaded later - say by llm_client.py - those reads would already
have happened against the bare environment and every .env value would be
silently ignored.

That is not theoretical. It shipped: DB_SERVICE_URL fell back to
"localhost", which on Windows resolves IPv6 first and costs about two
seconds per call, and the agentic loop's NFR check failed at 0/20 requests
within 500 ms. Loading the file before any submodule is imported is what
makes .env actually take effect.
"""

from pathlib import Path

from dotenv import load_dotenv

# student-1/.env - one file shared by the three services and the loop.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")
