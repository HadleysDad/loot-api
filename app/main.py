from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
import copy
from copy import deepcopy
from fastapi.responses import JSONResponse

from app.loot_loader import LOOT_TABLE
from app.rng import get_rng
from app.drop_engine import (
    extract_all_items,
    extract_items_by_tag,
    extract_items_by_tags,
    roll_from_items,
    simulate_drops,
    apply_luck,
)

from app.schemas import (
    DropRequest,
    CategoryDropRequest,
    RarityDropRequest,
    TagSearchRequest,
    TagDropRequest,
    SimulationRequest,
    LuckDropRequest,
    LuckSimulateRequest,
    CompareSimulationRequest,
    BalanceRequest,
    ReweightRequest,
    ExportRequest,
    ImportTestRequest,
)


app = FastAPI(
    title="Loot Table API",
    description="AAA-grade loot RNG system for game developers — compatible with Unity, Roblox, Unreal, Godot.",
    version="3.0.0",
)

# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health", tags=["Health"], response_model=dict)
def health_check():
    return {"status": "ok"}


# ============================================================
# METADATA ENDPOINTS
# ============================================================
@app.get(
    "/info", 
    tags=["Metadata"], 
    summary="API Info + Systme Metadata",
    description="Returns API build version, author, items counts, and structure overview", 
    response_model=dict
)
def info():
    return {
        "name": "Loot Table API",
        "version": "3.0.0",
        "item_count": len(extract_all_items(LOOT_TABLE)),
        "categories": list(LOOT_TABLE.keys()),
        "author": "Sam Grabar",
        "license": "Commercial",
    }

@app.get(
    "/schema",
    tags=["Metadata"],
    summary="Returns full loot table JSON",
    description="Useful for debugging, browsing items, or exporting your starting schema.", 
    response_model=dict
)
def schema():
    return LOOT_TABLE


@app.get(
    "/tags",
    tags=["Metadata"],
    summary="Retrieve every tag used across loot table",
    description="Used for filtering simulations, dropsm abd crafting analysis.", 
    response_model=List[str]
)
def list_tags():
    tags = set()
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    tags.update(item.get("tags", []))
    return sorted(tags)


@app.get(
    "/stats",
    tags=["Metadata"],
    summary="List every stat name used by items",
    description="Strength / Agility / Luck / AttackSpeed / etc.", 
    response_model=List[str]
)
def list_stats():
    stats = set()
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    stats.update(item.get("stats", {}).keys())
    return sorted(stats)


@app.get(
    "/categories",
    tags=["Metadata"],
    summary="List every category used by items.",
    description="All searchable categories used in the loot table.", 
    response_model=List[str]
)
def list_categories():
    return list(LOOT_TABLE.keys())


#============================================================
# Help
#============================================================

@app.get("/rarity/schema", tags=["Help"])
def rarity_schema():
    return {
        "Common": "float % value",
        "Uncommon": "float % value",
        "Rare": "float % value",
        "Epic": "float % value",
        "Legendary": "float % value"
    }

# ============================================================
# ITEM SEARCH
# ============================================================

@app.post(
    "/items/by-tag/{tag}",
    tags=["Item Search"],
    summary="Return all item containing a specific tag",
    description="Example tags: fire | frost | sword | healing | ring | rare",
    response_model=dict
)
def items_by_tag(tag: str):
    items = extract_items_by_tag(LOOT_TABLE, tag)
    return {
        "tag": tag,
        "count": len(items),
        "items": items,
    }


@app.post(
    "/items/by-tags",
    tags=["Item Search"],
    summary="Search using multiple tags",
    description="Returns only items that contain ALL requested tags.",
    response_model=dict
)
def items_by_tags(req: TagSearchRequest):
    items = extract_items_by_tags(LOOT_TABLE, req.tags)
    return {
        "tags": req.tags,
        "count": len(items),
        "items": items,
    }


# ============================================================
# SINGLE DROPS
# ============================================================

