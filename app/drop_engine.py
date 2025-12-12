def build_pool(items):
    pool = []
    for item in items:
        pool.extend([item] * item["drop"]["weight"])
    return pool

def roll_from_items(items, rng):
    pool = build_pool(items)
    return rng.choise(pool)

def extract_all_items(loot_table):
    all_items = []
    for category in loot_table.values():
        for item_type in category.values():
            for rarity_items in item_type.values():
                all_items.extend(rarity_items)
    return all_items