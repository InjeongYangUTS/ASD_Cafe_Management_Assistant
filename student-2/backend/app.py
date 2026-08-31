from flask import Flask, jsonify, request
import sqlite3
from pathlib import Path

app = Flask(__name__)

DB_PATH = Path(__file__).parent.parent / "database" / "menu_recipe.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# GET ALL MENUS
# -----------------------------

@app.route("/api/menus", methods=["GET"])
def get_menus():
    conn = get_db_connection()

    menus = conn.execute("""
        SELECT
            menu_id,
            name,
            category,
            description,
            price
        FROM menus
        ORDER BY menu_id
    """).fetchall()

    conn.close()

    return jsonify([dict(menu) for menu in menus])


# -----------------------------
# GET ONE MENU
# -----------------------------

@app.route("/api/menus/<int:menu_id>", methods=["GET"])
def get_menu(menu_id):
    conn = get_db_connection()

    menu = conn.execute("""
        SELECT
            menu_id,
            name,
            category,
            description,
            price
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    conn.close()

    if menu is None:
        return jsonify({
            "error": "Menu item not found"
        }), 404

    return jsonify(dict(menu))


# -----------------------------
# CREATE MENU
# -----------------------------

@app.route("/api/menus", methods=["POST"])
def create_menu():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = data.get("name")
    category = data.get("category")
    description = data.get("description", "")
    price = data.get("price")

    if not name or not category or price is None:
        return jsonify({
            "error": "Name, category and price are required"
        }), 400

    conn = get_db_connection()

    cursor = conn.execute(
        """
        INSERT INTO menus (name, category, description, price)
        VALUES (?, ?, ?, ?)
        """,
        (name, category, description, price)
    )

    conn.commit()

    new_menu_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Menu item created successfully",
        "menu_id": new_menu_id
    }), 201


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

    conn = get_db_connection()

    existing_menu = conn.execute("""
        SELECT *
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    if existing_menu is None:
        conn.close()

        return jsonify({
            "error": "Menu item not found"
        }), 404

    name = data.get("name", existing_menu["name"])
    category = data.get("category", existing_menu["category"])
    description = data.get(
        "description",
        existing_menu["description"]
    )
    price = data.get("price", existing_menu["price"])

    try:
        price = float(price)

        if price < 0:
            raise ValueError

    except (TypeError, ValueError):
        conn.close()

        return jsonify({
            "error": "Price must be a valid positive number"
        }), 400

    conn.execute("""
        UPDATE menus
        SET
            name = ?,
            category = ?,
            description = ?,
            price = ?
        WHERE menu_id = ?
    """, (
        name,
        category,
        description,
        price,
        menu_id
    ))

    conn.commit()

    updated_menu = conn.execute("""
        SELECT
            menu_id,
            name,
            category,
            description,
            price
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    conn.close()

    return jsonify(dict(updated_menu))


# -----------------------------
# DELETE MENU
# -----------------------------

@app.route("/api/menus/<int:menu_id>", methods=["DELETE"])
def delete_menu(menu_id):
    conn = get_db_connection()

    menu = conn.execute("""
        SELECT *
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    if menu is None:
        conn.close()

        return jsonify({
            "error": "Menu item not found"
        }), 404

    conn.execute("""
        DELETE FROM menus
        WHERE menu_id = ?
    """, (menu_id,))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Menu item deleted successfully"
    })


# -----------------------------
# MENU PRICE
# -----------------------------

