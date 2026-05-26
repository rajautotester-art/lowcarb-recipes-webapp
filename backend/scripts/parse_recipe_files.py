from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BACKEND_DIR / "data" / "raw"
TEXT_DIR = RAW_DIR / "text"
PDF_DIR = RAW_DIR / "pdf"
IMAGE_DIR = RAW_DIR / "images"
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"
OUTPUT_PATH = BACKEND_DIR / "data" / "recipes.parquet"
ANNOTATIONS_PATH = PROCESSED_DIR / "recipe_annotations.json"

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_TABLE_EXTENSIONS = {".csv"}


KEYWORD_TAGS = {
    "travel snacks": ["travel", "snack", "portable", "lunchbox", "thepla", "cracker"],
    "protein": ["protein", "paneer", "tofu", "greek yogurt", "hung curd", "chia", "peanut"],
    "low carb": ["low carb", "keto", "diabetic", "almond flour", "coconut flour", "psyllium", "cauliflower"],
    "bread": ["bread", "bun", "sandwich", "toast"],
    "dosa": ["dosa", "chilla", "uttapam"],
    "cake": ["cake", "muffin", "dessert", "sweet"],
    "breakfast": ["breakfast", "upma", "poha", "chilla", "dosa"],
    "eggless": ["eggless", "no egg", "without egg"],
    "indian": ["masala", "methi", "paneer", "thepla", "dosa", "chilla", "curry leaves"],
}

MACRO_PATTERNS = {
    "net_carbs_g": r"(?P<value>\d+(?:\.\d+)?)\s*(?:g|grams)?\s*(?:net\s*)?carbs?",
    "protein_g": r"(?P<value>\d+(?:\.\d+)?)\s*(?:g|grams)?\s*protein",
    "fat_g": r"(?P<value>\d+(?:\.\d+)?)\s*(?:g|grams)?\s*fat",
    "calories": r"(?P<value>\d+(?:\.\d+)?)\s*(?:cal|calories|kcal)",
}

KNOWN_INGREDIENTS = [
    "almond flour",
    "coconut flour",
    "cashew flour",
    "flaxseed",
    "flax meal",
    "psyllium",
    "paneer",
    "tofu",
    "mozzarella",
    "cream cheese",
    "parmesan",
    "ghee",
    "butter",
    "curd",
    "greek yogurt",
    "yogurt",
    "peanut",
    "pecan",
    "pistachio",
    "sesame",
    "coconut",
    "cardamom",
    "cinnamon",
    "garlic",
    "methi",
    "ajwain",
    "erythritol",
    "monk fruit",
    "stevia",
]

TEXT_REPLACEMENTS = {
    "\u00e2\u0080\u0093": "-",
    "\u00e2\u0080\u0094": "-",
    "\u00e2\u0080\u00a2": "\n",
    "\u00e2\u0080\u009c": '"',
    "\u00e2\u0080\u009d": '"',
    "\u00e2\u0080\u0098": "'",
    "\u00e2\u0080\u0099": "'",
    "\u00c2\u00bc": "1/4",
    "\u00c2\u00bd": "1/2",
    "\u00c2\u00be": "3/4",
    "â": "-",
    "â": "-",
    "â¢": "\n",
    "â– ": "\n",
    "â ": "\n",
    "Â½": "1/2",
    "Â¼": "1/4",
    "Â¾": "3/4",
    "â": "1/3",
    "â": "2/3",
    "â": "1/8",
    "â": "3/8",
    "â": "5/8",
    "â": "7/8",
    "â": '"',
    "â": '"',
    "â": "'",
    "â": "'",
}


def stable_id(source: str, name: str) -> str:
    raw = f"{source}:{name}".encode("utf-8")
    return "r_" + hashlib.sha1(raw).hexdigest()[:10]


def normalize_extracted_text(text: str) -> str:
    for bad, good in TEXT_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_extracted_text(text)).strip()


def split_recipe_blocks(text: str) -> list[str]:
    parts = re.split(r"\n\s*---+\s*\n|\n\s*Recipe\s*:\s*", text, flags=re.IGNORECASE)
    skipped_headings = (
        "flavor variations",
        "ingredients",
        "ingredients (for 1 batch)",
        "method",
        "texture tips",
        "variations",
    )
    blocks = []
    for part in parts:
        block = part.strip()
        if not block:
            continue
        title = clean_recipe_name(block.splitlines()[0].strip("# "))
        if title.lower() in skipped_headings:
            continue
        blocks.append(block)
    return blocks


