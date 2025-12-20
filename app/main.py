from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any

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
@app.get("/info", response_model=dict)
def info():
    return {
        "name": "Loot Table API",
        "version": "3.0.0",
        "item_count": len(extract_all_items(LOOT_TABLE)),
        "categories": list(LOOT_TABLE.key()),
        "author": "Your Name",
        "license": "Commercial",
    }

@app.get("/tags", response_model=List[str])
def list_tags():
    tags = set()
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    tags.update(item.get("tags", []))
    return sorted(tags)


@app.get("/stats", response_model=List[str])
def list_stats():
    stats = set()
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    stats.update(item.get("stats", {}).keys())
    return sorted(stats)


@app.get("/categories", response_model=List[str])
def list_categories():
    return list(LOOT_TABLE.keys())

@app.get("/schema", response_model=dict)
def schema():
    return LOOT_TABLE


# ============================================================
# ITEM SEARCH
# ============================================================

@app.post("/items/by-tag/{tag}", response_model=dict)
def items_by_tag(tag: str):
    items = extract_items_by_tag(LOOT_TABLE, tag)
    return {
        "tag": tag,
        "count": len(items),
        "items": items,
    }


@app.post("/items/by-tags", response_model=dict)
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

@app.post("/drop", response_model=dict)
def drop_any(req: DropRequest):
    rng = get_rng(req.seed)
    items = extract_all_items(LOOT_TABLE)
    return {"drop": roll_from_items(items, rng)}


@app.post("/drop/by-category", response_model=dict)
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


@app.post("/drop/by-rarity", response_model=dict)
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


@app.post("/drop/by-tag/{tag}", response_model=dict)
def drop_by_tag(tag: str, seed: int | None = None):
    items = extract_items_by_tag(LOOT_TABLE, tag)

    if not items:
        raise HTTPException(400, "No items contain this tag")

    rng = get_rng(seed)
    return {"tag": tag, "drop": roll_from_items(items, rng)}


@app.post("/drop/by-tags", response_model=dict)
def drop_by_tags(req: TagDropRequest):
    items = extract_items_by_tags(LOOT_TABLE, req.tags)

    if not items:
        raise HTTPException(400, "No items match these tags")

    rng = get_rng(req.seed)
    return {"tags": req.tags, "drop": roll_from_items(items, rng)}


@app.post("/drop/with-luck", response_model=dict)
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

@app.get("/legenday-preview", response_model=dict)
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

@app.post("/simulate", response_model=dict)
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

@app.post("/simulate/with-luck", response_model=dict)
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

@app.post("/simulate/compare", response_model=dict)
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

@app.get("/balance/overview", response_model=dict)
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

#=============================================================================================
# Balance Suggestions
#=============================================================================================

@app.post("/balance/suggestions")
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

app.post("/balance/reweight")
def balance_reweight(req: ReweightRequest):
    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")

    rng = get_rng(req.seed)
    
    # Get loot
    items = extract_all_items(LOOT_TABLE)
    
    # Run simulation to see current natural distribution
    drops = simulate_drops(items, rng, req.simulations)
    
    # Count rarity
    rarity_counts = {}
    for item in drops:
        r = item["rarity"]
        rarity_counts[r] = rarity_counts.get(r, 0) + 1
    
    current_dist = {
        r: round((n / req.simulations) * 100, 3)
        for r, n in rarity_counts.items()
    }
    
    # Build response structure:
    # if not target rarity provided, return current
    imbalance = {}
    multipliers = {}
    
    for rarity, current in current_dist.items():
        target = req.target_rarity.get(rarity, None)

        if target is None:
            imbalance[rarity] = {
                "error": f"Missing target for rarity {rarity}"
            }
            continue

        # Percent difference (+/-)
        delta = round(target - current, 3)

        # Multiplier formula
        # if target > current → scale up weight
        # if target < current → scale down weight
        if current == 0:
            multiplier = 0
        else:
            multiplier = round(target / current, 3)

        imbalance[rarity] = {
            "current_percent": current,
            "target_percent": target,
            "delta": delta,
        }

        multipliers[rarity] = multiplier

    return {
        "simulations": req.simulations,
        "current_distribution": current_dist,
        "target_distribution": req.target_rarity,
        "suggested_weight_multiplier": multipliers,
        "analysis": imbalance
    }
        
        