RECIPES = {
    1: {"Coffee Beans": 18, "Full Cream Milk": 120},
    2: {"Coffee Beans": 18, "Full Cream Milk": 180},
    3: {"Coffee Beans": 18, "Full Cream Milk": 150},
    4: {"Coffee Beans": 18},
    5: {"Coffee Beans": 18, "Ice": 200},
    6: {"Coffee Beans": 18, "Full Cream Milk": 150, "Ice": 200},
    7: {"Coffee Beans": 18, "Full Cream Milk": 180, "Vanilla Syrup": 20},
    8: {"Coffee Beans": 18, "Full Cream Milk": 180, "Caramel Syrup": 20},
    9: {"Chocolate Powder": 25, "Full Cream Milk": 200},
    10: {"Bread": 2, "Chicken": 100, "Lettuce": 30, "Mayonnaise": 15},
    11: {"Bread": 2, "Ham": 60, "Cheese": 30, "Butter": 10},
    12: {"Bread": 2, "Avocado": 100, "Butter": 10},
    13: {"Chocolate Cake Slice": 1},
    14: {"Blueberry Muffin": 1},
    15: {"Croissant": 1},
}


def build_requirements(items):
    requirements = {}
    unknown_menu_ids = []
    for item in items:
        try:
            menu_id = int(item["menu_id"])
            quantity = int(item.get("quantity", 1))
        except (KeyError, TypeError, ValueError):
            raise ValueError("Every item requires numeric menu_id and quantity.")
        if quantity < 1:
            raise ValueError("Quantity must be at least one.")
        recipe = RECIPES.get(menu_id)
        if recipe is None:
            unknown_menu_ids.append(menu_id)
            continue
        for name, amount in recipe.items():
            requirements[name] = requirements.get(name, 0) + amount * quantity
    return requirements, unknown_menu_ids