def first_nonempty_line(block: str, fallback: str) -> str:
    for line in block.splitlines():
        cleaned = clean_recipe_name(line.strip().strip("#:- "))
        if cleaned:
            return cleaned
    return fallback


def clean_recipe_name(value: str) -> str:
    value = normalize_extracted_text(value)
    value = value.replace("\x7f", " ").replace("■", " ").strip()
    value = value.replace("*", " ")
    value = re.sub(r"^#+\s*", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^\d+[\.)]\s*", "", value)
    value = re.split(r"\s{2,}| Dry:| Wet:| Ingredients?:| Method:| Instructions?:", value, maxsplit=1)[0]
    value = re.sub(r"\b\d{6}[\s_-]+\d{6}\b", "", value)
    value = re.sub(r"\s+", " ", value).strip(" -:|")
    return value[:120].strip()


def title_from_block(block: str, fallback: str) -> str:
    marker = re.compile(
        r"^(ingredients?|base dough ingredients|ingredient|instructions?|method|base method|makes|notes|tips)\b",
        re.IGNORECASE,
    )
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return fallback

    title_parts = [lines[0]]
    for line in lines[1:3]:
        if marker.match(line):
            break
        current = " ".join(title_parts).strip()
        needs_continuation = (
            current.endswith((",", "&", "/", "("))
            or current.count("(") > current.count(")")
            or current.lower().endswith("sautéed")
        )
        if not needs_continuation:
            break
        title_parts.append(line)

    return clean_recipe_name(" ".join(title_parts))


def extract_section(block: str, names: list[str]) -> str:
    joined_names = "|".join(re.escape(name) for name in names)
    pattern = rf"(?is)(?:^|\n)\s*(?:{joined_names})\s*:?\s*(.*?)(?=\n\s*[A-Z][A-Za-z ]{{2,}}:\s*|\Z)"
    match = re.search(pattern, block)
    return normalize_text(match.group(1)) if match else ""


def extract_major_section(block: str, names: list[str], stop_names: list[str]) -> str:
    joined_names = "|".join(re.escape(name) for name in names)
    joined_stops = "|".join(re.escape(name) for name in stop_names)
    pattern = rf"(?is)(?:^|\n)\s*(?:{joined_names})\b[^\n]*:?\s*\n?(.*?)(?=\n\s*(?:{joined_stops})\b[^\n]*\n|\Z)"
    match = re.search(pattern, block)
    return match.group(1).strip() if match else ""


def split_ingredient_and_method_text(block: str, recipe_name: str) -> tuple[str, str]:
    block = normalize_extracted_text(block)
    text = block.replace("\x7f", "\n").replace("■", "\n").replace("•", "\n")
    text = re.sub(re.escape(recipe_name), "", text, count=1, flags=re.IGNORECASE).strip()

    method_marker = re.search(
        r"(?im)^\s*(instructions?|method|directions?|steps?|preparation(?:\s+steps)?)\s*:?\s*$",
        text,
    )
    if method_marker:
        ingredients_part = text[: method_marker.start()]
        method_part = text[method_marker.end() :]
        ingredient_heading = re.search(
            r"(?im)^\s*(ingredients?|base ingredients|main ingredients|classic vegetarian version|vegan alternative version|base dough(?: ingredients)?|dry ingredients|dry(?: mix)?|wet ingredients|wet(?: / binding ingredients)?)\s*:?\s*$",
            ingredients_part,
        )
        if ingredient_heading:
            ingredients_part = ingredients_part[ingredient_heading.start() :]
        return ingredients_part.strip(), normalize_text(method_part)

    numbered_step = re.search(r"(?s)(?:^|\n)\s*1[\.\)]\s+", text)
    if numbered_step:
        ingredients_part = text[: numbered_step.start()]
        method_part = text[numbered_step.start() :]
        return ingredients_part.strip(), normalize_text(method_part)

    return normalize_text(text), ""


def extract_listish(value: str) -> list[str]:
    if not value:
        return []
    value = normalize_extracted_text(value)
    value = value.replace("\x7f", "\n").replace("■", "\n").replace("•", "\n")
    pieces = re.split(r",|\n|;|- ", value)
    cleaned = []
    for piece in pieces:
        item = piece.strip().lower()
        if not item or item in {":", "-"}:
            continue
        if item.endswith(":") and not re.search(r"\d", item):
            continue
        if re.match(r"^(instructions?|method|directions?|steps?|preparation)\b", item):
            continue
        cleaned.append(item)
    return cleaned


