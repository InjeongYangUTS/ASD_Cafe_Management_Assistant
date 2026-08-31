import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "menu_recipe.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Run schema
    with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
        cursor.executescript(file.read())

    # -----------------------------
    # Menus
    # -----------------------------

    menus = [
        (1, "Cappuccino", "Coffee", "Espresso with steamed milk and foam", 5.50),
        (2, "Latte", "Coffee", "Espresso with steamed milk", 5.50),
        (3, "Flat White", "Coffee", "Espresso with smooth steamed milk", 5.50),
        (4, "Long Black", "Coffee", "Espresso with hot water", 5.00),
        (5, "Iced Long Black", "Iced Coffee", "Espresso served over cold water and ice", 5.50),
        (6, "Iced Latte", "Iced Coffee", "Espresso with cold milk and ice", 6.00),
        (7, "Vanilla Latte", "Coffee", "Latte with vanilla syrup", 6.00),
        (8, "Caramel Latte", "Coffee", "Latte with caramel syrup", 6.00),
        (9, "Hot Chocolate", "Drink", "Chocolate with steamed milk", 5.00),
        (10, "Chicken Sandwich", "Food", "Chicken, lettuce and mayonnaise sandwich", 9.50),
        (11, "Ham & Cheese Toastie", "Food", "Toasted ham and cheese sandwich", 8.50),
        (12, "Avocado Toast", "Food", "Toast with avocado and seasoning", 10.00),
        (13, "Chocolate Cake", "Dessert", "Chocolate cake slice", 7.00),
        (14, "Blueberry Muffin", "Dessert", "Blueberry muffin", 5.00),
        (15, "Croissant", "Pastry", "Butter croissant", 4.50),
    ]

    cursor.executemany(
        """
        INSERT INTO menus
        (menu_id, name, category, description, price)
        VALUES (?, ?, ?, ?, ?)
        """,
        menus
    )

    # -----------------------------
    # Recipes
    # -----------------------------

    recipes = [
        (1, 1, "Cappuccino Recipe", "Prepare espresso, steam milk and finish with milk foam."),
        (2, 2, "Latte Recipe", "Prepare espresso and combine with steamed milk."),
        (3, 3, "Flat White Recipe", "Prepare espresso and add smooth microfoam milk."),
        (4, 4, "Long Black Recipe", "Add hot water to the cup and pour espresso over it."),
        (5, 5, "Iced Long Black Recipe", "Add cold water and ice, then pour espresso over the top."),
        (6, 6, "Iced Latte Recipe", "Add ice and milk, then pour espresso over the mixture."),
        (7, 7, "Vanilla Latte Recipe", "Combine espresso, vanilla syrup and steamed milk."),
        (8, 8, "Caramel Latte Recipe", "Combine espresso, caramel syrup and steamed milk."),
        (9, 9, "Hot Chocolate Recipe", "Mix chocolate powder with steamed milk until smooth."),
        (10, 10, "Chicken Sandwich Recipe", "Layer chicken, lettuce and mayonnaise between bread slices."),
        (11, 11, "Ham & Cheese Toastie Recipe", "Place ham and cheese between bread and toast until golden."),
        (12, 12, "Avocado Toast Recipe", "Toast bread, add avocado and finish with seasoning."),
        (13, 13, "Chocolate Cake Serving", "Plate one prepared chocolate cake slice."),
        (14, 14, "Blueberry Muffin Serving", "Serve one prepared blueberry muffin."),
        (15, 15, "Croissant Serving", "Serve one prepared butter croissant."),
    ]

    cursor.executemany(
        """
        INSERT INTO recipes
        (recipe_id, menu_id, name, instructions)
        VALUES (?, ?, ?, ?)
        """,
        recipes
    )

    # -----------------------------
    # Ingredients
    # -----------------------------

    ingredients = [
        (1, "Coffee Beans", "g"),
        (2, "Full Cream Milk", "ml"),
        (3, "Ice", "g"),
        (4, "Vanilla Syrup", "ml"),
        (5, "Caramel Syrup", "ml"),
        (6, "Chocolate Powder", "g"),
        (7, "Bread", "slice"),
        (8, "Chicken", "g"),
        (9, "Lettuce", "g"),
        (10, "Mayonnaise", "g"),
        (11, "Ham", "g"),
        (12, "Cheese", "g"),
        (13, "Avocado", "g"),
        (14, "Butter", "g"),
        (15, "Chocolate Cake Slice", "slice"),
        (16, "Blueberry Muffin", "each"),
        (17, "Croissant", "each"),
    ]

    cursor.executemany(
        """
        INSERT INTO ingredients
        (ingredient_id, name, unit)
        VALUES (?, ?, ?)
        """,
        ingredients
    )

    # -----------------------------
    # Ingredient Costs
    # -----------------------------

    ingredient_costs = [
        (1, 1, 0.040),
        (2, 2, 0.003),
        (3, 3, 0.001),
        (4, 4, 0.025),
        (5, 5, 0.025),
        (6, 6, 0.030),
        (7, 7, 0.500),
        (8, 8, 0.020),
        (9, 9, 0.010),
        (10, 10, 0.015),
        (11, 11, 0.025),
        (12, 12, 0.020),
        (13, 13, 0.018),
        (14, 14, 0.020),
        (15, 15, 3.000),
        (16, 16, 2.000),
        (17, 17, 1.800),
    ]

    cursor.executemany(
        """
        INSERT INTO ingredient_costs
        (id, ingredient_id, unit_cost)
        VALUES (?, ?, ?)
        """,
        ingredient_costs
    )

    # -----------------------------
    # Recipe Ingredients
    # -----------------------------

    recipe_ingredients = [
        # Cappuccino
        (1, 1, 1, 18, "g"),
        (2, 1, 2, 180, "ml"),

        # Latte
        (3, 2, 1, 18, "g"),
        (4, 2, 2, 220, "ml"),

        # Flat White
        (5, 3, 1, 18, "g"),
        (6, 3, 2, 180, "ml"),

        # Long Black
        (7, 4, 1, 18, "g"),

        # Iced Long Black
        (8, 5, 1, 18, "g"),
        (9, 5, 3, 100, "g"),

        # Iced Latte
        (10, 6, 1, 18, "g"),
        (11, 6, 2, 220, "ml"),
        (12, 6, 3, 100, "g"),

        # Vanilla Latte
        (13, 7, 1, 18, "g"),
        (14, 7, 2, 220, "ml"),
        (15, 7, 4, 20, "ml"),

        # Caramel Latte
        (16, 8, 1, 18, "g"),
        (17, 8, 2, 220, "ml"),
        (18, 8, 5, 20, "ml"),

        # Hot Chocolate
        (19, 9, 6, 25, "g"),
        (20, 9, 2, 220, "ml"),

        # Chicken Sandwich
        (21, 10, 7, 2, "slice"),
        (22, 10, 8, 100, "g"),
        (23, 10, 9, 30, "g"),
        (24, 10, 10, 20, "g"),

        # Ham & Cheese Toastie
        (25, 11, 7, 2, "slice"),
        (26, 11, 11, 60, "g"),
        (27, 11, 12, 40, "g"),
        (28, 11, 14, 10, "g"),

        # Avocado Toast
        (29, 12, 7, 2, "slice"),
        (30, 12, 13, 100, "g"),

        # Chocolate Cake
        (31, 13, 15, 1, "slice"),

        # Blueberry Muffin
        (32, 14, 16, 1, "each"),

        # Croissant
        (33, 15, 17, 1, "each"),
    ]

    cursor.executemany(
        """
        INSERT INTO recipe_ingredients
        (id, recipe_id, ingredient_id, quantity, unit)
        VALUES (?, ?, ?, ?, ?)
        """,
        recipe_ingredients
    )

    conn.commit()
    conn.close()

    print("Student 2 database created successfully.")
    print(f"Database location: {DB_PATH}")


if __name__ == "__main__":
    setup_database()