from copy import deepcopy
from app.import_rules import AUTO_CORRECT_PROFILES, RARITY_KEYS

def auto_correct_loot_table(
    loot_table: dict,
    profile: str = "safe"
) -> tuple[dict, list[str]]:
    
    config = AUTO_CORRECT_PROFILES.get(profile)
    if not config:
        raise ValueError(f"Unknown auto-correct profile: {profile}")

    table = deepcopy(loot_table)
    changes = []

    # Walk structure
    for category in table.values():
        for item_type in category.values():
            for rarity, items in item_type.items():
                for item in items:

                    # Weight fix
                    if config["fix_weight"]:
                        w = item["drop"].get("weight")
                        if isinstance(w, (int, float)) and w < 1:
                            item["drop"]["weight"] = 1
                            changes.append("Clamped drop.weight to minimum 1")

                    # Normalize rarity casing
                    if config["normalize_rarity"]:
                        if item["rarity"].capitalize() in RARITY_KEYS:
                            item["rarity"] = item["rarity"].capitalize()

                    # Clean tags
                    if config["clean_tags"]:
                        tags = item.get("tags", [])
                        if isinstance(tags, list):
                            clean = [t for t in tags if isinstance(t, str)]
                            if clean != tags:
                                item["tags"] = clean
                                changes.append("Removed invalid tag values")

                    # Fill optional fields
                    if config["fill_optional_fields"]:
                        item.setdefault("tags", [])
                        item.setdefault("stats", {})

    return table, changes
