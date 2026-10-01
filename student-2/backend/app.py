from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from mcp_client import call_mcp_tool

app = Flask(__name__)
CORS(app)


DATABASE_SERVICE = os.getenv("DATABASE_SERVICE_URL", "http://localhost:5202")

RAG_SERVICE = os.getenv("RAG_SERVICE_URL", "http://host.docker.internal:5600")

# =========================================================
# MENU ROUTES
# =========================================================

# -----------------------------
# GET ALL MENUS
# -----------------------------

@app.route("/api/menus", methods=["GET"])
def get_menus():
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/menus",
            timeout=10
        )

        if not response.ok:
            return jsonify({
                "error": "Unable to retrieve menus from database service"
            }), response.status_code

        return jsonify(response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# GET ONE MENU
# -----------------------------

@app.route("/api/menus/<int:menu_id>", methods=["GET"])
def get_menu(menu_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/menus/{menu_id}",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Menu item not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to retrieve menu item"
            }), response.status_code

        return jsonify(response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# CREATE MENU
# -----------------------------

@app.route("/api/menus", methods=["POST"])
def create_menu():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    name = data.get("name")
    category = data.get("category")
    description = data.get("description", "")
    price = data.get("price")

    if not name or not category or price is None:
        return jsonify({
            "error": "Name, category and price are required"
        }), 400

    try:
        price = float(price)

        if price < 0:
            return jsonify({
                "error": "Price must be 0 or greater"
            }), 400

    except (TypeError, ValueError):
        return jsonify({
            "error": "Price must be a valid number"
        }), 400

    try:
        response = requests.post(
            f"{DATABASE_SERVICE}/api/database/menus",
            json={
                "name": name,
                "category": category,
                "description": description,
                "price": price
            },
            timeout=10
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# UPDATE MENU
# -----------------------------

@app.route("/api/menus/<int:menu_id>", methods=["PUT"])
def update_menu(menu_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    try:
        existing_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/menus/{menu_id}",
            timeout=10
        )

        if existing_response.status_code == 404:
            return jsonify({
                "error": "Menu item not found"
            }), 404

        if not existing_response.ok:
            return jsonify({
                "error": "Unable to retrieve menu item"
            }), existing_response.status_code

        existing_menu = existing_response.json()

        name = data.get(
            "name",
            existing_menu["name"]
        )

        category = data.get(
            "category",
            existing_menu["category"]
        )

        description = data.get(
            "description",
            existing_menu["description"]
        )

        price = data.get(
            "price",
            existing_menu["price"]
        )

        try:
            price = float(price)

            if price < 0:
                raise ValueError

        except (TypeError, ValueError):
            return jsonify({
                "error": "Price must be a valid positive number"
            }), 400

        response = requests.put(
            f"{DATABASE_SERVICE}/api/database/menus/{menu_id}",
            json={
                "name": name,
                "category": category,
                "description": description,
                "price": price
            },
            timeout=10
        )

        if not response.ok:
            return jsonify(
                response.json()
            ), response.status_code

        updated_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/menus/{menu_id}",
            timeout=10
        )

        return jsonify(updated_response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# DELETE MENU
# -----------------------------

@app.route("/api/menus/<int:menu_id>", methods=["DELETE"])
def delete_menu(menu_id):
    try:
        response = requests.delete(
            f"{DATABASE_SERVICE}/api/database/menus/{menu_id}",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Menu item not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to delete menu item"
            }), response.status_code

        return jsonify({
            "message": "Menu item deleted successfully"
        })

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# =========================================================
# MENU PRICE ROUTES
# =========================================================

@app.route("/api/menu-prices/<int:menu_id>", methods=["GET"])
def get_menu_price(menu_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/menu-prices/{menu_id}",
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


@app.route("/api/menu-prices/<int:menu_id>", methods=["PUT"])
def update_menu_price(menu_id):
    data = request.get_json()

    if not data or "price" not in data:
        return jsonify({
            "error": "Price is required"
        }), 400

    try:
        price = float(data["price"])

        if price < 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "error": "Price must be a valid positive number"
        }), 400

    try:
        response = requests.put(
            f"{DATABASE_SERVICE}/api/database/menu-prices/{menu_id}",
            json={
                "price": price
            },
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# =========================================================
# INGREDIENT ROUTES
# =========================================================

# -----------------------------
# GET ALL INGREDIENTS
# -----------------------------

@app.route("/api/ingredients", methods=["GET"])
def get_ingredients():
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/ingredients",
            timeout=10
        )

        if not response.ok:
            return jsonify({
                "error": "Unable to retrieve ingredients"
            }), response.status_code

        return jsonify(response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# GET ONE INGREDIENT
# -----------------------------

@app.route("/api/ingredients/<int:ingredient_id>", methods=["GET"])
def get_ingredient(ingredient_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/ingredients/{ingredient_id}",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Ingredient not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to retrieve ingredient"
            }), response.status_code

        return jsonify(response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# CREATE INGREDIENT
# -----------------------------

@app.route("/api/ingredients", methods=["POST"])
def create_ingredient():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    name = data.get("name")
    unit = data.get("unit")
    unit_cost = data.get("unit_cost")

    if not name or not unit or unit_cost is None:
        return jsonify({
            "error": "Name, unit and unit_cost are required"
        }), 400

    try:
        unit_cost = float(unit_cost)

        if unit_cost < 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "error": "Unit cost must be a valid positive number"
        }), 400

    try:
        response = requests.post(
            f"{DATABASE_SERVICE}/api/database/ingredients",
            json={
                "name": name,
                "unit": unit,
                "unit_cost": unit_cost
            },
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# UPDATE INGREDIENT
# -----------------------------

@app.route(
    "/api/ingredients/<int:ingredient_id>",
    methods=["PUT"]
)
def update_ingredient(ingredient_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    try:
        existing_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/ingredients/{ingredient_id}",
            timeout=10
        )

        if existing_response.status_code == 404:
            return jsonify({
                "error": "Ingredient not found"
            }), 404

        if not existing_response.ok:
            return jsonify({
                "error": "Unable to retrieve ingredient"
            }), existing_response.status_code

        existing = existing_response.json()

        name = data.get(
            "name",
            existing["name"]
        )

        unit = data.get(
            "unit",
            existing["unit"]
        )

        unit_cost = data.get(
            "unit_cost",
            existing["unit_cost"]
        )

        try:
            unit_cost = float(unit_cost)

            if unit_cost < 0:
                raise ValueError

        except (TypeError, ValueError):
            return jsonify({
                "error": "Unit cost must be a valid positive number"
            }), 400

        response = requests.put(
            f"{DATABASE_SERVICE}/api/database/ingredients/{ingredient_id}",
            json={
                "name": name,
                "unit": unit,
                "unit_cost": unit_cost
            },
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# DELETE INGREDIENT
# -----------------------------

@app.route(
    "/api/ingredients/<int:ingredient_id>",
    methods=["DELETE"]
)
def delete_ingredient(ingredient_id):
    try:
        response = requests.delete(
            f"{DATABASE_SERVICE}/api/database/ingredients/{ingredient_id}",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Ingredient not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to delete ingredient"
            }), response.status_code

        return jsonify({
            "message": "Ingredient deleted successfully"
        })

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# =========================================================
# RECIPE ROUTES
# =========================================================

# -----------------------------
# GET ALL RECIPES
# -----------------------------

@app.route("/api/recipes", methods=["GET"])
def get_recipes():
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/recipes",
            timeout=10
        )

        if not response.ok:
            return jsonify({
                "error": "Unable to retrieve recipes"
            }), response.status_code

        return jsonify(response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# GET ONE RECIPE
# -----------------------------

@app.route("/api/recipes/<int:recipe_id>", methods=["GET"])
def get_recipe(recipe_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/recipes/{recipe_id}",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Recipe not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to retrieve recipe"
            }), response.status_code

        return jsonify(response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# CREATE RECIPE
# -----------------------------

@app.route("/api/recipes", methods=["POST"])
def create_recipe():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    menu_id = data.get("menu_id")
    name = data.get("name")
    instructions = data.get("instructions")

    if menu_id is None or not name or not instructions:
        return jsonify({
            "error": "Menu ID, name and instructions are required"
        }), 400

    try:
        menu_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/menus/{menu_id}",
            timeout=10
        )

        if menu_response.status_code == 404:
            return jsonify({
                "error": "Menu item not found"
            }), 404

        if not menu_response.ok:
            return jsonify({
                "error": "Unable to verify menu item"
            }), menu_response.status_code

        response = requests.post(
            f"{DATABASE_SERVICE}/api/database/recipes",
            json={
                "menu_id": menu_id,
                "name": name,
                "instructions": instructions
            },
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# UPDATE RECIPE
# -----------------------------

@app.route("/api/recipes/<int:recipe_id>", methods=["PUT"])
def update_recipe(recipe_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    try:
        existing_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/recipes/{recipe_id}",
            timeout=10
        )

        if existing_response.status_code == 404:
            return jsonify({
                "error": "Recipe not found"
            }), 404

        if not existing_response.ok:
            return jsonify({
                "error": "Unable to retrieve recipe"
            }), existing_response.status_code

        existing = existing_response.json()

        menu_id = data.get(
            "menu_id",
            existing["menu_id"]
        )

        name = data.get(
            "name",
            existing["name"]
        )

        instructions = data.get(
            "instructions",
            existing["instructions"]
        )

        menu_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/menus/{menu_id}",
            timeout=10
        )

        if menu_response.status_code == 404:
            return jsonify({
                "error": "Menu item not found"
            }), 404

        if not menu_response.ok:
            return jsonify({
                "error": "Unable to verify menu item"
            }), menu_response.status_code

        response = requests.put(
            f"{DATABASE_SERVICE}/api/database/recipes/{recipe_id}",
            json={
                "menu_id": menu_id,
                "name": name,
                "instructions": instructions
            },
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# DELETE RECIPE
# -----------------------------

@app.route(
    "/api/recipes/<int:recipe_id>",
    methods=["DELETE"]
)
def delete_recipe(recipe_id):
    try:
        response = requests.delete(
            f"{DATABASE_SERVICE}/api/database/recipes/{recipe_id}",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Recipe not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to delete recipe"
            }), response.status_code

        return jsonify({
            "message": "Recipe deleted successfully"
        })

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# =========================================================
# RECIPE INGREDIENT ROUTES
# =========================================================

