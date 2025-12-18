from fastapi import FastAPI, HTTPException
from app.loot_loader import LOOT_TABLE
from app.drop_engine import extract_all_items, roll_from_items
from app.rng import get_rng
from app.drop_engine import extract_all_items, extract_items_by_tag, extract_items_by_tags, roll_from_items, simulate_drops, apply_luck
from app.schemas import DropRequest, CategoryDropRequest, RarityDropRequest, TagSearchRequest, TagDropRequest, SimulationRequest, LuckDropRequest, LuckSimulateRequest, CompareSimulationRequest

app = FastAPI(
    title="Loot Table API",
    description="Random loot generator for game developers. Includes massive fantasy loot table",
    version="1.0.0"
)

# Health endpoint
@app.get("/health", tags=["Health"])
def health_check():
    return {"Status": "Ok"}


@app.get("/tags")
def list_tags():
    tags = set()
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    tags.update(item.get("tags", []))
    return sorted(tags)

@app.get("/stats")
def list_stats():
    stats = set()
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    stats.update(item.get("stats", {}).keys())
    return sorted(stats)

@app.get("/categories")
def list_categories():
    return list(LOOT_TABLE.keys())

    
@app.post("/items/by-tag/{tag}")
def items_by_tag(tag: str):
    items = extract_items_by_tag(LOOT_TABLE, tag)
    return {
        "tag": tag,
        "count": len(items),
        "items": items
    }

@app.post("/items/by-tags")
def items_by_tags(req: TagSearchRequest):
    items = extract_items_by_tags(LOOT_TABLE, req.tags)
    return {
        "tags": req.tags,
        "count": len(items),
        "items": items
    }
    
@app.post("/drop/with-luck")
def drop_with_luck(req: LuckDropRequest):
    # Clamp luck to a safe range
    luck = max(0.0, min(req.luck, 1.0))
    
    rng = get_rng(req.seed)
    
    # Select items
    if req.tags:
        items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not items:
            raise HTTPException(400, "No items match provided tags")
    else:
        items = extract_all_items(LOOT_TABLE)
        
    # Apply luck
    adjusted_items = apply_luck(items, luck)
        
    # Roll
    return roll_from_items(adjusted_items, rng)

#--------------DROP--------------

@app.post("/drop")
def drop_any(req: DropRequest):
    rng = get_rng(req.seed)
    items = extract_all_items(LOOT_TABLE)
    return roll_from_items(items, rng)

@app.post("/drop/by-category")
def drop_by_category(req: CategoryDropRequest):
    category = req.category.lower()
    if category not in LOOT_TABLE:
        raise HTTPException(400, "Invalid Category")
    
    rng = get_rng(req.seed)
    
    items = []
    for item_type in LOOT_TABLE[category].values():
        for rarity_items in item_type.values():
            items.extend(rarity_items)
            
    return roll_from_items(items, rng)

@app.post("/drop/by-rarity")
def drop_by_rarity(req: RarityDropRequest):
    rarity = req.rarity.lower()
    rng = get_rng(req.seed)
    
    items = []
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            items.extend(item_type.get(rarity, []))
    
    if not items:
        raise HTTPException(400, "No items found for that rarity")
    
    return roll_from_items(items, rng)


@app.post("/drop/by-tag/{tag}")
def drop_by_tag(tag: str, seed: int | None = None):
    items = extract_items_by_tag(LOOT_TABLE, tag)
    if not items:
        raise HTTPException(400, "No items found for this tag")
    
    rng = get_rng(seed)
    return roll_from_items(items, rng)

@app.post("/drop/by-tags")
def drop_by_tags(req: TagDropRequest):
    items = extract_items_by_tags(LOOT_TABLE, req.tags)
    if not items:
        raise HTTPException(400, "No items match these tags")
    
    rng = get_rng(req.seed)
    return roll_from_items(items, rng)

