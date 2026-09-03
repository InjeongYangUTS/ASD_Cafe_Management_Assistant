"""
Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
Outbound service clients used by the backend/API microservice.

Every cross-feature dependency is reached over HTTP only:

    DatabaseClient  -> student-1-database  (my own SQLite, via its /db API)
    OrderClient     -> the Order service   (order history a review attaches to)
    MenuClient      -> the Order service   (menu names, read through /api/menu)

No client here opens another team member's SQLite file, which is the
Cross-Feature Database API Integration rule for Release 0. Each client
degrades gracefully so the Feedback service stays usable while a peer
service is down, and always reports which source the data came from.

The language model client lives separately in services/llm_client.py,
because AI-Mode is configured differently from the plain HTTP peers
(OpenAI SDK, Ollama /v1 endpoint, much longer timeouts).

NOTE ON SERVICE NAMING
    The approved Project Group Registration Form numbers this feature as
    Student 1 and Order & Kitchen Management as Student 2. The order
    service currently lives in the repository under student-4/ and runs
    as the container student-4-backend on port 8400, so that is the
    default here. It is read from ORDER_SERVICE_URL, so when the team
    settles on one numbering the value changes in docker-compose.yml
    alone - no code edit.
"""


import json
import os
import time

import requests

# The backend package root (student-1/backend), one level above this
# services/ package. menu_terms.json sits there.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_SERVICE_URL = os.environ.get("DB_SERVICE_URL", "http://localhost:7100")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://localhost:8400")

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", 4))

# Health probes of OPTIONAL services must stay well inside the Docker
# healthcheck timeout, so they get their own much shorter budget.
PROBE_TIMEOUT = float(os.environ.get("PROBE_TIMEOUT", 1.5))

# Calls to a PEER service (orders, menu) get a shorter budget than calls to
# my own database. A peer being down must not slow my pages down: a review
# renders perfectly well without the menu name attached to it.
PEER_TIMEOUT = float(os.environ.get("PEER_TIMEOUT", 2))

# How long a failed peer lookup is remembered before we try again.
#
# Without this, every request re-probed a service that was known to be
# down, and GET /api/summary took over ten seconds - it failed the agentic
# loop's endpoint check. Re-testing a dead peer on every single page load
# buys nothing; once a minute is plenty to notice it came back.
PEER_RETRY_SECONDS = float(os.environ.get("PEER_RETRY_SECONDS", 60))


class PeerCircuit:
    """
    Remembers that a peer service was unreachable, so we stop paying the
    timeout on every request until it is worth retrying.

    Deliberately tiny and per-process: this is a latency guard, not a
    resilience framework. It never hides a working peer for long, and a
    successful call clears it immediately.
    """

    def __init__(self, retry_after=PEER_RETRY_SECONDS):
        self.retry_after = retry_after
        self._failed_at = None

    def is_open(self):
        """True while we are still skipping calls to this peer."""
        if self._failed_at is None:
            return False

        if time.monotonic() - self._failed_at >= self.retry_after:
            self._failed_at = None
            return False

        return True

    def record_failure(self):
        self._failed_at = time.monotonic()

    def record_success(self):
        self._failed_at = None


