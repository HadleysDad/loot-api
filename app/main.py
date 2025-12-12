from fastapi import FastAPI, HTTPException
from loot_loader import LOOT_TABLE
from drop_engine import extract_all_items, roll_from_items
from rng import get_rng
from schemas import DropRequest, CategoryDropRequest, RarityDropRequest, TagSearchRequest, TagDropRequest

app = FastAPI(
    title="Loot Table API",
    description="Random loot generator for game developers. Includes massive fantasy loot table",
    version="1.0.0"
)

# Health endpoint
@app.get("/health", tags=["Health"])
def health_check():
    return {"Status": "Ok"}

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

@app.post("/items/list")
def list_items():
    from loot_loader import LOOT_TABLE
    return LOOT_TABLE

@app.post("/items/by-tag/{tag}")
def items_by_tag(tag: str):
    from drop_engine import extract_items_by_tag
    items = extract_items_by_tag(LOOT_TABLE, tag)
    return {
        "tag": tag,
        "count": len(items),
        "items": items
    }

@app.post("/items/by-tags")
def items_by_tags(req: TagSearchRequest):
    from drop_engine import extract_items_by_tags
    items = extract_items_by_tags(LOOT_TABLE, req.tags)
    return {
        "tags": req.tags,
        "count": len(items),
        "items": items
    }

@app.post("/drop/by-tag/{tag}")
def drop_by_tag(tag: str, seed: int | None = None):
    from drop_engine import extract_items_by_tag, roll_from_items
    from rng import get_rng
    
    items = extract_items_by_tag(LOOT_TABLE, tag)
    if not items:
        raise HTTPException(400, "No items found for this tag")
    
    rng = get_rng(seed)
    return roll_from_items(items, rng)

@app.post("/drop/by-tag")
def drop_by_tags(req: TagDropRequest):
    from drop_engine import extract_items_by_tags, roll_from_items
    from rng import get_rng
    
    items = extract_items_by_tags(LOOT_TABLE, req.tags)
    if not items:
        raise HTTPException(400, "No items match these tags")

@app.post("/simulate/by-tag/{tag}")
def simulate_by_tag(tag: str, simulations: int = 1000):
    from drop_engine import extract_items_by_tag
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
