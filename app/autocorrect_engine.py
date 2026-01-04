# app/autocorrect_engine.py

from typing import Dict, List, Any, Tuple, Iterator
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
        "description": "Progression & economy diagnostics + structural normalization (preview-only).",
    },
    "strict": {
        "preview": True,
        "apply": False,
        "export": False,
        "changes_rarity": True,
        "removes_items": True,
        "description": "CI-grade enforcement with strict schema rules (preview-only).",
    },
}

RARITY_ORDER = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

STAT_IMPACT_WEIGHTS = {
    "attack": 1.0,
    "damage": 1.0,
    "crit_chance": 1.5,
    "crit_damage": 1.5,
    "attack_speed": 1.2,
    "armor": 0.8,
    "health": 0.6,
    "lifesteal": 2.0,
    "cooldown_reduction": 1.8,
}

# ============================================================
# Helpers
# ============================================================

def _norm_rarity(r: str) -> str:
    if not isinstance(r, str):
        return str(r)
    # keep exact "Common" style
    return r[:1].upper() + r[1:]


def _iter_items(loot_table: Dict[str, Any]) -> Iterator[Tuple[str, str, str, int, Dict[str, Any]]]:
    """
    Yields: category_name, item_type_name, rarity_name, idx, item
    Safe iterator: never throws if structure is weird.
    """
    if not isinstance(loot_table, dict):
        return
    for category_name, category_block in loot_table.items():
        if not isinstance(category_block, dict):
            continue
        for item_type_name, type_block in category_block.items():
            if not isinstance(type_block, dict):
                continue
            for rarity_name, items in type_block.items():
                if not isinstance(items, list):
                    continue
                for idx, item in enumerate(items):
                    if isinstance(item, dict):
                        yield category_name, item_type_name, _norm_rarity(rarity_name), idx, item


def _path(cat: str, typ: str, rarity: str, idx: int, field: str | None = None) -> str:
    base = f"$.{cat}.{typ}.{rarity}[{idx}]"
    if field:
        return f"{base}.{field}"
    return base


def _power_score(item: Dict[str, Any]) -> float:
    """
    Simple "power" heuristic:
    sum of numeric stats (if present), else 0.
    """
    stats = item.get("stats", {})
    if not isinstance(stats, dict):
        return 0.0
    total = 0.0
    for v in stats.values():
        if isinstance(v, (int, float)):
            total += float(v)
    return total


def _safe_weight(item: Dict[str, Any]) -> int:
    drop = item.get("drop", {})
    if not isinstance(drop, dict):
        return 0
    w = drop.get("weight", 0)
    if isinstance(w, bool):
        return 0
    if isinstance(w, (int, float)):
        return int(w)
    return 0


def _weight_concentration(weights: List[int]) -> float:
    """
    Returns "dominance" ratio: (sum of top 5 weights) / (sum of all weights).
    0..1. Higher = fewer items dominate.
    """
    if not weights:
        return 0.0
    total = sum(max(0, int(w)) for w in weights)
    if total <= 0:
        return 0.0
    top = sorted((max(0, int(w)) for w in weights), reverse=True)[:5]
    return sum(top) / total