class ServiceError(Exception):
    """Raised when a downstream service answers with an error we must surface."""

    def __init__(self, message, status_code=502, detail=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


# =====================================================================
# My own database microservice
# =====================================================================

class DatabaseClient:
    """Thin HTTP wrapper over student-1-database. The only way into feedback.db."""

    def __init__(self, base_url=DB_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    def _request(self, method, path, **kwargs):
        url = self.base_url + path
        try:
            response = requests.request(method, url, timeout=HTTP_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise ServiceError(
                "feedback database service is unavailable", 503, str(exc)
            )

        if response.status_code >= 400:
            try:
                detail = response.json().get("error")
            except ValueError:
                detail = response.text[:200]
            raise ServiceError(
                detail or "database request failed", response.status_code
            )

        if response.status_code == 204 or not response.content:
            return {}

        return response.json()

    # -- customer_feedback -------------------------------------------
    def list_feedback(self, **params):
        clean = {key: value for key, value in params.items()
                 if value not in (None, "")}
        return self._request("GET", "/db/feedback", params=clean)

    def create_feedback(self, payload):
        return self._request("POST", "/db/feedback", json=payload)

    def get_feedback(self, feedback_id):
        return self._request("GET", "/db/feedback/%d" % feedback_id)

    def update_feedback(self, feedback_id, payload):
        return self._request("PUT", "/db/feedback/%d" % feedback_id, json=payload)

    def delete_feedback(self, feedback_id, payload=None):
        return self._request(
            "DELETE", "/db/feedback/%d" % feedback_id, json=payload or {}
        )

    def save_analysis(self, feedback_id, payload):
        return self._request(
            "PUT", "/db/feedback/%d/analysis" % feedback_id, json=payload
        )

    # -- store_logs ---------------------------------------------------
    def feedback_logs(self, feedback_id):
        return self._request("GET", "/db/feedback/%d/logs" % feedback_id)

    def list_logs(self, **params):
        clean = {key: value for key, value in params.items()
                 if value not in (None, "")}
        return self._request("GET", "/db/logs", params=clean)

    # -- service ------------------------------------------------------
    def stats(self):
        return self._request("GET", "/db/stats")

    def health(self):
        return self._request("GET", "/db/health")


# =====================================================================
# Order service - orders a review can be written about
# =====================================================================

class OrderClient:
    """
    Reads order lines from the Order service, so a review that names no
    menu item can still be attributed to what the customer bought.

    It used to do more: a customer could pick the visit their review was
    about. That was dropped because nothing verifies the link yet, and an
    order number shown next to a review reads as verified whether or not
    it is. The columns remain for Release 1.

    The Order service may not be running (a teammate's container, or
    mid-deploy), so every method degrades to empty rather than failing -
    the per-item breakdown is then absent instead of wrong.

    We never read the Order service's SQLite file. Only its HTTP API.
    """

    def __init__(self, base_url=ORDER_SERVICE_URL):
        self.base_url = base_url.rstrip("/")
        self.circuit = PeerCircuit()

    def _orders(self, params):
        response = requests.get(
            self.base_url + "/api/orders", params=params, timeout=PEER_TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            for key in ("orders", "data", "items", "results"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return []

        return payload if isinstance(payload, list) else []

    def items_by_order(self, order_ids):
        """
        Return {order_id: [menu name, ...]} for the given orders.

        Used to attribute a review to a menu item when the customer did
        not name one in the text - if they only ordered a Flat White,
        "my coffee was cold" is about the Flat White.

        One list call, not one request per order: the whole point of
        going over HTTP is that the calls are not free.
        """
        wanted = {int(order_id) for order_id in order_ids if order_id}
        if not wanted or self.circuit.is_open():
            return {}

        try:
            orders = self._orders({"limit": 200, "include": "items"})
            self.circuit.record_success()
        except (requests.RequestException, ValueError):
            self.circuit.record_failure()
            return {}

        mapping = {}
        for order in orders:
            if not isinstance(order, dict) or order.get("id") not in wanted:
                continue

            mapping[int(order["id"])] = [
                item.get("menu_name")
                for item in (order.get("items") or [])
                if item.get("menu_name")
            ]

        return mapping

    def health(self):
        try:
            response = requests.get(
                self.base_url + "/api/orders", params={"limit": 1}, timeout=PROBE_TIMEOUT
            )
            return {"reachable": response.ok, "url": self.base_url}
        except requests.RequestException:
            return {"reachable": False, "url": self.base_url}


# =====================================================================
# Menu vocabulary - which menu item a review is talking about
# =====================================================================

class MenuClient:
    """
    Supplies the menu names used to attribute complaints and praise to
    individual menu items.

    Menu data is owned by the Menu feature, so we read it through the
    Order service's /api/menu endpoint rather than touching anyone's
    database. menu_terms.json is a local fallback cache with the customer
    wording ("avo toast", "hot choc") that a bare menu name does not
    carry, and callers can always tell which source was used through
    'menu_source'.
    """

    def __init__(self, base_url=ORDER_SERVICE_URL, catalog_path=None):
        self.base_url = base_url.rstrip("/")
        self.catalog_path = catalog_path or os.path.join(
            BASE_DIR, "menu_terms.json"
        )
        self._fallback = self._load_fallback()
        self.circuit = PeerCircuit()

        # Menu names change rarely; a review analysis does not need a fresh
        # copy per request. Caching turns an N-request page into one lookup.
        self._cache = None
        self._cached_at = 0.0
        self.cache_seconds = float(os.environ.get("MENU_CACHE_SECONDS", 120))

    def _load_fallback(self):
        with open(self.catalog_path, "r", encoding="utf-8") as handle:
            catalog = json.load(handle)

        items = {}
        for item in catalog["items"]:
            name = item["name"]
            aliases = [alias.lower() for alias in item.get("aliases", [])]
            if name.lower() not in aliases:
                aliases.append(name.lower())

            items[name] = {
                "menu_id": item.get("menu_id"),
                "name": name,
                "category": item.get("category", "GENERAL"),
                "aliases": aliases,
            }
        return items

    def get_vocabulary(self):
        """
        Return ({menu name: entry}, source).

        Live names from the Menu API are merged over the fallback so any
        item the team has added since this file was written is still
        recognised - it just matches on its own name rather than on a
        hand-written alias.
        """
        if self._cache is not None and                 time.monotonic() - self._cached_at < self.cache_seconds:
            return self._cache

        vocabulary = {name: dict(entry)
                      for name, entry in self._fallback.items()}

        if self.circuit.is_open():
            return self._remember((vocabulary, "fallback"))

        try:
            response = requests.get(
                self.base_url + "/api/menu", timeout=PEER_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
            self.circuit.record_success()
        except (requests.RequestException, ValueError):
            self.circuit.record_failure()
            return self._remember((vocabulary, "fallback"))

        live = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(live, list) or not live:
            return self._remember((vocabulary, "fallback"))

        for item in live:
            if not isinstance(item, dict):
                continue

            name = item.get("name") or item.get("menu_name")
            if not name:
                continue

            existing = vocabulary.get(name)
            if existing:
                existing["menu_id"] = item.get("menu_id", existing["menu_id"])
            else:
                vocabulary[name] = {
                    "menu_id": item.get("menu_id"),
                    "name": name,
                    "category": "GENERAL",
                    "aliases": [name.lower()],
                }

        return self._remember((vocabulary, "menu-service"))

    def _remember(self, result):
        self._cache = result
        self._cached_at = time.monotonic()
        return result

    def health(self):
        try:
            response = requests.get(self.base_url + "/api/menu", timeout=PROBE_TIMEOUT)
            return {"reachable": response.ok, "url": self.base_url}
        except requests.RequestException:
            return {"reachable": False, "url": self.base_url}
