"""
Student 4 - Order & Kitchen Management
Stand-in services for Student 2 (Menu) and Student 3 (Inventory).

WHY THIS EXISTS
    My feature integrates with two team-mates' APIs. While their services are
    still being built I still need to prove that my integration code works -
    not just that it degrades politely. This script serves the two contracts
    my backend calls, so the cross-feature path can be demonstrated and
    tested today, and switched to the real containers by changing
    MENU_SERVICE_URL / INVENTORY_SERVICE_URL back in docker-compose.yml.

    It is a TEST DOUBLE. It is never part of the deployed application.

CONTRACTS IMPLEMENTED
    GET  /api/menus                  -> Student 2
    POST /api/inventory/check        -> Student 3   {available: bool, ...}
    POST /api/inventory/deduct       -> Student 3
    GET  /api/inventory              -> Student 3   (health probe)

Run:
    python tests/mock_peers.py
    (menu on :8200, inventory on :8300)
"""

import json
import os
import threading

from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "backend", "menu_catalog.json")

MENU_PORT = int(os.environ.get("MOCK_MENU_PORT", 8200))
INVENTORY_PORT = int(os.environ.get("MOCK_INVENTORY_PORT", 8300))

with open(CATALOG_PATH, "r", encoding="utf-8") as handle:
    CATALOG = json.load(handle)["items"]

# Pretend stock, in "portions of this menu item we can still make".
STOCK = {int(item["menu_id"]): 40 for item in CATALOG}
STOCK[12] = 2      # Avocado Toast is nearly out - useful for the demo


menu_app = Flask("mock-student-2-menu")
inventory_app = Flask("mock-student-3-inventory")


@menu_app.get("/api/menus")
def menus():
    """Student 2's shape: a list of menus with a live price."""
    return jsonify([
        {
            "menu_id": item["menu_id"],
            "name": item["name"],
            # +10c on every item so it is obvious in the UI that the price
            # came from the Menu API and not from my fallback cache.
            "price": round(item["price"] + 0.10, 2),
            "available": True,
        }
        for item in CATALOG
    ])


@inventory_app.get("/api/inventory")
def inventory():
    return jsonify({"stock": STOCK})


@inventory_app.post("/api/inventory/check")
def check():
    body = request.get_json(silent=True) or {}
    shortages = []

    for line in body.get("items", []):
        menu_id = int(line["menu_id"])
        quantity = int(line["quantity"])
        if STOCK.get(menu_id, 0) < quantity:
            shortages.append({
                "menu_id": menu_id,
                "requested": quantity,
                "available": STOCK.get(menu_id, 0),
            })

    return jsonify({"available": not shortages, "shortages": shortages})


@inventory_app.post("/api/inventory/deduct")
def deduct():
    body = request.get_json(silent=True) or {}
    applied = []

    for line in body.get("items", []):
        menu_id = int(line["menu_id"])
        quantity = int(line["quantity"])
        STOCK[menu_id] = max(0, STOCK.get(menu_id, 0) - quantity)
        applied.append({"menu_id": menu_id, "deducted": quantity,
                        "remaining": STOCK[menu_id]})

    return jsonify({"deducted": True, "source": body.get("source"),
                    "applied": applied})


def serve(app, port):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=serve, args=(menu_app, MENU_PORT),
                     daemon=True).start()

    print("[mock] Student 2 Menu API      -> http://localhost:%d/api/menus"
          % MENU_PORT)
    print("[mock] Student 3 Inventory API -> http://localhost:%d/api/inventory"
          % INVENTORY_PORT)

    serve(inventory_app, INVENTORY_PORT)