def _compute_item_power(item: Dict[str, Any]) -> float:
    stats = item.get("stats", {})
    score = 0.0
    
    for stat, value in stats.items():
        weight = STAT_IMPACT_WEIGHTS.get(stat, 0.5)
        if isinstance(value, (int, float)):
            score += value * weight
    
    return round(score, 2) 


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
    # AGGRESSIVE fixes (Phase 1–3 placeholders already exist in your project)
    # Keep your earlier aggressive rules above/below as needed.
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

    # ==================================================
    # AGGRESSIVE PHASE 4: Progression & Economy Signals
    # Preview-only diagnostics (no apply/export)
    # ==================================================

    # Collect per-rarity stats, tags, weights
    rarity_power: Dict[str, List[float]] = {r: [] for r in RARITY_ORDER}
    rarity_weights: Dict[str, List[int]] = {r: [] for r in RARITY_ORDER}
    rarity_tag_sets: Dict[str, set] = {r: set() for r in RARITY_ORDER}
    rarity_stat_keys: Dict[str, set] = {r: set() for r in RARITY_ORDER}

    total_weight_all = 0
    total_weight_by_rarity: Dict[str, int] = {r: 0 for r in RARITY_ORDER}

    for cat, typ, rarity, idx, item in _iter_items(loot_table):
        if rarity not in rarity_power:
            # Ignore custom tiers for phase 4 metrics
            continue

        p = _power_score(item)
        w = _safe_weight(item)

        rarity_power[rarity].append(p)
        rarity_weights[rarity].append(w)

        total_weight_all += max(0, w)
        total_weight_by_rarity[rarity] += max(0, w)

        tags = item.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str):
                    rarity_tag_sets[rarity].add(t)

        stats = item.get("stats", {})
        if isinstance(stats, dict):
            for k in stats.keys():
                if isinstance(k, str):
                    rarity_stat_keys[rarity].add(k)

    # ---- Phase 4 Rule 1: Power Inflation Curve (avg power should rise by tier) ----
    # Only evaluate if we have enough data points to be meaningful
    avg_power: Dict[str, float] = {}
    for r in RARITY_ORDER:
        vals = rarity_power[r]
        if vals:
            avg_power[r] = round(sum(vals) / max(1, len(vals)), 4)
        else:
            avg_power[r] = 0.0

    # Require each tier to be meaningfully >= previous (tolerance)
    # Tunable threshold: 10% lift between tiers (indie-friendly default)
    lift = 1.10
    for i in range(1, len(RARITY_ORDER)):
        prev_r = RARITY_ORDER[i - 1]
        cur_r = RARITY_ORDER[i]
        prev_val = avg_power.get(prev_r, 0.0)
        cur_val = avg_power.get(cur_r, 0.0)

        # If stats are missing across the board, don't spam
        if prev_val == 0.0 and cur_val == 0.0:
            continue

        if prev_val > 0 and cur_val < prev_val * lift:
            fixes.append({
                "path": "$",
                "issue": f"Progression curve weak: avg {cur_r} power ({cur_val}) is not at least {int((lift-1)*100)}% above {prev_r} ({prev_val}).",
                "before": {"avg_power": {prev_r: prev_val, cur_r: cur_val}},
                "after": f"Increase {cur_r} stats or reduce {prev_r} stats/weights to create clearer progression.",
                "action": f"Adjust stat curve so {cur_r} is meaningfully stronger than {prev_r}.",
                "severity": "aggressive",
            })

    # ---- Phase 4 Rule 2: Legendary not meaningfully stronger than Epic ----
    epic = avg_power.get("Epic", 0.0)
    leg = avg_power.get("Legendary", 0.0)
    if epic > 0 and leg > 0 and leg < epic * 1.10:
        fixes.append({
            "path": "$",
            "issue": f"Legendary power may feel unrewarding: avg Legendary ({leg}) is < 10% above avg Epic ({epic}).",
            "before": {"avg_power": {"Epic": epic, "Legendary": leg}},
            "after": "Increase Legendary stats or reduce Epic stats for clearer payoff.",
            "action": "Increase Legendary stat deltas vs Epic (or reduce Epic power).",
            "severity": "aggressive",
        })

    # ---- Phase 4 Rule 3: Early Legendary Risk (legendary weight share) ----
    if total_weight_all > 0:
        leg_share = (total_weight_by_rarity.get("Legendary", 0) / total_weight_all) * 100
        # Tunable: > 1.0% of total weight is often too generous for legendaries
        if leg_share > 1.0:
            fixes.append({
                "path": "$",
                "issue": f"Early Legendary risk: Legendary weight share is {round(leg_share, 3)}% of total pool (often too high).",
                "before": {"legendary_weight_share_percent": round(leg_share, 3)},
                "after": "Reduce Legendary weights or increase lower-tier weights to preserve progression.",
                "action": "Reduce Legendary drop weights (or gate Legendary behind progression).",
                "severity": "aggressive",
            })

    # ---- Phase 4 Rule 4: Loot Fatigue / Weight Concentration (dominance) ----
    # If top 5 items account for too much of a tier's weight, players see repeats.
    for r in RARITY_ORDER:
        dominance = _weight_concentration(rarity_weights[r])
        if dominance >= 0.50 and sum(rarity_weights[r]) > 0:
            fixes.append({
                "path": "$",
                "issue": f"Loot fatigue risk in {r}: top-weight items dominate {round(dominance*100, 2)}% of tier weight.",
                "before": {"dominance_percent": round(dominance * 100, 2), "rarity": r},
                "after": "Spread weights more evenly; add more items; reduce top-item weights.",
                "action": f"Reduce top weights in {r} or add more comparable items to increase variety.",
                "severity": "aggressive",
            })

    # ---- Phase 4 Rule 5: Rarity Purpose Check (new mechanics/tags/stats keys) ----
    # Higher tiers should introduce *something* new (tags or stat keys).
    # Compare each tier to previous.
    for i in range(1, len(RARITY_ORDER)):
        prev_r = RARITY_ORDER[i - 1]
        cur_r = RARITY_ORDER[i]
        prev_tags = rarity_tag_sets.get(prev_r, set())
        cur_tags = rarity_tag_sets.get(cur_r, set())
        prev_keys = rarity_stat_keys.get(prev_r, set())
        cur_keys = rarity_stat_keys.get(cur_r, set())

        # If tier exists but adds nothing new vs prev
        if cur_tags and prev_tags and cur_tags.issubset(prev_tags) and cur_keys.issubset(prev_keys):
            fixes.append({
                "path": "$",
                "issue": f"{cur_r} may lack unique identity: tags/stats keys are not introducing new mechanics vs {prev_r}.",
                "before": {
                    "prev_rarity": prev_r,
                    "cur_rarity": cur_r,
                    "new_tags_count": len(cur_tags - prev_tags),
                    "new_stat_keys_count": len(cur_keys - prev_keys),
                },
                "after": f"Introduce new tags or stat mechanics in {cur_r} to justify tier progression.",
                "action": f"Add unique tags and/or new stat keys to {cur_r} items (tier identity).",
                "severity": "aggressive",
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