@app.post(
    "/drop",
    tags=["Drops"],
    summary="Random drop from entire loot pool",
    description="Ignores rarity and category. Uses weighted probability table.", 
    response_model=dict
)
def drop_any(req: DropRequest):
    rng = get_rng(req.seed)
    items = extract_all_items(LOOT_TABLE)
    return {"drop": roll_from_items(items, rng)}


@app.post(
    "/drop/by-category",
     tags=["Drops"],
    summary="Drop from specific category",
    description="Armor-only drops, Weapon-only drops, Jewellery, Materials, etc.", 
    response_model=dict
)
def drop_by_category(req: CategoryDropRequest):
    category = req.category.lower()

    if category not in LOOT_TABLE:
        raise HTTPException(400, "Invalid category name")

    rng = get_rng(req.seed)
    items = []

    for item_type in LOOT_TABLE[category].values():
        for rarity in item_type.values():
            items.extend(rarity)

    return {"category": category, "drop": roll_from_items(items, rng)}


@app.post(
    "/drop/by-rarity",
     tags=["Drops"],
    summary="Drop from specific rarity",
    description="Common / Uncommon / Rare / Epic / Legendary restricted RNG.",
    response_model=dict
)
def drop_by_rarity(req: RarityDropRequest):
    rarity = req.rarity.value.lower()
    rng = get_rng(req.seed)

    items = []
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            items.extend(item_type.get(rarity, []))

    if not items:
        raise HTTPException(400, "No items for that rarity")

    return {"rarity": rarity, "drop": roll_from_items(items, rng)}


@app.post(
    "/drop/by-tag/{tag}",
    tags=["Drops"],
    summary="Drop single item matching tag",
    description="Useful for ability or class–specific loot rolls.", 
    response_model=dict
)
def drop_by_tag(tag: str, seed: int | None = None):
    items = extract_items_by_tag(LOOT_TABLE, tag)

    if not items:
        raise HTTPException(400, "No items contain this tag")

    rng = get_rng(seed)
    return {"tag": tag, "drop": roll_from_items(items, rng)}


@app.post(
    "/drop/by-tags",
    tags=["Drops"],
    summary="Drop using multi-tag filter",
    description="Returns loot that matches all tags simultaneously.", 
    response_model=dict
)
def drop_by_tags(req: TagDropRequest):
    items = extract_items_by_tags(LOOT_TABLE, req.tags)

    if not items:
        raise HTTPException(400, "No items match these tags")

    rng = get_rng(req.seed)
    return {"tags": req.tags, "drop": roll_from_items(items, rng)}


@app.post(
    "/drop/with-luck",
     tags=["Drops"],
    summary="Drop roll with probability biasing",
    description="luck=1.0 dramatically improves rare/legendary probability.",
    response_model=dict
)
def drop_with_luck(req: LuckDropRequest):
    luck = max(0.0, min(req.luck, 1.0))
    rng = get_rng(req.seed)

    if req.tags:
        items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not items:
            raise HTTPException(400, "No items match provided tags")
    else:
        items = extract_all_items(LOOT_TABLE)

    adjusted_items = apply_luck(items, luck)
    drop = roll_from_items(adjusted_items, rng)

    return {
        "luck": luck,
        "tags": req.tags,
        "drop": drop,
    }

#=============================================================
# TRY IT NOW: LEGENDARY PREVIEW
#=============================================================

@app.get(
    "/legenday-preview",
    tags=["Debug / Preview"],
    summary="Show a single legendary result",
    description="Used as a live RNG validator inside docs.", 
    response_model=dict
)
def legendary_preview():
    items = []
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            items.extend(item_type.get("legendary", []))
    rng = get_rng()
    return {"legendary": roll_from_items(items, rng)}


# ============================================================
# SIMULATION ENGINE (STANDARD)
# ============================================================

