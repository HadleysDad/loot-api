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