@app.route("/api/menu-prices/<int:menu_id>", methods=["GET"])
def get_menu_price(menu_id):
    conn = get_db_connection()

    menu = conn.execute("""
        SELECT
            menu_id,
            name,
            price
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    conn.close()

    if menu is None:
        return jsonify({
            "error": "Menu item not found"
        }), 404

    return jsonify(dict(menu))


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

    conn = get_db_connection()

    menu = conn.execute("""
        SELECT *
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    if menu is None:
        conn.close()

        return jsonify({
            "error": "Menu item not found"
        }), 404

    conn.execute("""
        UPDATE menus
        SET price = ?
        WHERE menu_id = ?
    """, (
        price,
        menu_id
    ))

    conn.commit()

    updated_menu = conn.execute("""
        SELECT
            menu_id,
            name,
            price
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    conn.close()

    return jsonify(dict(updated_menu))

# -----------------------------
# GET ALL INGREDIENTS
# -----------------------------

@app.route("/api/ingredients", methods=["GET"])
def get_ingredients():
    conn = get_db_connection()

    ingredients = conn.execute("""
        SELECT
            i.ingredient_id,
            i.name,
            i.unit,
            ic.unit_cost
        FROM ingredients i
        LEFT JOIN ingredient_costs ic
            ON i.ingredient_id = ic.ingredient_id
        ORDER BY i.ingredient_id
    """).fetchall()

    conn.close()

    return jsonify([dict(ingredient) for ingredient in ingredients])

# -----------------------------
# GET ONE INGREDIENT
# -----------------------------

@app.route("/api/ingredients/<int:ingredient_id>", methods=["GET"])
def get_ingredient(ingredient_id):
    conn = get_db_connection()

    ingredient = conn.execute("""
        SELECT
            i.ingredient_id,
            i.name,
            i.unit,
            ic.unit_cost
        FROM ingredients i
        LEFT JOIN ingredient_costs ic
            ON i.ingredient_id = ic.ingredient_id
        WHERE i.ingredient_id = ?
    """, (ingredient_id,)).fetchone()

    conn.close()

    if ingredient is None:
        return jsonify({
            "error": "Ingredient not found"
        }), 404

    return jsonify(dict(ingredient))

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

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO ingredients
        (name, unit)
        VALUES (?, ?)
    """, (
        name,
        unit
    ))

    ingredient_id = cursor.lastrowid

    conn.execute("""
        INSERT INTO ingredient_costs
        (ingredient_id, unit_cost)
        VALUES (?, ?)
    """, (
        ingredient_id,
        unit_cost
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Ingredient created successfully",
        "ingredient_id": ingredient_id
    }), 201

# -----------------------------
# UPDATE INGREDIENT
# -----------------------------

@app.route("/api/ingredients/<int:ingredient_id>", methods=["PUT"])
def update_ingredient(ingredient_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    conn = get_db_connection()

    ingredient = conn.execute("""
        SELECT
            i.ingredient_id,
            i.name,
            i.unit,
            ic.unit_cost
        FROM ingredients i
        LEFT JOIN ingredient_costs ic
            ON i.ingredient_id = ic.ingredient_id
        WHERE i.ingredient_id = ?
    """, (ingredient_id,)).fetchone()

    if ingredient is None:
        conn.close()

        return jsonify({
            "error": "Ingredient not found"
        }), 404

    name = data.get("name", ingredient["name"])
    unit = data.get("unit", ingredient["unit"])
    unit_cost = data.get("unit_cost", ingredient["unit_cost"])

    try:
        unit_cost = float(unit_cost)

        if unit_cost < 0:
            raise ValueError

    except (TypeError, ValueError):
        conn.close()

        return jsonify({
            "error": "Unit cost must be a valid positive number"
        }), 400

    conn.execute("""
        UPDATE ingredients
        SET
            name = ?,
            unit = ?
        WHERE ingredient_id = ?
    """, (
        name,
        unit,
        ingredient_id
    ))

    conn.execute("""
        UPDATE ingredient_costs
        SET unit_cost = ?
        WHERE ingredient_id = ?
    """, (
        unit_cost,
        ingredient_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Ingredient updated successfully"
    })

# -----------------------------
# DELETE INGREDIENT
# -----------------------------

@app.route("/api/ingredients/<int:ingredient_id>", methods=["DELETE"])
def delete_ingredient(ingredient_id):
    conn = get_db_connection()

    ingredient = conn.execute("""
        SELECT *
        FROM ingredients
        WHERE ingredient_id = ?
    """, (ingredient_id,)).fetchone()

    if ingredient is None:
        conn.close()

        return jsonify({
            "error": "Ingredient not found"
        }), 404

    conn.execute("""
        DELETE FROM ingredient_costs
        WHERE ingredient_id = ?
    """, (ingredient_id,))

    conn.execute("""
        DELETE FROM ingredients
        WHERE ingredient_id = ?
    """, (ingredient_id,))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Ingredient deleted successfully"
    })