@app.post(
    "/simulate",
    tags=["Simulation"],
    summary="Run probability simulation",
    description="Returns rarity distribution statistics and top item results.", 
    response_model=dict
)
def simulate(req: SimulationRequest):

    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")

    rng = get_rng(req.seed)

    if req.tags:
        items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not items:
            raise HTTPException(400, "No items match provided tags")
    else:
        items = extract_all_items(LOOT_TABLE)

    drops = simulate_drops(items, rng, req.simulations)

    rarity_counts = {}
    item_counts = {}
    item_rarity = {}
    tag_counts = {}

    for item in drops:

        rar = item["rarity"]
        rarity_counts[rar] = rarity_counts.get(rar, 0) + 1

        name = item["name"]
        item_counts[name] = item_counts.get(name, 0) + 1
        item_rarity[name] = rar

        for tag in item.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # enforce correct rarity order
    rarity_order = [
        "Common",
        "Uncommon",
        "Rare",
        "Epic",
        "Legendary"
    ]

    rarity_distribution = {
        r: round((rarity_counts.get(r, 0) / req.simulations) * 100, 2)
        for r in rarity_order
        if r in rarity_counts
    }

    # rarity selectors
    def top_by_rarity(target, limit=3):
        return [
            (name, count)
            for name, count in sorted(
                item_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            if item_rarity.get(name) == target
        ][:limit]

    warnings = []

    if rarity_distribution.get("Legendary", 0) < 0.5:
        warnings.append("Legendary items drop less than 0.5% of the time.")

    return {
        "simulations": req.simulations,
        "rarity_distribution": rarity_distribution,
        "top_items_overall": sorted(
            item_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10],
        "top_rare_items": top_by_rarity("Rare"),
        "top_epic_items": top_by_rarity("Epic"),
        "top_legendary_items": top_by_rarity("Legendary"),
        "warnings": warnings
    }

# ============================================================
# SIMULATION ENGINE (LUCK)
# ============================================================

@app.post(
    "/simulate/with-luck",
     tags=["Simulation"],
    summary="Run RNG simulation with luck bias",
    description="Shows how loot shifts under luck biasing conditions.",
    response_model=dict
)
def simulate_with_luck(req: LuckSimulateRequest):

    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")

    luck = max(0.0, min(req.luck, 1.0))
    rng = get_rng(req.seed)

    if req.tags:
        items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not items:
            raise HTTPException(400, "No items match provided tags")
    else:
        items = extract_all_items(LOOT_TABLE)

    adjusted_items = apply_luck(items, luck)
    drops = simulate_drops(adjusted_items, rng, req.simulations)

    rarity_counts = {}
    item_counts = {}
    item_rarity = {}

    for item in drops:
        rar = item["rarity"]
        rarity_counts[rar] = rarity_counts.get(rar, 0) + 1

        name = item["name"]
        item_counts[name] = item_counts.get(name, 0) + 1
        item_rarity[name] = rar

    rarity_order = [
        "Common",
        "Uncommon",
        "Rare",
        "Epic",
        "Legendary"
    ]

    rarity_distribution = {
        r: round((rarity_counts.get(r, 0) / req.simulations) * 100, 2)
        for r in rarity_order
        if r in rarity_counts
    }

    def top_by_rarity(target, limit=3):
        return [
            (name, count)
            for name, count in sorted(
                item_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            if item_rarity.get(name) == target
        ][:limit]

    warnings = []

    if rarity_distribution.get("Legendary", 0) < 0.5:
        warnings.append("Legendary items drop less than 0.5% of the time.")

    return {
        "luck": luck,
        "simulations": req.simulations,
        "rarity_distribution": rarity_distribution,
        "top_items_overall": sorted(
            item_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10],
        "top_rare_items": top_by_rarity("Rare"),
        "top_epic_items": top_by_rarity("Epic"),
        "top_legendary_items": top_by_rarity("Legendary"),
        "warnings": warnings
    }



# ============================================================
# SIMULATION COMPARISON
# ============================================================

@app.post(
    "/simulate/compare",
    tags=["Simulation"],
    summary="Compare standard vs luck simulation",
    description="Used by devs to evaluate impact on balance before shipping change.", 
    response_model=dict
)
def simulate_compare(req: CompareSimulationRequest):

    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")

    luck = max(0.0, min(req.luck, 1.0))

    rng_a = get_rng(req.seed)
    rng_b = get_rng(req.seed)

    if req.tags:
        base_items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not base_items:
            raise HTTPException(400, "No items match provided tags")
    else:
        base_items = extract_all_items(LOOT_TABLE)

    lucky_items = apply_luck(base_items, luck)

    drops_a = simulate_drops(base_items, rng_a, req.simulations)
    drops_b = simulate_drops(lucky_items, rng_b, req.simulations)

    def analyze(results):
        rarity_counts = {}
        for item in results:
            r = item["rarity"]
            rarity_counts[r] = rarity_counts.get(r, 0) + 1
        return {
            r: round((c / req.simulations) * 100, 2)
            for r, c in rarity_counts.items()
        }

    base_dist = analyze(drops_a)
    luck_dist = analyze(drops_b)

    delta = {
        r: round(luck_dist.get(r, 0) - base_dist.get(r, 0), 2)
        for r in set(base_dist) | set(luck_dist)
    }

    return {
        "simulations": req.simulations,
        "luck": luck,
        "rarity_distribution": {
            "base": base_dist,
            "with_luck": luck_dist,
            "delta": delta,
        }
    }

#=============================================================
# BALANCE/OVERVIEW
#=============================================================

@app.get(
    "/balance/overview",
    tags=["Balance Tools"],
    summary="Full loot table balance analysis",
    description="Category %, rarity %, tag %, and stat curve averages included.", 
    response_model=dict
)
def balance_overview():

    total_items = 0

    rarity_counts = {
        "Common": 0,
        "Uncommon": 0,
        "Rare": 0,
        "Epic": 0,
        "Legendary": 0,
    }

    category_counts = {}          # weapons/armor/…
    item_type_counts = {}         # swords/boots/…
    tag_counts = {}               # fire/melee/…
    stat_totals_by_rarity = {}    # track attribute sums
    stat_counts_by_rarity = {}    # track number of items used
    
    # walk entire loot table
    for category_name, category in LOOT_TABLE.items():
        category_counts[category_name] = category_counts.get(category_name, 0) + 0
        
        for item_type_name, rarities in category.items():
            item_type_counts[item_type_name] = item_type_counts.get(item_type_name, 0) + 0

            for rarity_name, items in rarities.items():

                for item in items:

                    total_items += 1

                    # rarity
                    rarity_counts[rarity_name.capitalize()] += 1

                    # category count finalization
                    category_counts[category_name] += 1

                    # item type count finalization
                    item_type_counts[item_type_name] += 1

                    # tags
                    for tag in item.get("tags", []):
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1

                    # stats
                    stats = item.get("stats", {})
                    if stats:

                        # init rarity stat buckets
                        if rarity_name not in stat_totals_by_rarity:
                            stat_totals_by_rarity[rarity_name] = {}
                            stat_counts_by_rarity[rarity_name] = 0

                        stat_counts_by_rarity[rarity_name] += 1

                        for stat_name, value in stats.items():
                            stat_totals_by_rarity[rarity_name][stat_name] = \
                                stat_totals_by_rarity[rarity_name].get(stat_name, 0) + value
            
    # compute rarity %
    rarity_percentages = {
        rarity: round((count / total_items) * 100, 2)
        for rarity, count in rarity_counts.items()
        if total_items > 0
    }    
    
    # compute average stats per rarity
    rarity_stat_averages = {}
    
    for rarity, totals in stat_totals_by_rarity.items():
        rarity_stat_averages[rarity.capitalize()] = {
            stat_name: round(totals[stat_name] / stat_counts_by_rarity[rarity], 2)
            for stat_name in totals
        }
    
    # compute category percentages
    category_percentages = {
        cat: round((count / total_items) * 100, 2)
        for cat, count in category_counts.items()
        if total_items > 0
    }
    
    # compute item type percentage
    item_type_percentages = {
        typ: round((count / total_items) * 100, 2)
        for typ, count in item_type_counts.items()
        if total_items > 0
    }
    
    # build return
    return {
        "total_items": total_items,
        
        "rarity_item_counts": rarity_counts,
        "rarity_percentages": rarity_percentages,
        
        "category_counts": category_counts,
        "category_percentages": category_percentages,
        
        "item_type_counts": item_type_counts,
        "item_type_percentages": item_type_percentages,
        
        "tag_population": dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)),
        
        "rarity_stat_averages": rarity_stat_averages
    }