# -----------------------------
# GET RECIPE INGREDIENTS
# -----------------------------

@app.route(
    "/api/recipes/<int:recipe_id>/ingredients",
    methods=["GET"]
)
def get_recipe_ingredients(recipe_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE}/api/database/recipes/{recipe_id}/ingredients",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Recipe not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to retrieve recipe ingredients"
            }), response.status_code

        return jsonify(response.json())

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# ADD INGREDIENT TO RECIPE
# -----------------------------

@app.route(
    "/api/recipes/<int:recipe_id>/ingredients",
    methods=["POST"]
)
def add_recipe_ingredient(recipe_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    ingredient_id = data.get("ingredient_id")
    quantity = data.get("quantity")
    unit = data.get("unit")

    if ingredient_id is None or quantity is None or not unit:
        return jsonify({
            "error": "Ingredient ID, quantity and unit are required"
        }), 400

    try:
        quantity = float(quantity)

        if quantity <= 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "error": "Quantity must be a valid positive number"
        }), 400

    try:
        recipe_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/recipes/{recipe_id}",
            timeout=10
        )

        if recipe_response.status_code == 404:
            return jsonify({
                "error": "Recipe not found"
            }), 404

        if not recipe_response.ok:
            return jsonify({
                "error": "Unable to verify recipe"
            }), recipe_response.status_code

        ingredient_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/ingredients/{ingredient_id}",
            timeout=10
        )

        if ingredient_response.status_code == 404:
            return jsonify({
                "error": "Ingredient not found"
            }), 404

        if not ingredient_response.ok:
            return jsonify({
                "error": "Unable to verify ingredient"
            }), ingredient_response.status_code

        response = requests.post(
            f"{DATABASE_SERVICE}/api/database/recipes/{recipe_id}/ingredients",
            json={
                "ingredient_id": ingredient_id,
                "quantity": quantity,
                "unit": unit
            },
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# UPDATE RECIPE INGREDIENT
# -----------------------------

@app.route(
    "/api/recipe-ingredients/<int:recipe_ingredient_id>",
    methods=["PUT"]
)
def update_recipe_ingredient(recipe_ingredient_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    try:
        existing_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/recipe-ingredients/{recipe_ingredient_id}",
            timeout=10
        )

        if existing_response.status_code == 404:
            return jsonify({
                "error": "Recipe ingredient not found"
            }), 404

        if not existing_response.ok:
            return jsonify({
                "error": "Unable to retrieve recipe ingredient"
            }), existing_response.status_code

        existing = existing_response.json()

        ingredient_id = data.get(
            "ingredient_id",
            existing["ingredient_id"]
        )

        quantity = data.get(
            "quantity",
            existing["quantity"]
        )

        unit = data.get(
            "unit",
            existing["unit"]
        )

        try:
            quantity = float(quantity)

            if quantity <= 0:
                raise ValueError

        except (TypeError, ValueError):
            return jsonify({
                "error": "Quantity must be a valid positive number"
            }), 400

        ingredient_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/ingredients/{ingredient_id}",
            timeout=10
        )

        if ingredient_response.status_code == 404:
            return jsonify({
                "error": "Ingredient not found"
            }), 404

        if not ingredient_response.ok:
            return jsonify({
                "error": "Unable to verify ingredient"
            }), ingredient_response.status_code

        response = requests.put(
            f"{DATABASE_SERVICE}/api/database/recipe-ingredients/{recipe_ingredient_id}",
            json={
                "ingredient_id": ingredient_id,
                "quantity": quantity,
                "unit": unit
            },
            timeout=10
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# -----------------------------
# DELETE RECIPE INGREDIENT
# -----------------------------

@app.route(
    "/api/recipe-ingredients/<int:recipe_ingredient_id>",
    methods=["DELETE"]
)
def delete_recipe_ingredient(recipe_ingredient_id):
    try:
        response = requests.delete(
            f"{DATABASE_SERVICE}/api/database/recipe-ingredients/{recipe_ingredient_id}",
            timeout=10
        )

        if response.status_code == 404:
            return jsonify({
                "error": "Recipe ingredient not found"
            }), 404

        if not response.ok:
            return jsonify({
                "error": "Unable to delete recipe ingredient"
            }), response.status_code

        return jsonify({
            "message": "Recipe ingredient deleted successfully"
        })

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500


# =========================================================
# AI PRICE RECOMMENDATION
# =========================================================

@app.route(
    "/api/ai/price-recommendation/<int:menu_id>",
    methods=["GET"]
)
def ai_price_recommendation(menu_id):

    # from the database microservice.
    try:
        database_response = requests.get(
            f"{DATABASE_SERVICE}/api/database/ai-price-data/{menu_id}",
            timeout=10
        )

        if database_response.status_code == 404:
            return jsonify({
                "error": "Menu item not found"
            }), 404

        if database_response.status_code == 400:
            return jsonify(
                database_response.json()
            ), 400

        if not database_response.ok:
            return jsonify({
                "error": "Unable to retrieve pricing data"
            }), database_response.status_code

        price_data = database_response.json()

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to database service"
        }), 500

    menu_name = price_data["menu_name"]
    current_price = float(
        price_data["current_price"]
    )
    ingredient_cost = float(
        price_data["ingredient_cost"]
    )

    # Calculate current profitability.
    gross_profit = current_price - ingredient_cost

    if current_price <= 0:
        return jsonify({
            "error": "Menu price must be greater than 0"
        }), 400

    gross_margin = (
        gross_profit / current_price
    ) * 100

    target_margin = 70.0

    # Backend performs the maths.
    # AI only explains the recommendation.
    if gross_margin >= target_margin:
        suggested_price = current_price
        pricing_action = "Maintain the current price"

    else:
        suggested_price = ingredient_cost / (
            1 - (target_margin / 100)
        )

        suggested_price = round(
            suggested_price,
            2
        )

        pricing_action = "Increase the current price"

    prompt = f"""
You are assisting staff with cafe menu pricing.

Use only the information below.

Menu item: {menu_name}
Current price: ${current_price:.2f}
Suggested price: ${suggested_price:.2f}
Current gross margin: {gross_margin:.2f}%
Target gross margin: {target_margin:.2f}%
Pricing action: {pricing_action}

Write exactly one short sentence explaining the pricing action.

Do not calculate anything.
Do not mention formulas.
Do not suggest another price.
Do not change any numbers.
Do not add extra details.
"""

    try:
        ollama_response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "qwen2.5:0.5b",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        ollama_response.raise_for_status()

        result = ollama_response.json()

        return jsonify({
            "menu_id": menu_id,
            "menu_name": menu_name,
            "ingredient_cost": round(
                ingredient_cost,
                2
            ),
            "current_price": round(
                current_price,
                2
            ),
            "gross_profit": round(
                gross_profit,
                2
            ),
            "gross_margin": round(
                gross_margin,
                2
            ),
            "target_margin": target_margin,
            "suggested_price": suggested_price,
            "pricing_action": pricing_action,
            "ai_explanation": result.get(
                "response",
                ""
            )
        })

    except requests.RequestException as error:
        return jsonify({
            "error": "Unable to connect to Ollama",
            "details": str(error)
        }), 503

