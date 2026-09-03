#student-3/backend/app.py

import os

from flask import Flask
from pathlib import Path

from routes.dashboard_routes import dashboard_bp
from routes.inventory_routes import inventory_bp
from routes.supplier_routes import supplier_bp
from routes.restock_routes import restock_bp


# =========================================================
# PROJECT PATHS
# =========================================================

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent

TEMPLATE_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "assets"


# =========================================================
# CREATE FLASK APPLICATION
# =========================================================

def create_app():

    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR)
    )

    app.config["SECRET_KEY"] = "inventory-development-secret-key"

    # =====================================================
    # REGISTER BLUEPRINTS
    # =====================================================

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(supplier_bp)
    app.register_blueprint(restock_bp)


    return app


# =========================================================
# APPLICATION INSTANCE
# =========================================================

app = create_app()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "5300")
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )