import os
from pathlib import Path

from flask import Flask, jsonify, redirect, request

from backend_client import BackendError
from routes.dashboard_routes import dashboard_bp
from routes.inventory_routes import inventory_bp
from routes.restock_routes import restock_bp
from routes.supplier_routes import supplier_bp


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR.parent / "assets"
SHARED_HOME_URL = os.getenv("SHARED_HOME_URL")
SHARED_PORT = os.getenv("SHARED_PORT", "5100")

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
app.secret_key = os.getenv("SECRET_KEY", "student-3-inventory-frontend-key")
app.register_blueprint(dashboard_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(supplier_bp)
app.register_blueprint(restock_bp)


@app.errorhandler(BackendError)
def handle_backend_error(exc):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"error": exc.message, "detail": exc.detail}), exc.status_code
    return f"Inventory service error: {exc.message}", exc.status_code


@app.context_processor
def inject_shared_home():
    if SHARED_HOME_URL:
        return {"shared_home": SHARED_HOME_URL}
    host = request.host.split(":")[0]
    return {"shared_home": f"{request.scheme}://{host}:{SHARED_PORT}/staff-dashboard"}


@app.get("/")
def home():
    return redirect("/inventory/")


@app.get("/health")
def health():
    from backend_client import call_backend
    try:
        backend = call_backend("GET", "/api/health")
        return {"service": "student-3-frontend", "status": "healthy", "backend": backend}
    except BackendError as exc:
        return {"service": "student-3-frontend", "status": "degraded", "detail": exc.message}, 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5300")), debug=False)