def section_lines_as_numbered_steps(value: str) -> str:
    lines = extract_listish(value)
    return " ".join(f"{index + 1} {line[:1].upper()}{line[1:]}" for index, line in enumerate(lines))


def split_quantity_item(value: str) -> dict[str, str]:
    item = normalize_text(value).strip(" -:;")
    item = re.sub(r"\s*\|\s*", " | ", item)
    match = re.match(r"^(?P<name>.+?)\s+[–—-]\s+(?P<amount>.+)$", item)
    if match:
        return {"item": match.group("name").strip(), "amount": match.group("amount").strip()}
    measure = re.search(
        r"(?P<amount>\d+(?:\.\d+)?\s*(?:/\s*\d+)?|\d+/\d+|[¼½¾⅓⅔⅛⅜⅝⅞])\s*(?:to\s*)?(?:[¼½¾⅓⅔⅛⅜⅝⅞]|\d+(?:\.\d+)?|\d+/\d+)?\s*(?:cup|cups|tbsp|tsp|g|grams?|ml|pinch|pinches|spray|drops?)?\\b.*",
        item,
        flags=re.IGNORECASE,
    )
    if measure and measure.start() > 0:
        return {"item": item[: measure.start()].strip(" -:;"), "amount": item[measure.start() :].strip()}
    return {"item": item, "amount": ""}


def looks_like_quantity(value: str) -> bool:
    value = normalize_text(value).strip()
    if not value:
        return False
    quantity_chars = r"Â¼Â½Â¾â…“â…”â…›â…œâ…â…ž¼½¾⅓⅔⅛⅜⅝⅞"
    lowered = value.lower()
    if lowered in {"to taste", "as needed"}:
        return True
    if re.match(rf"^[{quantity_chars}\d/]", value) and "as needed" in lowered:
        return True
    return bool(
        re.match(
            rf"^(?:[{quantity_chars}]|\d+(?:\.\d+)?|\d+/\d+)\s*(?:[{quantity_chars}]|\d+(?:\.\d+)?|\d+/\d+)?\s*(?:cup|cups|tbsp|tsp|g|grams?|ml|pinch|pinches|spray|drops?)?(?:\s*\([^)]*\))?(?:\s*(?:\+|to|–|-)\s*(?:[{quantity_chars}]|\d+(?:\.\d+)?|\d+/\d+)\s*(?:cup|cups|tbsp|tsp|g|grams?|ml|pinch|pinches|spray|drops?)?)?(?:\s+as needed)?$",
            value,
            flags=re.IGNORECASE,
        )
    )