# =========================================================
# SHARED RAG INTEGRATION
# =========================================================

@app.route("/api/rag/query", methods=["POST"])
def rag_query():

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
            f"{RAG_SERVICE}/query",
            json={
                "question": question.strip()
            },
            timeout=120
        )

        response.raise_for_status()

        return jsonify(response.json()), response.status_code

    except requests.Timeout:
        return jsonify({
            "error": "The RAG server did not respond in time"
        }), 504

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to the RAG server"
        }), 503

    except ValueError:
        return jsonify({
            "error": "Invalid response from the RAG server"
        }), 502

# =========================================================
# SHARED MCP INTEGRATION
# =========================================================

@app.route("/api/mcp/query", methods=["POST"])
def mcp_query():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid request"
        }), 400

    question = data.get("question", "").strip()
    question_lower = question.lower()

    if not question:
        return jsonify({
            "error": "Question is required"
        }), 400

    try:

        # -------------------------------------------------
        # Load live Student 2 data through MCP
        # -------------------------------------------------

        menus_result = call_mcp_tool("get_menus")
        recipes_result = call_mcp_tool("get_recipes")
        ingredients_result = call_mcp_tool("get_ingredients")

        menus = menus_result.get("menus", [])
        recipes = recipes_result.get("recipes", [])
        ingredients = ingredients_result.get("ingredients", [])

        # -------------------------------------------------
        # Counts
        # -------------------------------------------------

        if "how many" in question_lower:

            if "recipe" in question_lower:
                return jsonify({
                    "status": "success",
                    "source": "MCP",
                    "tool": "get_recipes",
                    "answer": (
                        f"There are {len(recipes)} recipes "
                        "in the live Menu & Recipe data."
                    )
                })

            if "ingredient" in question_lower:
                return jsonify({
                    "status": "success",
                    "source": "MCP",
                    "tool": "get_ingredients",
                    "answer": (
                        f"There are {len(ingredients)} ingredients "
                        "in the live Menu & Recipe data."
                    )
                })

            if "menu" in question_lower:
                return jsonify({
                    "status": "success",
                    "source": "MCP",
                    "tool": "get_menus",
                    "answer": (
                        f"There are {len(menus)} menu items "
                        "in the live Menu & Recipe data."
                    )
                })

        # -------------------------------------------------
        # Find matching menu / recipe / ingredient
        # -------------------------------------------------

        matching_menu = next(
            (
                menu for menu in menus
                if str(menu.get("name", "")).lower() in question_lower
                or str(menu.get("menu_name", "")).lower() in question_lower
            ),
            None
        )

        matching_recipe = next(
            (
                recipe for recipe in recipes
                if str(recipe.get("menu_name", "")).lower() in question_lower
                or str(recipe.get("name", "")).lower() in question_lower
            ),
            None
        )

        matching_ingredient = next(
            (
                ingredient for ingredient in ingredients
                if str(ingredient.get("name", "")).lower() in question_lower
                or str(ingredient.get("ingredient_name", "")).lower()
                in question_lower
            ),
            None
        )

        # -------------------------------------------------
        # Price of a menu item
        # -------------------------------------------------

        if (
            ("price" in question_lower or "cost" in question_lower)
            and matching_menu
        ):
            menu_id = matching_menu.get("menu_id")

            result = call_mcp_tool(
                "get_menu_price",
                {"menu_id": menu_id}
            )

            price = result.get("price")

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_menu_price",
                "answer": (
                    f"Price information for "
                    f"{matching_menu.get('name') or matching_menu.get('menu_name')}: "
                    f"{format_mcp_value(price)}"
                )
            })

        # -------------------------------------------------
        # Ingredients assigned to a recipe
        # -------------------------------------------------

        if "ingredient" in question_lower and matching_recipe:

            recipe_id = matching_recipe.get("recipe_id")

            result = call_mcp_tool(
                "get_recipe_ingredients",
                {"recipe_id": recipe_id}
            )

            recipe_ingredients = result.get("ingredients", [])

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_recipe_ingredients",
                "answer": (
                    f"Ingredients for "
                    f"{matching_recipe.get('name')}: "
                    f"{format_mcp_list(recipe_ingredients)}"
                )
            })

        # -------------------------------------------------
        # Specific recipe
        # -------------------------------------------------

        if "recipe" in question_lower and matching_recipe:

            recipe_id = matching_recipe.get("recipe_id")

            result = call_mcp_tool(
                "get_recipe",
                {"recipe_id": recipe_id}
            )

            recipe = result.get("recipe", {})

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_recipe",
                "answer": format_recipe(recipe)
            })

        # -------------------------------------------------
        # Specific ingredient
        # -------------------------------------------------

        if matching_ingredient:

            ingredient_id = matching_ingredient.get("ingredient_id")

            result = call_mcp_tool(
                "get_ingredient",
                {"ingredient_id": ingredient_id}
            )

            ingredient = result.get("ingredient", {})

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_ingredient",
                "answer": format_mcp_value(ingredient)
            })

        # -------------------------------------------------
        # Specific menu item
        # -------------------------------------------------

        if matching_menu:

            menu_id = matching_menu.get("menu_id")

            result = call_mcp_tool(
                "get_menu",
                {"menu_id": menu_id}
            )

            menu = result.get("menu", {})

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_menu",
                "answer": format_mcp_value(menu)
            })

        # -------------------------------------------------
        # List recipes
        # -------------------------------------------------

        if "recipe" in question_lower:

            names = [
                recipe.get("name")
                for recipe in recipes
                if recipe.get("name")
            ]

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_recipes",
                "answer": (
                    "Available recipes: "
                    + ", ".join(names)
                )
            })

        # -------------------------------------------------
        # List ingredients
        # -------------------------------------------------

        if "ingredient" in question_lower:

            names = [
                ingredient.get("name")
                or ingredient.get("ingredient_name")
                for ingredient in ingredients
            ]

            names = [name for name in names if name]

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_ingredients",
                "answer": (
                    "Available ingredients: "
                    + ", ".join(names)
                )
            })

        # -------------------------------------------------
        # List menu items
        # -------------------------------------------------

        if "menu" in question_lower:

            names = [
                menu.get("name")
                or menu.get("menu_name")
                for menu in menus
            ]

            names = [name for name in names if name]

            return jsonify({
                "status": "success",
                "source": "MCP",
                "tool": "get_menus",
                "answer": (
                    "Available menu items: "
                    + ", ".join(names)
                )
            })

        # -------------------------------------------------
        # Unsupported live-data question
        # -------------------------------------------------

        return jsonify({
            "status": "unsupported",
            "source": "MCP",
            "answer": (
                "I can answer live questions about menus, prices, "
                "recipes and ingredients."
            )
        })

    except RuntimeError as error:
        return jsonify({
            "error": str(error)
        }), 502

    except Exception as error:
        return jsonify({
            "error": "Unable to connect to the MCP server",
            "details": str(error)
        }), 503


