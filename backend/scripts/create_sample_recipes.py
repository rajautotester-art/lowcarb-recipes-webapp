from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_PATH = DATA_DIR / "recipes.parquet"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    recipes = [
        {
            "recipe_id": "r001",
            "recipe_name": "Almond Flour Masala Dosa",
            "category": "Breakfast",
            "ingredients": ["almond flour", "coconut flour", "curd", "ginger", "green chili", "cumin"],
            "tags": ["eggless", "low carb", "dosa", "south indian", "breakfast"],
            "macros": "Approx 7g net carbs, 11g protein per serving",
            "notes": "Rest batter for 10 minutes. Cook small dosas on medium heat so they hold shape.",
        },
        {
            "recipe_id": "r002",
            "recipe_name": "Paneer Methi Travel Crackers",
            "category": "Snack",
            "ingredients": ["paneer", "almond flour", "methi", "ajwain", "sesame", "ghee"],
            "tags": ["eggless", "travel snacks", "protein", "crackers", "portable"],
            "macros": "Approx 4g net carbs, 13g protein per serving",
            "notes": "Bake until fully dry. Carry in an airtight box. Good with dry chutney powder.",
        },
        {
            "recipe_id": "r003",
            "recipe_name": "Cauliflower Paneer Upma",
            "category": "Breakfast",
            "ingredients": ["cauliflower rice", "paneer", "mustard seeds", "curry leaves", "peanuts"],
            "tags": ["eggless", "low carb", "protein", "breakfast", "quick"],
            "macros": "Approx 8g net carbs, 16g protein per serving",
            "notes": "Squeeze moisture from cauliflower for a fluffy texture.",
        },
        {
            "recipe_id": "r004",
            "recipe_name": "Coconut Flour Mini Bread",
            "category": "Bread",
            "ingredients": ["coconut flour", "psyllium husk", "curd", "baking powder", "butter"],
            "tags": ["eggless", "low carb", "bread", "sandwich", "travel"],
            "macros": "Approx 5g net carbs, 8g protein per slice",
            "notes": "Let it cool fully before slicing. Toast for better texture.",
        },
        {
            "recipe_id": "r005",
            "recipe_name": "Besan Tofu Chilla",
            "category": "Breakfast",
            "ingredients": ["besan", "tofu", "spinach", "carom seeds", "turmeric", "green chili"],
            "tags": ["eggless", "protein", "chilla", "dosa", "savory"],
            "macros": "Approx 12g net carbs, 18g protein per serving",
            "notes": "Use less besan and more tofu puree for a lower-carb version.",
        },
        {
            "recipe_id": "r006",
            "recipe_name": "Eggless Almond Cardamom Mug Cake",
            "category": "Dessert",
            "ingredients": ["almond flour", "greek yogurt", "cardamom", "erythritol", "baking powder"],
            "tags": ["eggless", "low carb", "cake", "dessert", "sweet"],
            "macros": "Approx 6g net carbs, 12g protein per serving",
            "notes": "Microwave in short bursts. Add saffron or rose essence for Indian dessert flavor.",
        },
        {
            "recipe_id": "r007",
            "recipe_name": "Keto Cabbage Thepla",
            "category": "Travel",
            "ingredients": ["cabbage", "almond flour", "flax meal", "methi", "curd", "spices"],
            "tags": ["eggless", "travel snacks", "low carb", "thepla", "roti"],
            "macros": "Approx 6g net carbs, 10g protein per thepla",
            "notes": "Cook with minimal moisture for travel. Pack with pickle or dry chutney.",
        },
    ]

    df = pd.DataFrame(recipes)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} recipes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
