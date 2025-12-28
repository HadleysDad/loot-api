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
