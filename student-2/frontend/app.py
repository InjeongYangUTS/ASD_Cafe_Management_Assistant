from flask import Flask, render_template, redirect, session, request, jsonify
import os
import requests

app = Flask(__name__)

# Must match the shared authentication service
app.secret_key = "temporary-secret-key"

STUDENT2_BACKEND = os.getenv("STUDENT2_BACKEND_URL", "http://student2-backend:5201")


# -------------------------
# Main Entry
# -------------------------

@app.route("/")
def home():
    # Return to the shared homepage where the user
    # can choose Customer or Staff
    return redirect("http://localhost:5100/")


# -------------------------
# Staff - Menu Management
# -------------------------

@app.route("/staff")
def manage():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("index.html")

@app.route("/menus")
def menus():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("menus.html")


# -------------------------
# Staff - Recipe Management
# -------------------------

@app.route("/recipes")
def recipes():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("recipes.html")


# -------------------------
# Staff - Ingredient Management
# -------------------------

@app.route("/ingredients")
def ingredients():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("ingredients.html")


# -------------------------
# Customer Menu
# -------------------------

@app.route("/customer-menu")
def customer_menu():
    if "customer_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/customer_login.html"
        )

    return render_template("customer_menu.html")

@app.route("/htmx/ai-price-recommendation")
def htmx_ai_price_recommendation():

    # Staff only
    if "staff_id" not in session:
        return "Unauthorized", 401

    menu_id = request.args.get("menu_id")

    if not menu_id:
        return """
            <p class="error-message">
                Please select a menu item.
            </p>
        """

    try:
        response = requests.get(
            f"http://student2-backend:5201/api/ai/price-recommendation/{menu_id}",
            timeout=60
        )

        if not response.ok:
            return """
                <p class="error-message">
                    Unable to generate AI recommendation.
                </p>
            """

        data = response.json()

        return render_template(
            "partials/ai_recommendation.html",
            recommendation=data
        )

    except requests.RequestException:
        return """
            <p class="error-message">
                Unable to connect to the AI service.
            </p>
        """

# -------------------------
# Staff - RAG Assistant
# -------------------------

@app.route("/rag")
def rag_page():
    if "staff_id" not in session:
        return redirect(
            "http://localhost:5100/shared/auth/staff_login.html"
        )

    return render_template("rag.html")


@app.route("/api/rag/query", methods=["POST"])
def frontend_rag_query():

    if "staff_id" not in session:
        return jsonify({
            "error": "Unauthorized"
        }), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A JSON request body is required"
        }), 400

    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({
            "error": "Question is required"
        }), 400

    try:
        response = requests.post(
            f"{STUDENT2_BACKEND}/api/rag/query",
            json={
                "question": question.strip()
            },
            timeout=130
        )

        return jsonify(response.json()), response.status_code

    except requests.Timeout:
        return jsonify({
            "error": "The AI assistant did not respond in time"
        }), 504

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to the AI assistant"
        }), 503

    except ValueError:
        return jsonify({
            "error": "Invalid response from the AI assistant"
        }), 502

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5200,
        debug=True
    )