def extract_ingredient_groups(value: str, recipe_name: str) -> list[dict[str, Any]]:
    if not value:
        return []
    text = normalize_extracted_text(value).replace("\x7f", "\n").replace("â– ", "\n").replace("â€¢", "\n")
    text = re.sub(re.escape(recipe_name), "", text, count=1, flags=re.IGNORECASE)
    heading_pattern = re.compile(
        r"^(?:base ingredients|main ingredients|dry ingredients|wet ingredients|yeast activation support|toppings|optional|spice mix|optional flavor additions|classic vegetarian version|vegan alternative version|flavor boosters|low-carb tweaks|base dough(?: ingredients)?(?:\s*\(.+\))?|dry(?: mix)?|wet(?: / binding ingredients)?|add-ins?(?: \\(after baking\\))?|cinnamon .*coating|variation\\s+\\d+\\s*:.+|classic onion akki rotti:?|carrot akki rotti:?|cabbage akki rotti:?|bottle gourd .*akki rotti:?|methi / dill akki rotti:?|onion & vegetable add-in variations.*|base technique.*)$",
        re.IGNORECASE,
    )
    skip_pattern = re.compile(
        r"^(?:amount|ingredients?|method|instructions?|notes?|estimated nutrition|nutrition|macros|rice-free|all variations below|includes\\b|use the same\\b)",
        re.IGNORECASE,
    )
    groups: list[dict[str, Any]] = []
    current = {"section": "Ingredients", "items": []}
    pending_item = ""

    def push_current() -> None:
        nonlocal current, pending_item
        if pending_item:
            current["items"].append({"item": pending_item, "amount": ""})
            pending_item = ""
        if current["items"]:
            groups.append(current)
        current = {"section": "Ingredients", "items": []}

    for raw_line in text.splitlines():
        line = normalize_text(raw_line)
        if not line:
            continue
        line = line.strip(" -:;")
        if not line or skip_pattern.match(line):
            pending_item = ""
            continue
        variation_inline = re.search(
            r"(?i)\b(variation\s+\d+\s*:.+?)(?=\s+[A-Z][A-Za-z /()]+\s+[–—-]\s+|$)",
            line,
        )
        if variation_inline:
            before = line[: variation_inline.start()].strip(" -:;")
            if before and (re.search(r"\d|[¼½¾⅓⅔⅛⅜⅝⅞]", before) or "optional" in before.lower()):
                for piece in re.split(r"\s+\|\s+", before):
                    item = split_quantity_item(piece)
                    if item["item"]:
                        current["items"].append(item)
            push_current()
            current = {"section": variation_inline.group(1).rstrip(":"), "items": []}
            line = line[variation_inline.end() :].strip(" -:;")
            if not line:
                continue
        if heading_pattern.match(line):
            push_current()
            current = {"section": line.rstrip(":"), "items": []}
            continue
        if looks_like_quantity(line) and pending_item:
            current["items"].append({"item": pending_item, "amount": line})
            pending_item = ""
            continue
        if re.search(r"\d|[¼½¾⅓⅔⅛⅜⅝⅞]", line) or "optional" in line.lower():
            if pending_item:
                current["items"].append({"item": pending_item, "amount": ""})
                pending_item = ""
            for piece in re.split(r"\s+\|\s+", line):
                item = split_quantity_item(piece)
                if item["item"]:
                    current["items"].append(item)
        if not (re.search(r"\d|[Â¼Â½Â¾â…“â…”â…›â…œâ…â…ž]", line) or "optional" in line.lower()) and not re.search(r"[.!?]$", line):
            if pending_item:
                current["items"].append({"item": pending_item, "amount": ""})
            pending_item = line

    push_current()
    return groups


def extract_steps(value: str) -> list[str]:
    if not value:
        return []
    value = normalize_extracted_text(value)
    value = re.split(r"\b(?:approximate\s+)?macros?\b|\bnutrition\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = value.replace("\x7f", "\n").replace("●", "\n")
    value = normalize_text(value.replace("\x7f", " ").replace("■", " "))
    heading_patterns = [
        r"buns?\s*/\s*rolls?",
        r"flatbread\s*/\s*pita\s+adaptation",
        r"base\s+method",
        r"method",
        r"instructions?",
        r"directions?",
        r"optional\s+variations?",
        r"tips?\s*&\s*variations?",
        r"notes?",
    ]
    value = re.sub(r"(?i)\b(variation\s+\d+\s*:)", r"\n\1", value)
    for pattern in heading_patterns:
        value = re.sub(rf"(?i)\b({pattern})\b", r"\n\1\n", value)
    value = re.sub(r"\s+(?=\d+[\.\)]?\s+[A-Z])", "\n", value)
    value = re.sub(r"\s+[–—]\s+(?=[A-Z])", "\n", value)
    value = re.sub(
        r"\s+(?=(?:Substitution Options|Saffron-Pistachio|Thandai|Mocha|Chocolate|Cardamom|Storage|Bake instead)\b)",
        "\n",
        value,
    )
    parts = re.split(r"\n+|\s+(?=\d+[\.\)]\s+)", value)
    steps = []
    for part in parts:
        step = re.sub(r"^\d+[\.\)]?\s*", "", part).strip(" -:;")
        step = re.sub(r"\s+\d+$", "", step).strip()
        if step and step not in {"-", "–", "—"}:
            if len(step) > 320:
                steps.extend(
                    sentence.strip()
                    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", step)
                    if sentence.strip()
                )
            else:
                steps.append(step)
    return steps or [value]


def title_from_filename(path: Path) -> str:
    name = path.stem
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\b(fixed|updated|v2)\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def infer_ingredients(text: str) -> list[str]:
    lowered = text.lower()
    return [ingredient for ingredient in KNOWN_INGREDIENTS if ingredient in lowered]


def infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = []
    for tag, terms in KEYWORD_TAGS.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered) for term in terms):
            tags.append(tag)
    return sorted(set(tags))


