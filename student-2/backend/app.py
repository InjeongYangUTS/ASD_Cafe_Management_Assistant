from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)


DATABASE_SERVICE = os.getenv("DATABASE_SERVICE_URL", "http://localhost:5202")


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

    # Get required pricing information
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