#-----------------SIMULATE-----------------------
@app.post("/simulate")
def simulate(req: SimulationRequest):
    rng = get_rng(req.seed)

    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")

    # 1. Select items
    if req.tags:
        items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not items:
            raise HTTPException(400, "No items match provided tags")
    else:
        items = extract_all_items(LOOT_TABLE)

    # 2. Run simulation
    drops = simulate_drops(items, rng, req.simulations)

    # 3. Analyze results
    rarity_counts = {}
    tag_counts = {}
    item_counts = {}
    item_rarity = {}

    for item in drops:
        rarity = item["rarity"]
        name = item["name"]

        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
        item_counts[name] = item_counts.get(name, 0) + 1
        item_rarity[name] = rarity

        for tag in item.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    rarity_distribution = {
        k: round((v / req.simulations) * 100, 2)
        for k, v in rarity_counts.items()
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

    # 4. Warnings
    warnings = []

    legendary_rate = rarity_distribution.get("Legendary", 0)
    epic_rate = rarity_distribution.get("Epic", 0)
    rare_rate = rarity_distribution.get("Rare", 0)

    if legendary_rate < 0.5:
        warnings.append("Legendary items drop less than 0.5% of the time.")
    if legendary_rate > 2.0:
        warnings.append("Legendary items drop more than 2% of the time.")
    if epic_rate > 10:
        warnings.append("Epic items account for more than 10% of all drops.")
    if rare_rate < 3:
        warnings.append("Rare items drop less than 3% of the time.")

    if req.simulations < 5000:
        warnings.append("Simulation count may be too low for reliable rare/legendary analysis.")

    # 5. Return
    return {
        "simulations": req.simulations,
        "rarity_distribution": rarity_distribution,
        "top_items_overall": sorted(
            item_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10],
        "top_rare_items": top_by_rarity("Rare"),
        "top_legendary_items": top_by_rarity("Legendary"),
        "tag_distribution": {
            k: round((v / req.simulations) * 100, 2)
            for k, v in tag_counts.items()
        },
        "warnings": warnings
    }


@app.post("/simulate/with-luck")
def simulate_with_luck(req: LuckSimulateRequest):
    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")

    luck = max(0.0, min(req.luck, 1.0))
    rng = get_rng(req.seed)

    # 1. Select items
    if req.tags:
        items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not items:
            raise HTTPException(400, "No items match provided tags")
    else:
        items = extract_all_items(LOOT_TABLE)

    # 2. Apply luck
    adjusted_items = apply_luck(items, luck)

    # 3. Run simulation
    drops = simulate_drops(adjusted_items, rng, req.simulations)

    # 4. Analyze
    rarity_counts = {}
    tag_counts = {}
    item_counts = {}
    item_rarity = {}

    for item in drops:
        rarity = item["rarity"]
        name = item["name"]

        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
        item_counts[name] = item_counts.get(name, 0) + 1
        item_rarity[name] = rarity

        for tag in item.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    rarity_distribution = {
        k: round((v / req.simulations) * 100, 2)
        for k, v in rarity_counts.items()
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

    # 5. Warnings
    warnings = []

    legendary_rate = rarity_distribution.get("Legendary", 0)
    epic_rate = rarity_distribution.get("Epic", 0)
    rare_rate = rarity_distribution.get("Rare", 0)

    if legendary_rate < 0.5:
        warnings.append("Legendary items drop less than 0.5% of the time.")
    if legendary_rate > 2.0:
        warnings.append("Legendary items drop more than 2% of the time.")
    if epic_rate > 10:
        warnings.append("Epic items account for more than 10% of all drops.")
    if rare_rate < 3:
        warnings.append("Rare items drop less than 3% of the time.")

    if req.simulations < 5000:
        warnings.append("Simulation count may be too low for reliable rare/legendary analysis.")

    # 6. Return
    return {
        "simulations": req.simulations,
        "luck": luck,
        "rarity_distribution": rarity_distribution,
        "top_items_overall": sorted(
            item_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10],
        "top_rare_items": top_by_rarity("Rare"),
        "top_legendary_items": top_by_rarity("Legendary"),
        "tag_distribution": {
            k: round((v / req.simulations) * 100, 2)
            for k, v in tag_counts.items()
        },
        "warnings": warnings
    }

@app.post("/simulate/compare")
def simulate_compare(req: CompareSimulationRequest):
    if req.simulations > 100_000:
        raise HTTPException(400, "Simulation limit exceeded")
    
    luck = max(0.0, min(req.luck, 1.0))
    
    # Use SAME seed for fair comparison
    rng_base = get_rng(req.seed)
    rng_luck = get_rng(req.seed)
    
    # 1. Select items
    if req.tags:
        items = extract_items_by_tags(LOOT_TABLE, req.tags)
        if not items:
            raise HTTPException(400, "No items match provided tags")
    else:
        items = extract_all_items(LOOT_TABLE)
    
    # 2. Prepare luck-adjusted items
    luck_items = apply_luck(items, luck)
    
    # 3. Run simulation
    drops_base = simulate_drops(items, rng_base, req.simulations)
    drops_luck = simulate_drops(luck_items, rng_luck, req.simulations)
    
    def analyze(drops):
        rarity_counts = {}
        item_counts = {}
        
        for item in drops:
            rarity = item["rarity"]
            name = item["name"]
            
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
            item_counts[name] = item_counts.get(name, 0) + 1
        
        rarity_distribution = {
            k: round((v / req.simulations) * 100, 2)
            for k, v in rarity_counts.items()
        }
        
        return rarity_distribution, item_counts
    
    base_rarity, base_items = analyze(drops_base)
    luck_rarity, luck_items_counts = analyze(drops_base)
    
    # 4. Compute deltas
    rarity_delta = {}
    for rarity in set(base_rarity) | set(luck_rarity):
        rarity_delta[rarity] = round(
            luck_rarity.get(rarity, 0) - base_rarity.get(rarity, 0),
            2
        )
    
    # 5. Top movers (items that gain most)
    item_delta = []
    for name in base_items:
        delta = luck_items_counts.get(name, 0) - base_items.get(name, 0)
        if delta != 0:
            item_delta.append((name, delta))
    
    top_gainers = sorted(item_delta, key=lambda x: x[1], reverse=True)[:5]
    top_losers = sorted(item_delta, key=lambda x: x[1])[:5]
    
    return {
        "simulations": req.simulations,
        "luck": luck,
        "tags": req.tags,
        "rarity_distribution": {
            "base": base_rarity,
            "with_luck": luck_rarity,
            "delta": rarity_delta
        },
        "tot_item_changes": {
            "gained": top_gainers,
            "lost": top_losers
        }
    } 