# -----------------------------
# GET ALL RECIPES
# -----------------------------

@app.route("/api/recipes", methods=["GET"])
def get_recipes():
    conn = get_db_connection()

    recipes = conn.execute("""
        SELECT
            r.recipe_id,
            r.menu_id,
            r.name,
            r.instructions,
            m.name AS menu_name
        FROM recipes r
        JOIN menus m
            ON r.menu_id = m.menu_id
        ORDER BY r.recipe_id
    """).fetchall()

    conn.close()

    return jsonify([dict(recipe) for recipe in recipes])

# -----------------------------
# GET ONE RECIPE
# -----------------------------

@app.route("/api/recipes/<int:recipe_id>", methods=["GET"])
def get_recipe(recipe_id):
    conn = get_db_connection()

    recipe = conn.execute("""
        SELECT
            r.recipe_id,
            r.menu_id,
            r.name,
            r.instructions,
            m.name AS menu_name
        FROM recipes r
        JOIN menus m
            ON r.menu_id = m.menu_id
        WHERE r.recipe_id = ?
    """, (recipe_id,)).fetchone()

    conn.close()

    if recipe is None:
        return jsonify({
            "error": "Recipe not found"
        }), 404

    return jsonify(dict(recipe))

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

    conn = get_db_connection()

    # Check that the menu item exists
    menu = conn.execute("""
        SELECT menu_id
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    if menu is None:
        conn.close()

        return jsonify({
            "error": "Menu item not found"
        }), 404

    cursor = conn.execute("""
        INSERT INTO recipes
        (menu_id, name, instructions)
        VALUES (?, ?, ?)
    """, (
        menu_id,
        name,
        instructions
    ))

    conn.commit()

    recipe_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Recipe created successfully",
        "recipe_id": recipe_id
    }), 201

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

    conn = get_db_connection()

    existing_recipe = conn.execute("""
        SELECT *
        FROM recipes
        WHERE recipe_id = ?
    """, (recipe_id,)).fetchone()

    if existing_recipe is None:
        conn.close()

        return jsonify({
            "error": "Recipe not found"
        }), 404

    menu_id = data.get("menu_id", existing_recipe["menu_id"])
    name = data.get("name", existing_recipe["name"])
    instructions = data.get(
        "instructions",
        existing_recipe["instructions"]
    )

    # Check that the menu item exists
    menu = conn.execute("""
        SELECT menu_id
        FROM menus
        WHERE menu_id = ?
    """, (menu_id,)).fetchone()

    if menu is None:
        conn.close()

        return jsonify({
            "error": "Menu item not found"
        }), 404

    conn.execute("""
        UPDATE recipes
        SET
            menu_id = ?,
            name = ?,
            instructions = ?
        WHERE recipe_id = ?
    """, (
        menu_id,
        name,
        instructions,
        recipe_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Recipe updated successfully"
    })

# -----------------------------
# DELETE RECIPE
# -----------------------------

@app.route("/api/recipes/<int:recipe_id>", methods=["DELETE"])
def delete_recipe(recipe_id):
    conn = get_db_connection()

    recipe = conn.execute("""
        SELECT *
        FROM recipes
        WHERE recipe_id = ?
    """, (recipe_id,)).fetchone()

    if recipe is None:
        conn.close()

        return jsonify({
            "error": "Recipe not found"
        }), 404

    conn.execute("""
        DELETE FROM recipe_ingredients
        WHERE recipe_id = ?
    """, (recipe_id,))

    conn.execute("""
        DELETE FROM recipes
        WHERE recipe_id = ?
    """, (recipe_id,))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Recipe deleted successfully"
    })

# -----------------------------
# TEST ROUTE
# -----------------------------

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