def infer_macros(text: str) -> dict[str, float | None]:
    macros: dict[str, float | None] = {key: None for key in MACRO_PATTERNS}
    lowered = text.lower()
    for key, pattern in MACRO_PATTERNS.items():
        match = re.search(pattern, lowered)
        if match:
            macros[key] = float(match.group("value"))
    return macros


def infer_category(tags: list[str], text: str) -> str:
    lowered = text.lower()
    if (
        "nut seed mixture" in lowered
        or "southindian nut seed mixture" in lowered
        or ("south indian" in lowered and "nut" in lowered and "seed" in lowered)
    ):
        return "General"
    if any(term in lowered for term in ["cookie", "cookies", "donut", "donuts", "barfi", "danish butter", "cheesecake"]):
        return "Dessert"
    if any(term in lowered for term in ["toffee", "payasam", "biscotti"]):
        return "Dessert"
    if any(term in lowered for term in ["bun", "buns", "loaf", "bread", "focaccia", "bagel"]):
        return "Bread"
    if "cake" in tags:
        return "Dessert"
    if any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered) for term in ["sauce", "chutney", "dip", "dips", "masala", "podi"]):
        return "General"
    if "travel snacks" in tags:
        return "Travel"
    if "bread" in tags:
        return "Bread"
    if "breakfast" in tags or "dosa" in tags:
        return "Breakfast"
    if any(term in lowered for term in ["snack", "cracker", "chips"]):
        return "Snack"
    return "General"


def build_annotations(tags: list[str], macros: dict[str, float | None], text: str) -> dict[str, Any]:
    net_carbs = macros.get("net_carbs_g")
    protein = macros.get("protein_g")
    annotations = {
        "is_eggless": "eggless" in tags or "egg" not in text.lower(),
        "is_low_carb": "low carb" in tags or (net_carbs is not None and net_carbs <= 12),
        "is_high_protein": "protein" in tags or (protein is not None and protein >= 12),
        "is_travel_friendly": "travel snacks" in tags,
        "meal_use_cases": tags,
        "bot_keywords": sorted(set(tags + extract_listish(text)[:20])),
    }
    return annotations


def parse_text_block(block: str, source_file: Path, index: int) -> dict[str, Any]:
    fallback_name = f"{source_file.stem} {index + 1}".strip()
    if source_file.suffix.lower() == ".pdf":
        name = title_from_block(block, title_from_filename(source_file))
    else:
        name = extract_section(block, ["recipe_name", "name", "title"]) or first_nonempty_line(block, fallback_name)
    name = clean_recipe_name(name)
    ingredient_stop_names = ["instructions", "method", "directions", "steps", "preparation", "notes", "macros", "nutrition"]
    ingredients_raw = extract_major_section(
        block,
        ["ingredients", "ingredient"],
        ingredient_stop_names,
    )
    if not ingredients_raw:
        ingredients_raw = extract_major_section(
            block,
            ["base technique", "base dough", "variation 1"],
            ["notes", "instructions", "method", "directions", "steps", "preparation", "macros", "nutrition"],
        )
    base_technique = extract_major_section(
        block,
        ["base technique"],
        ["variation 1", "ingredients", "notes", "instructions", "method", "directions", "steps", "preparation", "macros", "nutrition"],
    )
    method_text = extract_major_section(
        block,
        ["method", "base method", "instructions", "directions", "steps", "preparation"],
        ["estimated nutrition", "nutrition", "macros"],
    )
    note_text = extract_section(block, ["notes", "note"])
    notes = method_text or section_lines_as_numbered_steps(base_technique) or note_text
    if not ingredients_raw or not notes:
        inferred_ingredients, inferred_notes = split_ingredient_and_method_text(block, name)
        ingredients_raw = ingredients_raw or inferred_ingredients
        notes = notes or inferred_notes
    if ingredients_raw:
        cleaned_ingredients, embedded_notes = split_ingredient_and_method_text(ingredients_raw, name)
        if embedded_notes:
            ingredients_raw = cleaned_ingredients
            notes = notes or embedded_notes
    notes = notes or normalize_text(block[:500])
    macros_text = extract_section(block, ["macros", "nutrition"])

    full_text = normalize_text(f"{name} {ingredients_raw} {notes} {macros_text} {block}")
    tag_text = normalize_text(f"{name} {ingredients_raw} {macros_text}")
    ingredient_groups = extract_ingredient_groups(ingredients_raw, name)
    grouped_ingredients = [
        f"{item['item']} - {item['amount']}" if item.get("amount") else item["item"]
        for group in ingredient_groups
        for item in group["items"]
    ]
    ingredients = grouped_ingredients or extract_listish(ingredients_raw) or infer_ingredients(full_text)
    tags = infer_tags(tag_text)
    macros = infer_macros(full_text)
    category = infer_category(tags, tag_text)
    annotations = build_annotations(tags, macros, full_text)

    return {
        "recipe_id": stable_id(str(source_file), name),
        "recipe_name": name,
        "category": category,
        "ingredients": ingredients,
        "ingredient_groups": ingredient_groups,
        "tags": tags,
        "macros": macros_text or ", ".join(f"{k}: {v}" for k, v in macros.items() if v is not None),
        "notes": notes,
        "method_steps": extract_steps(notes),
        "source_file": str(source_file),
        "source_type": source_file.suffix.lower().lstrip("."),
        "raw_text": full_text,
        **macros,
        **annotations,
    }


