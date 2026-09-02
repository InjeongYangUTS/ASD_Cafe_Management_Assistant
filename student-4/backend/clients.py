"""
Student 4 (Stella Kwon) - Order & Kitchen Management
Outbound service clients used by the backend/API microservice.

Every cross-feature dependency is reached over HTTP only:

    DatabaseClient   -> student-4-database   (my own SQLite, via its /db API)
    MenuClient       -> student-2-backend    (menu names + prices)
    InventoryClient  -> student-3-backend    (stock check + deduction)
    OllamaClient     -> ollama               (AI-Mode, Llama / Qwen)

No client here opens another team member's SQLite file. Each one degrades
gracefully so the Order service stays usable while a peer service is down,
and always reports which source the data came from.
"""

import json
import os

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_SERVICE_URL = os.environ.get("DB_SERVICE_URL", "http://localhost:7400")
MENU_SERVICE_URL = os.environ.get("MENU_SERVICE_URL", "http://localhost:8200")
INVENTORY_SERVICE_URL = os.environ.get("INVENTORY_SERVICE_URL", "http://localhost:8300")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", 4))
AI_TIMEOUT = float(os.environ.get("AI_TIMEOUT", 45))


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
    """Thin HTTP wrapper over student-4-database. The only way in."""

    def __init__(self, base_url=DB_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    def _request(self, method, path, **kwargs):
        url = self.base_url + path
        try:
            response = requests.request(
                method, url, timeout=HTTP_TIMEOUT, **kwargs
            )
        except requests.RequestException as exc:
            raise ServiceError(
                "order database service is unavailable", 503, str(exc)
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

    # -- orders ------------------------------------------------------
    def list_orders(self, **params):
        return self._request("GET", "/db/orders", params=params)

    def create_order(self, payload):
        return self._request("POST", "/db/orders", json=payload)

    def get_order(self, order_id):
        return self._request("GET", "/db/orders/%d" % order_id)

    def update_order(self, order_id, payload):
        return self._request("PUT", "/db/orders/%d" % order_id, json=payload)

    def delete_order(self, order_id):
        return self._request("DELETE", "/db/orders/%d" % order_id)

    # -- order items -------------------------------------------------
    def list_items(self, order_id):
        return self._request("GET", "/db/orders/%d/items" % order_id)

    def add_item(self, order_id, payload):
        return self._request("POST", "/db/orders/%d/items" % order_id, json=payload)

    def update_item(self, item_id, payload):
        return self._request("PUT", "/db/order-items/%d" % item_id, json=payload)

    def delete_item(self, item_id):
        return self._request("DELETE", "/db/order-items/%d" % item_id)

    # -- order statuses ----------------------------------------------
    def list_statuses(self, order_id):
        return self._request("GET", "/db/orders/%d/statuses" % order_id)

    def add_status(self, order_id, payload):
        return self._request("POST", "/db/orders/%d/statuses" % order_id, json=payload)

    def recent_statuses(self, limit=50):
        return self._request("GET", "/db/order-statuses", params={"limit": limit})

    def delete_status(self, status_id):
        return self._request("DELETE", "/db/order-statuses/%d" % status_id)

    def stats(self):
        return self._request("GET", "/db/stats")

    def health(self):
        return self._request("GET", "/db/health")


# =====================================================================
# Student 2 - Menu & Recipe
# =====================================================================

class MenuClient:
    """
    Reads menu names and prices from Student 2's Menu API.

    Student 2's service may not be running yet (or may be mid-deploy), so a
    local catalogue acts as a fallback cache. Callers can always tell which
    was used through the 'price_source' field on each item.
    """

    def __init__(self, base_url=MENU_SERVICE_URL, catalog_path=None):
        self.base_url = base_url.rstrip("/")
        self.catalog_path = catalog_path or os.path.join(BASE_DIR, "menu_catalog.json")
        self._fallback = self._load_fallback()

    def _load_fallback(self):
        with open(self.catalog_path, "r", encoding="utf-8") as handle:
            catalog = json.load(handle)

        items = {}
        for item in catalog["items"]:
            items[int(item["menu_id"])] = {
                "menu_id": int(item["menu_id"]),
                "name": item["name"],
                "price": float(item["price"]),
                "station": item["station"],
                "prep_seconds": int(item["prep_seconds"]),
                "ingredient_count": int(item["ingredient_count"]),
                "price_source": "fallback",
                "available": True,
            }
        return items

    @staticmethod
    def _normalise(raw):
        """Accept the several shapes Student 2's API might return."""
        if isinstance(raw, dict):
            for key in ("menus", "data", "items", "results"):
                if isinstance(raw.get(key), list):
                    raw = raw[key]
                    break
            else:
                raw = [raw]

        if not isinstance(raw, list):
            return {}

        parsed = {}
        for row in raw:
            if not isinstance(row, dict):
                continue

            menu_id = row.get("menu_id", row.get("id"))
            price = row.get("price", row.get("unit_price", row.get("sale_price")))
            name = row.get("name", row.get("menu_name", row.get("title")))

            if menu_id is None or price is None:
                continue

            try:
                parsed[int(menu_id)] = {
                    "menu_id": int(menu_id),
                    "name": name or ("Menu #%s" % menu_id),
                    "price": float(price),
                    "available": bool(row.get("available", True)),
                }
            except (TypeError, ValueError):
                continue

        return parsed

    def get_catalog(self):
        """
        Return {menu_id: item}. Live prices from Student 2 are merged over the
        fallback so kitchen attributes (station / prep time) are always present.
        """
        catalog = {mid: dict(item) for mid, item in self._fallback.items()}

        try:
            response = requests.get(
                self.base_url + "/api/menus", timeout=HTTP_TIMEOUT
            )
            response.raise_for_status()
            live = self._normalise(response.json())
        except (requests.RequestException, ValueError):
            return catalog, "fallback"

        if not live:
            return catalog, "fallback"

        for menu_id, item in live.items():
            merged = catalog.get(menu_id, {
                "station": "BAR",
                "prep_seconds": 90,
                "ingredient_count": 2,
            })
            merged = dict(merged)
            merged.update({
                "menu_id": menu_id,
                "name": item["name"],
                "price": item["price"],
                "available": item["available"],
                "price_source": "menu-service",
            })
            catalog[menu_id] = merged

        return catalog, "menu-service"

    def health(self):
        try:
            response = requests.get(self.base_url + "/api/menus", timeout=2)
            return {"reachable": response.ok, "url": self.base_url}
        except requests.RequestException:
            return {"reachable": False, "url": self.base_url}


# =====================================================================
# Student 3 - Inventory & Restocking
# =====================================================================

class InventoryClient:
    """
    Checks and deducts stock through Student 3's Inventory API.

    We send menu_id + quantity; Student 3's service resolves the recipe and
    adjusts ingredient stock. We never read their inventory tables directly.
    """

    def __init__(self, base_url=INVENTORY_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    def _post(self, path, lines):
        payload = {
            "source": "student-4-order-service",
            "items": [
                {"menu_id": line["menu_id"], "quantity": line["quantity"]}
                for line in lines
            ],
        }
        response = requests.post(
            self.base_url + path, json=payload, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    def check(self, lines):
        """Return (ok, detail). ok=None means the service was unreachable."""
        try:
            data = self._post("/api/inventory/check", lines)
        except (requests.RequestException, ValueError) as exc:
            return None, {"reason": "inventory service unreachable",
                          "detail": str(exc)}

        available = data.get("available", data.get("ok", True))
        return bool(available), data

    def deduct(self, lines):
        """Return (deducted, detail). deducted=None means unreachable."""
        try:
            data = self._post("/api/inventory/deduct", lines)
        except (requests.RequestException, ValueError) as exc:
            return None, {"reason": "inventory service unreachable",
                          "detail": str(exc)}

        return True, data

    def health(self):
        try:
            response = requests.get(self.base_url + "/api/inventory", timeout=2)
            return {"reachable": response.ok, "url": self.base_url}
        except requests.RequestException:
            return {"reachable": False, "url": self.base_url}


# =====================================================================
# AI-Mode - Ollama runtime
# =====================================================================

class OllamaClient:
    """Calls the shared Ollama runtime with an approved open-source LLM."""

    def __init__(self, base_url=OLLAMA_URL, model=OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt, system=None, temperature=0.2):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        response = requests.post(
            self.base_url + "/api/generate", json=payload, timeout=AI_TIMEOUT
        )
        response.raise_for_status()

        return response.json().get("response", "").strip()

    def health(self):
        try:
            response = requests.get(self.base_url + "/api/tags", timeout=3)
            models = [m.get("name") for m in response.json().get("models", [])]
            return {"reachable": response.ok, "url": self.base_url,
                    "model": self.model, "installed_models": models}
        except (requests.RequestException, ValueError):
            return {"reachable": False, "url": self.base_url, "model": self.model}