#============================================================================================
# Balance Test-Import: validate a custom loot tavle JSON
#============================================================================================

@app.post(
    "/balance/test-import",
    response_model=dict,
    tags=["Balance Tools"],
    summary="Validate a custom loot table JSON",
    description=(
        "Upload your own loot table JSON (same structure as /schema) and get:\n"
        "- structural validation (required fields, types, weights)\n"
        "- rarity / category summaries\n"
        "- tag population\n"
        "- average stats per rarity\n"
        "This endpoint does NOT modify the built-in loot table."
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "name": "UnityLoot_v1",
                        "loot_table": {
                            "Weapons": {
                                "sword_1h": {
                                    "Common": [
                                        {
                                            "name": "Rusty Sword",
                                            "rarity": "Common",
                                            "type": "weapon_sword_1h",
                                            "tags": ["melee", "physical"],
                                            "stats": {"attack": 5},
                                            "drop": {"weight": 100}
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        }
    }
)
def balance_test_import(req: ImportTestRequest):
    
    loot_table = req.loot_table
    name = req.name or "imported_loot_table"
    
    errors: List[str] = []
    warnings: List[str] = []
    
    total_items = 0
    rarity_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    item_type_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}

    stat_totals_by_rarity: Dict[str, Dict[str, float]] = {}
    stat_counts_by_rarity: Dict[str, int] = {}
    
    # 1. Top-level structure check
    if not isinstance(loot_table, dict):
        errors.append("Top-level 'loot_table' must be a JSON ovject (dict of categories).")
        return {
            "name": name,
            "valid": False,
            "errors": errors,
            "warnings": warnings,
        }
    
    # 2. Walk structure: category -> item_type -> rarity -> [items]
    for category_name, category_val in loot_table.items():
        if not isinstance(category_val, dict):
            errors.append(
                f"Category '{category_name}' should map to an object of item types (dict)."
            )
            continue
        
        category_counts.setdefault(category_name, 0)
        
        for item_type_name, type_val in category_val.items():
            if not isinstance(type_val, dict):
                errors.append(
                    f"In category '{category_name}', item type '{item_type_name}'"
                    f"should map to an object of rarities (dict)."
                )
                continue
            
            item_type_counts.setdefault(item_type_name, 0)
            
            for rarity_name, items in type_val.items():
                if not isinstance(items, list):
                    errors.append(
                        f"In {category_name}/{item_type_name}, rarity '{rarity_name}' "
                        f"should be a list of items."
                    )
                    continue
                
                for idx, item in enumerate(items):
                    path = f"{category_name}/{item_type_name}/{rarity_name}[{idx}]"
                    
                    if not isinstance(item, dict):
                        errors.append(f"Item at {path} must be an ovject.")
                        continue
                    
                    # Required fields
                    required_fields = ["name", "rarity", "types", "drop"]
                    missing = [f for f in required_fields if f not in item]
                    if missing:
                        errors.append(
                            f"Item at {path} is missing required fields: {', '.join(missing)}"
                        )
                        continue
                    
                    # name
                    if not isinstance(item["name"], str):
                        errors.append(f"Item at {path} has non-string 'name'.")
                        continue
                    
                    # rarity value
                    rarity_value = item["rarity"]
                    if not isinstance(rarity_value, str):
                        errors.append(f"Item '{item['name']}' at {path} has non-string 'rarity'.")
                        continue
                    
                    # drop block & weight
                    drop_block = item["drop"]
                    if not isinstance(drop_block, dict):
                        errors.append(
                            f"Item '{item[name]}' at {path} has 'drop' that is not an object."
                        )
                        continue
                    
                    weight = drop_block.get("weight")
                    if not isinstance(weight, (int, float)):
                        errors.append(
                            f"Item '{item['name']}' at {path} has invalid drop.weight "
                            f"(must be a number)."
                        )
                        continue
                    if weight < 0:
                        errors.append(
                            f"Item '{item['name']}' at {path} has non-positive "
                            f"drop.weight ({weight})."
                        )
                        continue
                    
                    # If we reach here, the item is strucurally valid
                    total_items += 1
                    rarity_counts[rarity_value] = rarity_counts.get(rarity_value, 0) + 1
                    category_counts[category_name] += 1
                    item_type_counts[item_type_name] += 1
                    
                    # Tags
                    tags_list = item.get("tags", [])
                    if isinstance(tags_list, list):
                        for t in tags_list:
                            if isinstance(t, str):
                                tag_counts[t] = tag_counts.get(t, 0) + 1
                    
                    # Stats
                    stats_block = item.get("stats", {})
                    if isinstance(stats_block, dict):
                        stat_totals_by_rarity.setdefault(rarity_value, {})
                        stat_counts_by_rarity[rarity_value] = (
                            stat_counts_by_rarity.get(rarity_value, 0) + 1
                        )
                        for stat_name, value in stats_block.items():
                            if isinstance(value, (int, float)):
                                stat_totals_by_rarity[rarity_value][stat_name] = (
                                    stat_totals_by_rarity[rarity_value].get(stat_name, 0) + value
                                )
    
    # 3. Compute rarity percentages
    rarity_percentages: Dict[str, float] = {}
    if total_items > 0:
        for r, count in rarity_counts.items():
            rarity_percentages[r] = round((count / total_items) * 100, 2)
        else:
            warnings.append("No valid items found in imported loot table.")
    
    # 4. Compute stat averages per rarity
    rarity_stat_averages: Dict[str, Dict[str, float]] = {}
    for rarity_value, totals in stat_totals_by_rarity.items():
        count_items = stat_counts_by_rarity.get(rarity_value, 0)
        if count_items > 0:
            rarity_stat_averages[rarity_value] = {
                stat_name: round(total / count_items, 2)
                for stat_name, total in totals.items()
            }

    # 5. Generic warnings about typical rarities (non-fatal)
    typical_rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
    for r in typical_rarities:
        if r not in rarity_counts:
            warnings.append(
                f"Rarity '{r}' was not found. If you use custom tiers, you can ignore this."
            )

    valid = len(errors) == 0

    return {
        "name": name,
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "total_items": total_items,
            "rarity_counts": rarity_counts,
            "rarity_percentages": rarity_percentages,
            "category_counts": category_counts,
            "item_type_counts": item_type_counts,
        },
        "tag_population": dict(
            sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        "rarity_stat_averages": rarity_stat_averages,
    }

#=============================================================================================
# Balance Suggestions
#=============================================================================================

@app.post(
    "/balance/suggestions",
    tags=["Balance Tools"],
    summary="Loot balancing recommendation engine",
    description="AI logic provides suggestions based on rarity, tags, type diversity.",
)
def balance_suggestions(req: BalanceRequest):
    rng = get_rng(req.seed)

    # Pull items
    items = extract_all_items(LOOT_TABLE)

    # Run sim
    drops = simulate_drops(items, rng, req.simulations)

    # Count structures
    rarity_count = {}
    tag_count = {}
    type_count = {}

    for item in drops:
        rarity = item["rarity"]
        rarity_count[rarity] = rarity_count.get(rarity, 0) + 1

        for t in item.get("tags", []):
            tag_count[t] = tag_count.get(t, 0) + 1

        i_type = item["type"].lower()
        type_count[i_type] = type_count.get(i_type, 0) + 1

    # Convert rarity to %
    rarity_percent = {
        r: round((n / req.simulations) * 100, 2)
        for r, n in rarity_count.items()
    }

    suggestions = []

    # 1. rarity curve expectations:
    expected = {
        "Common": 70,
        "Uncommon": 20,
        "Rare": 7,
        "Epic": 2.5,
        "Legendary": 0.5
    }

    for rarity, exp_val in expected.items():
        current = rarity_percent.get(rarity, 0)
        delta = round(current - exp_val, 2)

        if abs(delta) > 0.5:
            if delta > 0:
                suggestions.append(
                    f"{rarity} rarity appears too frequently (+{delta}%). "
                    f"Reduce weight values."
                )
            else:
                suggestions.append(
                    f"{rarity} rarity appears too rarely ({delta}%). "
                    f"Increase weight values or add more items."
                )

    # 2. tag imbalance warnings
    melee = tag_count.get("melee", 0)
    caster = tag_count.get("caster", 0)

    if melee > 0 and caster > 0:
        ratio = max(melee, caster) / min(melee, caster)
        if ratio >= 4:
            dominant = "melee" if melee > caster else "caster"
            suggestions.append(
                f"{dominant} items appearing disproportionately (ratio {ratio:.1f})."
            )

    # 3. category starvation
    for cat, count in type_count.items():
        pct = (count / req.simulations) * 100
        if pct < 1:
            suggestions.append(
                f"{cat} category extremely rare ({pct:.2f}%). "
                f"Check weights or add additional gear."
            )

    # 4. legendary issues
    leg = rarity_percent.get("Legendary", 0)
    if leg < 0.25:
        suggestions.append("Legendary may be dropping too rarely for fun experience.")

    # 5. no suggestions safety
    if not suggestions:
        suggestions.append("Loot table appears balanced based on simulation.")

    return {
        "simulations": req.simulations,
        "rarity_distribution": rarity_percent,
        "tag_distribution": tag_count,
        "type_distribution": type_count,
        "suggestions": suggestions
    }

#===================================================================
# Balance Reweight
#===================================================================

@app.post("/balance/reweight",
          tags=["Balance Tools"],
          summary="Analyze imbalance + calculate weight multipliers",
          description="Provide rarity percentage targets. Total may be > or < 100, tool normalizes internally.")

def balance_reweight(req: ReweightRequest):
    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")

    rng = get_rng(req.seed)
    items = extract_all_items(LOOT_TABLE)

    # -------------------------------
    # Step 1: simulate natural rarity
    # -------------------------------

    drops = simulate_drops(items, rng, req.simulations)

    rarity_counts = {}
    for item in drops:
        r = item["rarity"]
        rarity_counts[r] = rarity_counts.get(r, 0) + 1

    current_dist = {
        r: round((n / req.simulations) * 100, 4)
        for r, n in rarity_counts.items()
    }

    # -------------------------------
    # Step 2: extract target rarity
    # -------------------------------
    raw_target = req.target_rarity

    # Missing rarity protection
    rarity_keys = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

    for key in rarity_keys:
        if key not in raw_target:
            raw_target[key] = current_dist.get(key, 0)

    # -------------------------------
    # Step 3: normalize target rarity
    # -------------------------------

    raw_total = sum(raw_target.values())

    normalized = {
        r: round((v / raw_total) * 100, 4)
        for r, v in raw_target.items()
    }

    # -------------------------------
    # Step 4: multiplier math
    # -------------------------------

    multipliers = {}
    delta_analysis = {}

    for rarity, current in current_dist.items():
        t = normalized[rarity]

        delta = round(t - current, 4)

        if current == 0:
            multipliers[rarity] = 0
        else:
            multipliers[rarity] = round(t / current, 4)

        delta_analysis[rarity] = {
            "current_percent": current,
            "normalized_target_percent": t,
            "delta": delta,
            "recommended_multiplier": multipliers[rarity],
        }

    # -------------------------------
    # Step 5: warnings
    # -------------------------------

    warnings = []

    if abs(raw_total - 100) > 0.01:
        warnings.append(
            f"Target input total was {raw_total}%. Targets were normalized to 100%."
        )

    recommended_ranges = {
        "Common": (50, 75),
        "Uncommon": (15, 35),
        "Rare": (5, 12),
        "Epic": (1, 4),
        "Legendary": (0.1, 1),
    }

    for rarity, (low, high) in recommended_ranges.items():
        t = normalized[rarity]
        if t < low:
            warnings.append(
                f"{rarity} target {t}% is below recommended minimum {low}%."
            )
        if t > high:
            warnings.append(
                f"{rarity} target {t}% exceeds recommended maximum {high}%."
            )

    return {
        "simulations": req.simulations,
        "current_distribution": current_dist,
        "normalized_target_distribution": normalized,
        "recommended_multiplier_values": multipliers,
        "rarity_analysis": delta_analysis,
        "warnings": warnings
    }

#============================================================================
# Balance Export
#============================================================================

@app.post(
    "/balance/export",
    tags=["Export Tools"],
    summary="Modify table weights + export",
    description="Returns a downloadable loot table JSON with adjusted weights."
)
def balance_export(req: ExportRequest):
    
    # Step 1: deep copy loot table
    new_table = deepcopy(LOOT_TABLE)
    
    rarity_keys = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
    
    # Step 2. validate input
    for rarity, mult in req.multipliers.items():
        if rarity not in rarity_keys:
            raise HTTPException(
                400,
                f"Invalid rarity multiplier: {rarity}"
            )
        if mult <= 0:
            raise HTTPException(
                400,
                "Multiplier must be > 0"
            )
    
    # Step 3. apply multiplier
    for category in new_table.values():
        for type_group in category.values():
            for rarity, items in type_group.items():
                multiplier = req.multipliers.get(rarity, 1.0)
                
                for item in items:
                    old_weight = item["drop"]["weight"]
                    new_weight = int(round(old_weight * multiplier))
                    
                    # prevent zero removal
                    if new_weight < 1:
                        new_weight = 1
                        
                    item["drop"]["weight"] = new_weight
    
    # Step 4: return downloable file
    return JSONResponse(
        content=new_table,
        headers={
            "Content-Disposition": "attachment; filename=new_loot_table.json"
        }
    )

#==============================================================================
# Balance Export Simple
#==============================================================================

@app.post(
    "/balance/export/simple",
    tags=["Export Tools"],
    summary="Return rarity multipliers only",
    description="Useful for lightweight client integrations & mobile applications."
)
def export_simple(req: ExportRequest):
    """
    Returns updated rarity multipliers only.
    Safe output for beginners and mobile clients.
    """
    
    return {
        "success": True,
        "rarity_weights": req.multipliers
    }

#=============================================================================
# Balance Export Full
#=============================================================================

@app.post(
    "/balance/export/full",
     tags=["Export Tools"],
    summary="Return fully rewritten loot table",
    description="Produces a complete new loot table instance reflecting rarity weight changes."
)
def export_full(req: ExportRequest):
    """
    Applies rarity multipliers to loot table and returns a modified json structure.
    """
    global LOOT_TABLE

    multipliers = req.multipliers

    # Soft copy to preserve original
    new_table = copy.deepcopy(LOOT_TABLE)
    
    # walk categories -> types -> rarity -> items
    for category, types in new_table.items():
        for item_type, rarities in types.items():
            for rarity, items in rarities.items():
                
                # if multiplier missing -> skip
                if rarity not in multipliers:
                    continue
                
                multiplier = multipliers[rarity]
                
                for item in items:
                    # get old weight
                    old_weight = item["drop"]["weight"]
                    
                    # multiply
                    new_weight = old_weight * multiplier
                    
                    # safety clamp minimum
                    if new_weight < 1:
                        new_weight = 1
                    
                    # round
                    item["drop"]["weight"] = round(new_weight)
    
    return {
        "success": True,
        "updated_loot_table": new_table
    }
    