from typing import Any, Dict, List, Tuple
from app.import_rules import RARITY_KEYS, FATAL_MISSING_ITEM_FIELDS, FATAL_DROP_FIELDS


def validate_loot_table(loot_table: Any) -> Dict[str, Any]:
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    summary = {
        "total_items": 0,
        "categories": 0,
        "item_types": 0,
        "rarity_counts": {r: 0 for r in RARITY_KEYS},
        "unknown_rarity_counts": {},
    }

    # Compatibility flags (this will become a major UX win)
    compatibility = {
        "can_overview": True,
        "can_simulate": True,
        "can_reweight": True,
        "can_export": True,
    }

    # ---- top-level must be dict ----
    if not isinstance(loot_table, dict):
        errors.append({
            "path": "$",
            "message": "Top-level loot_table must be an object/dict of categories."
        })
        # If structure is wrong, nothing else is safe
        for k in compatibility:
            compatibility[k] = False
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "summary": summary,
            "compatibility": compatibility,
        }

    summary["categories"] = len(loot_table)

    # Walk categories
    for cat_name, cat_obj in loot_table.items():
        if not isinstance(cat_obj, dict):
            errors.append({
                "path": f"$.{cat_name}",
                "message": "Category must be an object/dict of item types."
            })
            continue

        # Walk item types
        for type_name, type_obj in cat_obj.items():
            summary["item_types"] += 1

            if not isinstance(type_obj, dict):
                errors.append({
                    "path": f"$.{cat_name}.{type_name}",
                    "message": "Item type must be an object/dict of rarities."
                })
                continue

            # Walk rarities
            for rarity_key, items in type_obj.items():
                if not isinstance(items, list):
                    errors.append({
                        "path": f"$.{cat_name}.{type_name}.{rarity_key}",
                        "message": "Rarity entry must be a list of item objects."
                    })
                    continue

                # Track unknown rarity keys (non-fatal)
                if rarity_key not in RARITY_KEYS:
                    summary["unknown_rarity_counts"][rarity_key] = (
                        summary["unknown_rarity_counts"].get(rarity_key, 0) + len(items)
                    )
                    warnings.append({
                        "path": f"$.{cat_name}.{type_name}.{rarity_key}",
                        "message": f"Unknown rarity key '{rarity_key}'. Allowed: {RARITY_KEYS}"
                    })

                # Walk items
                for i, item in enumerate(items):
                    path = f"$.{cat_name}.{type_name}.{rarity_key}[{i}]"

                    if not isinstance(item, dict):
                        errors.append({
                            "path": path,
                            "message": "Item must be an object/dict."
                        })
                        continue

                    # Required fields
                    missing = [f for f in FATAL_MISSING_ITEM_FIELDS if f not in item]
                    if missing:
                        errors.append({
                            "path": path,
                            "message": f"Missing required fields: {', '.join(missing)}"
                        })
                        continue

                    # name
                    if not isinstance(item["name"], str) or not item["name"].strip():
                        errors.append({
                            "path": f"{path}.name",
                            "message": "Item name must be a non-empty string."
                        })
                        continue

                    # rarity value must match container key
                    if not isinstance(item["rarity"], str):
                        errors.append({
                            "path": f"{path}.rarity",
                            "message": "Item rarity must be a string."
                        })
                        continue

                    if item["rarity"] != rarity_key:
                        errors.append({
                            "path": f"{path}.rarity",
                            "message": f"Item rarity '{item['rarity']}' must match container rarity '{rarity_key}'."
                        })
                        continue

                    # drop.weight
                    drop = item["drop"]
                    if not isinstance(drop, dict):
                        errors.append({
                            "path": f"{path}.drop",
                            "message": "drop must be an object/dict."
                        })
                        continue

                    missing_drop = [f for f in FATAL_DROP_FIELDS if f not in drop]
                    if missing_drop:
                        errors.append({
                            "path": f"{path}.drop",
                            "message": f"Missing required drop fields: {', '.join(missing_drop)}"
                        })
                        continue

                    weight = drop.get("weight")
                    if not isinstance(weight, int):
                        errors.append({
                            "path": f"{path}.drop.weight",
                            "message": "drop.weight must be an integer >= 1."
                        })
                        continue
                    if weight < 1:
                        errors.append({
                            "path": f"{path}.drop.weight",
                            "message": "drop.weight must be >= 1."
                        })
                        continue

                    # Optional fields warnings (non-fatal)
                    if "tags" not in item:
                        warnings.append({
                            "path": path,
                            "message": "Missing optional field 'tags' (recommended)."
                        })
                    else:
                        if not isinstance(item["tags"], list) or any(not isinstance(t, str) for t in item["tags"]):
                            warnings.append({
                                "path": f"{path}.tags",
                                "message": "tags should be a list[str]."
                            })

                    if "stats" in item and not isinstance(item["stats"], dict):
                        warnings.append({
                            "path": f"{path}.stats",
                            "message": "stats should be an object/dict of numeric values."
                        })

                    # Update counts
                    summary["total_items"] += 1
                    if rarity_key in RARITY_KEYS:
                        summary["rarity_counts"][rarity_key] += 1

    # Determine validity
    valid = len(errors) == 0

    # Compatibility decisions
    # If any fatal structural errors exist, prevent deeper tools from being “guaranteed”
    if not valid:
        # Overview can still work sometimes, but we keep this strict for trust
        compatibility["can_overview"] = False
        compatibility["can_simulate"] = False
        compatibility["can_reweight"] = False
        compatibility["can_export"] = False

    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "compatibility": compatibility,
    }
