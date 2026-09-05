import json
import os
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_SERVICE_URL = os.environ.get("DB_SERVICE_URL", "http://localhost:7100")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://localhost:8400")

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", 4))

PROBE_TIMEOUT = float(os.environ.get("PROBE_TIMEOUT", 1.5))

PEER_TIMEOUT = float(os.environ.get("PEER_TIMEOUT", 2))

PEER_RETRY_SECONDS = float(os.environ.get("PEER_RETRY_SECONDS", 60))


class PeerCircuit:
    """Skips a peer service for PEER_RETRY_SECONDS after it fails. Per-process."""

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

    def feedback_logs(self, feedback_id):
        return self._request("GET", "/db/feedback/%d/logs" % feedback_id)

    def list_logs(self, **params):
        clean = {key: value for key, value in params.items()
                 if value not in (None, "")}
        return self._request("GET", "/db/logs", params=clean)

    def stats(self):
        return self._request("GET", "/db/stats")

    def health(self):
        return self._request("GET", "/db/health")


class OrderClient:
    """Reads order lines from the Order service over HTTP; degrades to empty when it is down."""

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
        """Return {order_id: [menu name, ...]} for the given orders in one call."""
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


class MenuClient:
    """Supplies menu names through the Order service's /api/menu, falling back to menu_terms.json."""

    def __init__(self, base_url=ORDER_SERVICE_URL, catalog_path=None):
        self.base_url = base_url.rstrip("/")
        self.catalog_path = catalog_path or os.path.join(
            BASE_DIR, "menu_terms.json"
        )
        self._fallback = self._load_fallback()
        self.circuit = PeerCircuit()

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
        """Return ({menu name: entry}, source), live Menu API names merged over the local fallback."""
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
