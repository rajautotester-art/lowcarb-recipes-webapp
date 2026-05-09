from pathlib import Path
import re
from typing import Any

import pandas as pd


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "recipes.parquet"
STOP_WORDS = {
    "a",
    "about",
    "and",
    "any",
    "are",
    "can",
    "do",
    "eggless",
    "for",
    "give",
    "have",
    "i",
    "indian",
    "is",
    "low",
    "lowcarb",
    "me",
    "need",
    "of",
    "recipe",
    "recipes",
    "show",
    "the",
    "to",
    "want",
    "with",
}
STRICT_FOOD_TERMS = {
    "almond",
    "badam",
    "barfi",
    "bread",
    "cake",
    "cheese",
    "coconut",
    "cookie",
    "cookies",
    "dosa",
    "garlic",
    "kaju",
    "maddur",
    "mixture",
    "paneer",
    "panner",
    "papdi",
    "pecan",
    "pistachio",
    "seed",
    "vada",
}


def _normalize(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value).lower()
    if hasattr(value, "tolist") and not isinstance(value, str):
        return _normalize(value.tolist())
    if value is None or pd.isna(value):
        return ""
    return str(value).lower()


def load_recipes() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    return pd.read_parquet(DATA_PATH)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return [_to_jsonable(record) for record in df.fillna("").to_dict(orient="records")]


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "tolist") and not isinstance(value, str):
        return _to_jsonable(value.tolist())
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, float) and value != value:
        return None
    return value


def get_all_recipes() -> list[dict[str, Any]]:
    return _records(load_recipes())


def search_recipes(query: str) -> list[dict[str, Any]]:
    df = load_recipes()
    if df.empty:
        return []

    q = query.strip().lower()
    if not q:
        return _records(df)

    searchable_cols = ["recipe_name", "ingredients", "tags", "notes", "macros"]
    mask = pd.Series(False, index=df.index)
    for col in searchable_cols:
        if col in df.columns:
            mask = mask | df[col].apply(lambda value: q in _normalize(value))

    return _records(df[mask])


def _query_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [token for token in tokens if len(token) > 2 and token not in STOP_WORDS]


def _recipe_text(recipe: pd.Series) -> str:
    fields = ["recipe_name", "ingredients", "tags", "notes", "macros", "bot_keywords"]
    return " ".join(_normalize(recipe.get(field, "")) for field in fields)


def _rank_recipes(query: str, strict: bool = False) -> list[dict[str, Any]]:
    df = load_recipes()
    if df.empty:
        return []

    tokens = _query_tokens(query)
    if not tokens:
        return _records(df)

    scored: list[tuple[int, int, Any]] = []
    for index, row in df.iterrows():
        name = _normalize(row.get("recipe_name", ""))
        ingredients = _normalize(row.get("ingredients", ""))
        tags = _normalize(row.get("tags", ""))
        notes = _normalize(row.get("notes", ""))
        searchable = _recipe_text(row)
        strict_searchable = f"{name} {ingredients}"
        match_text = strict_searchable if strict else searchable
        matched_tokens = [token for token in tokens if token in match_text]

        if strict and len(matched_tokens) != len(tokens):
            continue
        if not matched_tokens:
            continue

        score = 0
        for token in matched_tokens:
            if token in name:
                score += 5
            if token in ingredients:
                score += 4
            if token in tags:
                score += 3
            if token in notes:
                score += 1
        scored.append((score, len(matched_tokens), index))

    scored.sort(reverse=True)
    return _records(df.loc[[index for _, _, index in scored]])


def get_recipe_by_id(recipe_id: str) -> dict[str, Any] | None:
    df = load_recipes()
    if df.empty or "recipe_id" not in df.columns:
        return None
    matches = df[df["recipe_id"] == recipe_id]
    if matches.empty:
        return None
    return _records(matches)[0]


def chat_response(message: str) -> dict[str, Any]:
    text = message.strip().lower()
    if not text:
        return {
            "reply": "Tell me what you want to cook, like travel snacks, dosa, bread, cake, or a high-protein low-carb meal.",
            "recipes": [],
        }

    intent_terms = {
        "travel snacks": ["travel", "snack", "portable", "lunchbox"],
        "protein": ["protein", "paneer", "tofu", "greek yogurt", "chia"],
        "low carb": ["low carb", "keto", "diabetic", "almond flour", "coconut flour"],
        "bread": ["bread", "roti", "wrap", "bun"],
        "dosa": ["dosa", "chilla", "uttapam"],
        "cake": ["cake", "dessert", "sweet", "muffin"],
        "breakfast": ["breakfast", "morning", "quick"],
    }

    tokens = _query_tokens(text)
    strict_terms = [token for token in tokens if token in STRICT_FOOD_TERMS]
    queries = [text]
    matched_intents = []
    for label, terms in intent_terms.items():
        if any(term in text for term in terms):
            matched_intents.append(label)
            if not strict_terms:
                queries.extend(terms)

    seen = set()
    recipes: list[dict[str, Any]] = []
    if strict_terms:
        candidates = _rank_recipes(" ".join(strict_terms), strict=True)
    else:
        candidates = []
        for query in queries:
            candidates.extend(_rank_recipes(query))

    for recipe in candidates:
        recipe_id = recipe["recipe_id"]
        if recipe_id not in seen:
            seen.add(recipe_id)
            recipes.append(recipe)

    if not strict_terms and not recipes:
        for query in queries:
            for recipe in search_recipes(query):
                recipe_id = recipe["recipe_id"]
                if recipe_id not in seen:
                    seen.add(recipe_id)
                    recipes.append(recipe)

    recipes = recipes[:5]

    if recipes:
        names = ", ".join(recipe["recipe_name"] for recipe in recipes[:3])
        focus = f" for {', '.join(matched_intents)}" if matched_intents else ""
        reply = (
            f"I found {len(recipes)} eggless low-carb Indian recipe ideas{focus}: {names}. "
            "Check the notes and macros before choosing. For travel, prefer dry, sturdy recipes and pack chutneys separately."
        )
    else:
        searched_for = f" matching {', '.join(strict_terms)}" if strict_terms else ""
        reply = (
            f"I did not find a close recipe{searched_for}. Try asking for something like low-carb dosa, travel snacks, "
            "high-protein dinner, almond-flour bread, or eggless cake."
        )

    return {"reply": reply, "recipes": recipes}
