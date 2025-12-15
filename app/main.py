from fastapi import FastAPI, HTTPException
from app.loot_loader import LOOT_TABLE
from app.drop_engine import extract_all_items, roll_from_items
from app.rng import get_rng
from app.schemas import DropRequest, CategoryDropRequest, RarityDropRequest, TagSearchRequest, TagDropRequest, SimulationRequest, LuckDropRequest

app = FastAPI(
    title="Loot Table API",
    description="Random loot generator for game developers. Includes massive fantasy loot table",
    version="1.0.0"
)

# Health endpoint
@app.get("/health", tags=["Health"])
def health_check():
    return {"Status": "Ok"}

@app.post("/items/list")
def list_items():
    from app.loot_loader import LOOT_TABLE
    return LOOT_TABLE

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
    from app.drop_engine import extract_items_by_tag
    items = extract_items_by_tag(LOOT_TABLE, tag)
    return {
        "tag": tag,
        "count": len(items),
        "items": items
    }

@app.post("/items/by-tags")
def items_by_tags(req: TagSearchRequest):
    from app.drop_engine import extract_items_by_tags
    items = extract_items_by_tags(LOOT_TABLE, req.tags)
    return {
        "tags": req.tags,
        "count": len(items),
        "items": items
    }
    
@app.post("/drop/with-luck")
def drop_with_luck(req: LuckDropRequest):
    from app.drop_engine import (
        extract_all_items,
        extract_items_by_tags,
        roll_from_items,
        apply_luck
    )
    from app.rng import get_rng
    
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

@app.post("/drop/legendary-only")
def drop_legendary(req: DropRequest):
    rng = get_rng(req.seed)
    
    items = []
    for category in LOOT_TABLE.values():
        for item_type in category.values():
            items.extend(item_type["legendary"])
            
    return roll_from_items(items, rng)



@app.post("/drop/by-tag/{tag}")
def drop_by_tag(tag: str, seed: int | None = None):
    from app.drop_engine import extract_items_by_tag, roll_from_items
    from app.rng import get_rng
    
    items = extract_items_by_tag(LOOT_TABLE, tag)
    if not items:
        raise HTTPException(400, "No items found for this tag")
    
    rng = get_rng(seed)
    return roll_from_items(items, rng)

@app.post("/drop/by-tags")
def drop_by_tags(req: TagDropRequest):
    from app.drop_engine import extract_items_by_tags, roll_from_items
    from app.rng import get_rng
    
    items = extract_items_by_tags(LOOT_TABLE, req.tags)
    if not items:
        raise HTTPException(400, "No items match these tags")
    
    rng = get_rng(req.seed)
    return roll_from_items(items, rng)

#-----------------SIMULATE-----------------------
@app.post("/simulate")
def simulate(req: SimulationRequest):
    from app.drop_engine import (
        extract_all_items,
        extract_items_by_tags,
        simulate_drops
    )
    from app.rng import get_rng

    rng = get_rng(req.seed)

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

    for item in drops:
        rarity = item["rarity"]
        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1

        for tag in item.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        name = item["name"]
        item_counts[name] = item_counts.get(name, 0) + 1

    rarity_distribution = {
        k: round((v / req.simulations) * 100, 2)
        for k, v in rarity_counts.items()
    }

    # 4. Generate warnings
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

    melee_count = tag_counts.get("melee", 0)
    caster_count = tag_counts.get("caster", 0)

    if melee_count and caster_count:
        ratio = max(melee_count, caster_count) / min(melee_count, caster_count)
        if ratio >= 3:
            dominant = "melee" if melee_count > caster_count else "caster"
            warnings.append(
                f"{dominant.capitalize()} items appear significantly more often than the opposite playstyle."
            )

    for element in ["fire", "frost", "arcane", "holy", "shadow", "poison"]:
        element_rate = (tag_counts.get(element, 0) / req.simulations) * 100
        if 0 < element_rate < 5:
            warnings.append(f"{element.capitalize()} items appear in less than 5% of drops.")

    for name, count in item_counts.items():
        percent = (count / req.simulations) * 100
        if percent > 5:
            warnings.append(f'Item "{name}" accounts for more than 5% of all drops.')

    if req.simulations < 5000:
        warnings.append("Simulation count may be too low for reliable rare/legendary analysis.")

    # 5. Always return
    return {
        "simulations": req.simulations,
        "rarity_distribution": rarity_distribution,
        "top_items": sorted(
            item_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10],
        "tag_distribution": {
            k: round((v / req.simulations) * 100, 2)
            for k, v in tag_counts.items()
        },
        "warnings": warnings
    }

@app.post("/simulate/by-tag/{tag}")
def simulate_by_tag(tag: str, simulations: int = 1000):
    from app.drop_engine import extract_items_by_tag
    import random
    
    items = extract_items_by_tag(LOOT_TABLE, tag) 
    if not items:
        raise HTTPException(400, "No items found for this tag")
    
    results = {}
    for _ in range(simulations):
        item = random.choice(items)
        name = item["name"]
        results[name] = results.get(name, 0) + 1 
        
    return {
        "tag": tag,
        "simulations": simulations,
        "results": results
    }  


        
        