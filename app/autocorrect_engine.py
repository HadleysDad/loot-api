# app/autocorrect_engine.py

from typing import Dict, List, Any
from copy import deepcopy

# ============================================================
# Profile Definitions
# ============================================================

AUTO_CORRECT_PROFILES = {"safe", "aggressive", "strict"}

SEVERITY_LEVELS = {
    "safe": 1,
    "aggressive": 2,
    "strict": 3,
}

PROFILE_CAPABILITIES = {
    "safe": {
        "preview": True,
        "apply": True,
        "export": False,
        "changes_rarity": False,
        "removes_items": False,
        "description": "Non-destructive fixes only (weights, missing optional fields).",
    },
    "aggressive": {
        "preview": True,
        "apply": False,
        "export": False,
        "changes_rarity": True,
        "removes_items": False,
        "description": "Structural normalization and balance fixes (preview-only).",
    },
    "strict": {
        "preview": True,
        "apply": False,
        "export": False,
        "changes_rarity": True,
        "removes_items": True,
        "description": "CI-grade enforcement with strict schema rules.",
    },
}


# ============================================================
# Preview Generator (AUTHORITATIVE SOURCE OF TRUTH)
# ============================================================

def generate_autocorrect_preview(
    loot_table: Dict[str, Any],
    validation_result: Dict[str, Any],
    profile: str = "safe",
) -> Dict[str, Any]:

    if profile not in AUTO_CORRECT_PROFILES:
        raise ValueError(f"Invalid auto-correct profile: {profile}")

    fixes: List[Dict[str, Any]] = []
    warnings = validation_result.get("warnings", [])
    errors = validation_result.get("errors", [])

    # --------------------------------------------------
    # SAFE fixes
    # --------------------------------------------------

    # Clamp invalid or missing drop.weight
    for err in errors:
        msg = err.get("message", "")
        path = err.get("path", "")

        if "drop.weight" in msg:
            fixes.append({
                "path": path,
                "issue": msg,
                "before": "invalid or < 1",
                "after": 1,
                "action": "Clamp drop.weight to minimum of 1",
                "severity": "safe",
            })

    # Missing optional tags
    for warn in warnings:
        msg = warn.get("message", "")
        path = warn.get("path", "")

        if "Missing optional field 'tags'" in msg:
            fixes.append({
                "path": path,
                "issue": "Missing tags",
                "before": None,
                "after": [],
                "action": "Add empty tags list",
                "severity": "safe",
            })

    # --------------------------------------------------
    # AGGRESSIVE fixes (preview only)
    # --------------------------------------------------

    for err in errors:
        msg = err.get("message", "")
        path = err.get("path", "")

        if "must match container rarity" in msg:
            fixes.append({
                "path": path,
                "issue": msg,
                "before": "item.rarity != container rarity",
                "after": "container rarity",
                "action": "Normalize item.rarity to container rarity",
                "severity": "aggressive",
            })
    
    #---------------------------------------------------
    # AGGRESSIVE Missing rarity tiers
    #---------------------------------------------------
    
    expected_rarities = {"Common", "Uncommon", "Rare", "Epic", "Legendary"}

    for category_name, category in loot_table.items():
        if not isinstance(category, dict):
            continue

        for item_type_name, type_block in category.items():
            if not isinstance(type_block, dict):
                continue

            existing_rarities = set(type_block.keys())
            missing_rarities = expected_rarities - existing_rarities

            if missing_rarities:
                fixes.append({
                    "path": f"$.{category_name}.{item_type_name}",
                    "issue": f"Missing rarity tiers: {sorted(missing_rarities)}",
                    "before": sorted(existing_rarities),
                    "after": sorted(expected_rarities),
                    "action": "Add empty rarity lists for consistency",
                    "severity": "aggressive",
                })
    
    #---------------------------------------------------
    # AGGRESSIVE: Weight outliers within rarity
    #---------------------------------------------------
    
    rarity_weight_totals = {}
    rarity_item_counts = {}
    
    for category in loot_table.values():
        for type_block in category.values():
            for rarity, items in type_block.items():
                for item in items:
                    weight = item.get("drop", {}).get("weight")
                    if isinstance(weight, int):
                        rarity_weight_totals[rarity] = (
                            rarity_weight_totals.get(rarity, 0) + weight
                        )
                        rarity_item_counts[rarity] = (
                            rarity_item_counts.get(rarity, 0) + 1
                        )
    
    rarity_avg_weight = {
        r: rarity_weight_totals[r] / rarity_item_counts[r]
        for r in rarity_weight_totals
        if rarity_item_counts[r] > 0
    }
    
    for category_name, category in loot_table.items():
        for item_type_name, type_block in category.items():
            for rarity, items in type_block.items():
                avg = rarity_avg_weight.get(rarity)
                if not avg:
                    continue
                
                for idx, item in enumerate(items):
                    weight = item.get("drop", {}).get("weight")
                    if isinstance(weight, int) and weight > avg * 5:
                        fixes.append({
                            "path": f"$.{category_name}.{item_type_name}.{rarity}[{idx}].drop.weight",
                            "issue": "Weight is extreme outlier within rarity tier",
                            "before": weight,
                            "after": int(avg * 2),
                            "action": "Cap weight relative to rarity average",
                            "severity": "aggressive",
                        })
    
    #---------------------------------------------------
    # AGGRESSIVE: Rarity curve imbalance
    #---------------------------------------------------
    
    expected_curve = {
        "common": 70,
        "Uncommon": 20,
        "Rare": 7,
        "Epic": 2.5,
        "Legendary": 0.5,
    }
    
    rarity_counts = validation_result.get("summary", {}).get("rarity_counts", {})
    total_items = sum(rarity_counts.values()) or 1
    
    for rarity, expected_pct in expected_curve.items():
        actual_pct = (rarity_counts.get(rarity, 0) / total_items) * 100
        drift = round(actual_pct - expected_pct, 2)
        
        if abs(drift) >= 5:
            fixes.append({
                "path": "$",
                "issue": f"{rarity} rarity deviates from expected curve by {drift}%",
                "before": round(actual_pct, 2),
                "after": expected_pct,
                "action": "Rebalance global rarity distributions",
                "severity": "aggressive",
            })
 
    # --------------------------------------------------
    # STRICT fixes (preview only)
    # --------------------------------------------------

    summary = validation_result.get("summary", {})
    unknown_rarities = summary.get("unknown_rarity_counts", {})

    for rarity, count in unknown_rarities.items():
        fixes.append({
            "path": "$",
            "issue": f"Unknown rarity '{rarity}' used {count} times",
            "before": rarity,
            "after": None,
            "action": "Reject or remove items with unknown rarity",
            "severity": "strict",
        })

    # --------------------------------------------------
    # Filter fixes by profile severity
    # --------------------------------------------------

    allowed_level = SEVERITY_LEVELS[profile]

    applicable_fixes = [
        fix for fix in fixes
        if SEVERITY_LEVELS[fix["severity"]] <= allowed_level
    ]

    return {
        "profile": profile,
        "would_apply": len(applicable_fixes) > 0,
        "summary": {
            "total_detected_issues": len(fixes),
            "applicable_fixes": len(applicable_fixes),
        },
        "fixes": applicable_fixes,
        "warnings": [w.get("message", "") for w in warnings],
    }


