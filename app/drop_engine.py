def build_pool(items):
    pool = []
    for item in items:
        pool.extend([item] * item["drop"]["weight"])
    return pool


def roll_from_items(items, rng):
    pool = build_pool(items)
    if not pool:
        raise ValueError("Loot pool is empty")
    return rng.choice(pool)


def extract_all_items(loot_table):
    all_items = []
    for category in loot_table.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                all_items.extend(rarity_items)
    return all_items


def extract_items_by_tag(loot_table, tag: str):
    results = []
    for category in loot_table.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    if tag in item.get("tags", []):
                        results.append(item)
    return results


def extract_items_by_tags(loot_table, tags: list[str]):
    results = []
    for category in loot_table.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                for item in rarity_items:
                    item_tags = set(item.get("tags", []))
                    if all(tag in item_tags for tag in tags):
                        results.append(item)
    return results

def simulate_drops(items, rng, simulations: int):
    results = []
    
    for _ in range(simulations):
        pool = []
        for item in items:
            pool.extend([item] * item["drop"]["weight"])
        results.append(rng.choice(pool))
        
    return results

def apply_luck(items, luck: float):
    """
    Adjusts drop weights based on luck.
    Higher rarity benefits more, but nothing is guaranteed.
    """
    
    if luck <= 0:
        return items
    
    rarity_multiplier = {
        "Common": 1.0,
        "Uncommon": 1.0 + (luck * 0.25),
        "Rare": 1.0 + (luck * 0.5),
        "Epic": 1.0 + (luck * 0.75),
        "Legendary": 1.0 + luck,
    }
    
    adjusted_items = []
    
    for item in items:
        rarity = item["rarity"]
        base_weight = item["drop"]["weight"]
        multiplier = rarity_multiplier.get(rarity, 1.0)
        
        adjusted_items.append({
            **item,
            "drop": {
                "weight": max(1, int(base_weight * multiplier))
            }
        })
        
    return adjusted_items