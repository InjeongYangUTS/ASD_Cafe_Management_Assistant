from adapters.student2_adapter import (
    Student2AdapterError,
    get_ingredient as adapter_get_ingredient,
    get_ingredients as adapter_get_ingredients,
    get_menu as adapter_get_menu,
    get_menu_price as adapter_get_menu_price,
    get_menus as adapter_get_menus,
    get_recipe as adapter_get_recipe,
    get_recipe_ingredients as adapter_get_recipe_ingredients,
    get_recipes as adapter_get_recipes,
)


def register_student2_tools(mcp):

    @mcp.tool()
    def get_menus() -> dict:
        """
        Return all menu items from Student 2 Menu & Recipe Management.

        Read-only tool.
        """
        try:
            menus = adapter_get_menus()

            return {
                "success": True,
                "menus": menus,
                "count": len(menus),
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_menu(menu_id: int) -> dict:
        """
        Return one menu item by its positive integer ID.

        Read-only tool.
        """
        if menu_id < 1:
            return {
                "success": False,
                "error": "menu_id must be a positive integer.",
            }

        try:
            menu = adapter_get_menu(menu_id)

            return {
                "success": True,
                "menu": menu,
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_menu_price(menu_id: int) -> dict:
        """
        Return the price information for one menu item.

        Read-only tool.
        """
        if menu_id < 1:
            return {
                "success": False,
                "error": "menu_id must be a positive integer.",
            }

        try:
            price = adapter_get_menu_price(menu_id)

            return {
                "success": True,
                "price": price,
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_ingredients() -> dict:
        """
        Return all ingredients from Student 2 Menu & Recipe Management.

        Read-only tool.
        """
        try:
            ingredients = adapter_get_ingredients()

            return {
                "success": True,
                "ingredients": ingredients,
                "count": len(ingredients),
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_ingredient(ingredient_id: int) -> dict:
        """
        Return one ingredient by its positive integer ID.

        Read-only tool.
        """
        if ingredient_id < 1:
            return {
                "success": False,
                "error": "ingredient_id must be a positive integer.",
            }

        try:
            ingredient = adapter_get_ingredient(ingredient_id)

            return {
                "success": True,
                "ingredient": ingredient,
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_recipes() -> dict:
        """
        Return all recipes from Student 2 Menu & Recipe Management.

        Read-only tool.
        """
        try:
            recipes = adapter_get_recipes()

            return {
                "success": True,
                "recipes": recipes,
                "count": len(recipes),
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_recipe(recipe_id: int) -> dict:
        """
        Return one recipe by its positive integer ID.

        Read-only tool.
        """
        if recipe_id < 1:
            return {
                "success": False,
                "error": "recipe_id must be a positive integer.",
            }

        try:
            recipe = adapter_get_recipe(recipe_id)

            return {
                "success": True,
                "recipe": recipe,
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }

    @mcp.tool()
    def get_recipe_ingredients(recipe_id: int) -> dict:
        """
        Return the ingredients assigned to one recipe.

        Read-only tool.
        """
        if recipe_id < 1:
            return {
                "success": False,
                "error": "recipe_id must be a positive integer.",
            }

        try:
            ingredients = adapter_get_recipe_ingredients(recipe_id)

            return {
                "success": True,
                "ingredients": ingredients,
            }

        except Student2AdapterError as exc:
            return {
                "success": False,
                "error": exc.message,
            }