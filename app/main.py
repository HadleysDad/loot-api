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

    rarity_dist = {
        k: round((v / req.simulations) * 100, 2)
        for k, v in rarity_counts.items()
    }

    def top_rarity(r):
        return sorted(
            [
                (n, c)
                for n, c in item_counts.items()
                if item_rarity[n] == r
            ],
            key=lambda x: x[1],
            reverse=True,
        )[:3]

    warnings = []

    if rarity_dist.get("Legendary", 0) < 0.5:
        warnings.append("Legendary appearance extremely low (<0.5%)")

    return {
        "simulations": req.simulations,
        "rarity_distribution": rarity_dist,
        "top_overall": sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        "top_rare": top_rarity("Rare"),
        "top_legendary": top_rarity("Legendary"),
        "warnings": warnings,
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
    for d in drops:
        rarity_counts[d["rarity"]] = rarity_counts.get(d["rarity"], 0) + 1

    rarity_dist = {
        k: round((v / req.simulations) * 100, 2)
        for k, v in rarity_counts.items()
    }

    return {
        "luck": luck,
        "simulations": req.simulations,
        "rarity_distribution": rarity_dist,
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