def parse_text_file(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [parse_text_block(block, path, index) for index, block in enumerate(split_recipe_blocks(text))]


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    page_text = []
    for page in reader.pages:
        page_text.append(page.extract_text() or "")
    return normalize_extracted_text("\n".join(page_text)).strip()


def parse_pdf_file(path: Path) -> list[dict[str, Any]]:
    text = extract_pdf_text(path)
    if not text:
        return [unsupported_placeholder(path, "pdf")]

    blocks = split_recipe_blocks(text)
    if len(blocks) == 1:
        return [parse_text_block(text, path, 0)]
    return [parse_text_block(block, path, index) for index, block in enumerate(blocks)]


def parse_csv_file(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            block = "\n".join(f"{key}: {value}" for key, value in row.items() if value)
            rows.append(parse_text_block(block, path, index))
    return rows


def unsupported_placeholder(path: Path, source_type: str) -> dict[str, Any]:
    name = path.stem.replace("_", " ").replace("-", " ").title()
    tags = infer_tags(name)
    macros = infer_macros("")
    annotations = build_annotations(tags, macros, name)
    return {
        "recipe_id": stable_id(str(path), name),
        "recipe_name": name,
        "category": infer_category(tags, name),
        "ingredients": [],
        "tags": tags,
        "macros": "",
        "notes": f"{source_type.upper()} parsing is not enabled yet. Add extracted text or install parser/OCR support next.",
        "source_file": str(path),
        "source_type": source_type,
        "raw_text": name,
        **macros,
        **annotations,
    }


def collect_recipes() -> list[dict[str, Any]]:
    recipes: list[dict[str, Any]] = []
    for path in sorted(TEXT_DIR.glob("*")):
        if path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS:
            recipes.extend(parse_text_file(path))
        elif path.suffix.lower() in SUPPORTED_TABLE_EXTENSIONS:
            recipes.extend(parse_csv_file(path))

    for path in sorted(PDF_DIR.glob("*")):
        if path.is_file():
            recipes.extend(parse_pdf_file(path))

    for path in sorted(IMAGE_DIR.glob("*")):
        if path.is_file():
            recipes.append(unsupported_placeholder(path, "image"))

    return recipes


def main() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    recipes = collect_recipes()
    if not recipes:
        print(f"No raw files found under {RAW_DIR}. Keeping existing sample data if present.")
        return 0

    df = pd.DataFrame(recipes)
    df["dedupe_name"] = df["recipe_name"].str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    df["is_updated_source"] = df["source_file"].str.lower().str.contains("updated|v2")
    df = (
        df.sort_values(["dedupe_name", "is_updated_source"], ascending=[True, False])
        .drop_duplicates(subset=["dedupe_name"], keep="first")
        .drop(columns=["dedupe_name", "is_updated_source"])
        .sort_values(["category", "recipe_name"])
    )
    df.to_parquet(OUTPUT_PATH, index=False)

    annotations = df[["recipe_id", "recipe_name", "source_file", "tags", "bot_keywords"]].to_dict(orient="records")
    ANNOTATIONS_PATH.write_text(json.dumps(annotations, indent=2), encoding="utf-8")

    print(f"Parsed {len(df)} recipes")
    print(f"Wrote parquet: {OUTPUT_PATH}")
    print(f"Wrote annotations: {ANNOTATIONS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