def format_recipe(recipe):

    name = (
        recipe.get("name")
        or recipe.get("menu_name")
        or "Recipe"
    )

    instructions = recipe.get("instructions")

    if instructions:
        return f"{name}: {instructions}"

    return format_mcp_value(recipe)


def format_mcp_list(items):

    if not items:
        return "No data available."

    formatted_items = []

    for item in items:

        if isinstance(item, dict):

            name = (
                item.get("ingredient_name")
                or item.get("name")
            )

            quantity = (
                item.get("quantity")
                or item.get("amount")
            )

            unit = item.get("unit")

            if name:
                text = str(name)

                if quantity:
                    text += f" - {quantity}"

                if unit:
                    text += f" {unit}"

                formatted_items.append(text)

            else:
                formatted_items.append(
                    format_mcp_value(item)
                )

        else:
            formatted_items.append(str(item))

    return ", ".join(formatted_items)


def format_mcp_value(value):

    if isinstance(value, dict):

        parts = []

        for key, item in value.items():

            if item is None:
                continue

            readable_key = key.replace("_", " ").title()

            parts.append(
                f"{readable_key}: {item}"
            )

        return ", ".join(parts)

    if isinstance(value, list):
        return format_mcp_list(value)

    return str(value)

# =========================================================
# TEST / HEALTH ROUTE
# =========================================================

@app.route("/")
def home():
    return jsonify({
        "service": "Menu & Recipe Backend API",
        "status": "running"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5201,
        debug=True
    )