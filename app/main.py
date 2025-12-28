from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
import copy
from copy import deepcopy
from fastapi.responses import JSONResponse

from app.autocorrect_engine import (
    generate_autocorrect_preview, 
    build_autocorrect_diff, 
    get_profile_capabilities, 
    apply_autocorrect,
)

from app.import_validator import validate_loot_table
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
    ExportcorrectRequest,
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
        "Upload your own loot table JSON and receive:\n"
        "- Structural validation (errors & warnings)\n"
        "- Rarity, category, and tag summaries\n"
        "- Auto-correct preview (SAFE / AGGRESSIVE / STRICT)\n"
        "- Optional SAFE auto-correction (non-destructive)\n\n"
        "This endpoint NEVER modifies the stored loot table."
    ),
)
def balance_test_import(req: ImportTestRequest):
    # --------------------------------------------------
    # 1. Run validation
    # --------------------------------------------------
    validation_result = validate_loot_table(req.loot_table)

    # --------------------------------------------------
    # 2. Generate auto-correct preview (non-destructive)
    # --------------------------------------------------
    preview = generate_autocorrect_preview(
        loot_table=req.loot_table,
        validation_result=validation_result,
        profile=req.auto_correct_profile or "safe",
    )
    
    capabilities = get_profile_capabilities(preview["profile"])
    diff_only = build_autocorrect_diff(preview)

    # --------------------------------------------------
    # 3. Optionally apply SAFE auto-corrections
    # --------------------------------------------------
    safe_apply_result = None

    if req.apply_safe_fixes:
        if preview["profile"] != "safe":
            # Guardrail: SAFE apply only
            safe_apply_result = {
                "applied": False,
                "reason": "Only SAFE profile can be applied automatically."
            }
        else:
            safe_apply_result ={
                "applied": True,
                "corrected_loot_table": apply_autocorrect(
                    loot_table=req.loot_table,
                    preview=preview
                )
            }
    # --------------------------------------------------
    # 4. Assemble response
    # --------------------------------------------------
    return {
        "name": req.name or "imported_loot_table",
        "valid": validation_result["valid"],
        "errors": validation_result["errors"],
        "warnings": validation_result["warnings"],
        "summary": validation_result["summary"],
        "compatibility": validation_result.get("compatibility", {}),
        "auto_correct_preview": preview,
        "auto_correct_diff": diff_only,
        "profile_capabilities": capabilities,
        "safe_auto_correct": {
            "requested": req.apply_safe_fixes,
            "applied": safe_apply_result is not None 
                        and safe_apply_result.get("applied_fix_count", 0) > 0,
            "result": safe_apply_result,
        },
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

#======================================================================
# Export Corrected
#======================================================================

@app.post(
    "/balance/export/corrected",
    tags=["Balance Tools"],
    summary="Exports corrected loot table using auto-correct profiles",
    description=(
        "Validate and auto-correct a custom loot table, then export a corrected JSON.\n\n"
        "Profiles:\n"
        "- SAFE: minimal fixes only (free)\n"
        "- STRICT: no corrections, validation only\n"
        "- AGGRESSIVE: advanced balancing (paid)"
    ),
)
def export_corrected_loot_table(req: ExportcorrectRequest):
    # 1. Validate first
    validation = validate_loot_table(req.loot_table)
    
    if not validation["valid"] and req.auto_correct_profile == "strict":
        raise HTTPException(
            status_code=400,
            detail="STRICT profile does not allow exporting invalid loot tables."
        )
    
    if req.auto_correct_profile != "safe":
        raise HTTPException(
            status_code=403,
            detail="Only SAFE auto-correct profile can be applied automatically."
        )
        
    # 2. Apply auto-correct
    try:
        preview = generate_autocorrect_preview(
            loot_table=req.loot_table,
            validation_result=validation,
            profile=req.auto_correct_profile,
        )
        
        corrected = apply_autocorrect(
            loot_table=req.loot_table,
            preview=preview,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # 3. Return export
    return {
        "name": req.name or "corrected_loot_table",
        "profile": req.auto_correct_profile,
        "valid": validation["valid"],
        "warnings": validation["warnings"],
        "exported_loot_table": corrected,
    }