# ============================================================
# Diff Builder (Preview → Diff-Only Output)
# ============================================================

def build_autocorrect_diff(preview: Dict[str, Any]) -> Dict[str, Any]:
    diffs: List[Dict[str, Any]] = []

    for fix in preview.get("fixes", []):
        diffs.append({
            "path": fix.get("path"),
            "severity": fix.get("severity"),
            "issue": fix.get("issue"),
            "before": fix.get("before"),
            "after": fix.get("after"),
            "action": fix.get("action"),
        })

    return {
        "profile": preview.get("profile"),
        "diff_count": len(diffs),
        "diffs": diffs,
    }


# ============================================================
# Apply Engine (SAFE ONLY – uses preview as input)
# ============================================================

def apply_autocorrect(
    loot_table: Dict[str, Any],
    preview: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Applies SAFE auto-correct fixes from a preview to a COPY of the loot table.
    Only fixes explicitly listed in the preview are applied.
    """
    table = deepcopy(loot_table)

    for fix in preview.get("fixes", []):
        if fix.get("severity") != "safe":
            continue

        _apply_single_fix(table, fix)

    return table


# ============================================================
# Internal Fix Handlers
# ============================================================

def _apply_single_fix(table: Dict[str, Any], fix: Dict[str, Any]) -> None:
    action = fix.get("action", "")
    path = fix.get("path", "")

    if "Clamp drop.weight" in action:
        _apply_weight_clamp(table, path)

    if "Add empty tags list" in action:
        _apply_missing_tags(table, path)


def _apply_weight_clamp(table: Dict[str, Any], path: str) -> None:
    try:
        parts = path.replace("$.", "").split(".")
        category, item_type, rarity_idx = parts[0], parts[1], parts[2]

        rarity, idx = rarity_idx.split("[")
        idx = int(idx.rstrip("]"))

        item = table[category][item_type][rarity][idx]
        drop = item.setdefault("drop", {})

        weight = drop.get("weight")
        if not isinstance(weight, int) or weight < 1:
            drop["weight"] = 1

    except Exception:
        # SAFE must never crash
        return


def _apply_missing_tags(table: Dict[str, Any], path: str) -> None:
    try:
        parts = path.replace("$.", "").split(".")
        category, item_type, rarity_idx = parts[0], parts[1], parts[2]

        rarity, idx = rarity_idx.split("[")
        idx = int(idx.rstrip("]"))

        item = table[category][item_type][rarity][idx]

        if "tags" not in item:
            item["tags"] = []

    except Exception:
        return


# ============================================================
# Capability Helper
# ============================================================

def get_profile_capabilities(profile: str) -> Dict[str, Any]:
    return PROFILE_CAPABILITIES.get(profile, PROFILE_CAPABILITIES["safe"])
