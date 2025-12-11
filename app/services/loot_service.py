import random
from collections import Counter
from typing import List
from app.models.loot_models import ItemEntry, LootTable

def generate_drop(loot_table: LootTable) -> str:
    """Returns a single random item based on weights."""
    names = [item.name for item in loot_table.items]
    weights = [item.rarity for item in loot_table.items]
    drop = random.choices(names, weights=weights, k=1)[0]
    return drop

def simulate_drops(loot_table: LootTable, simulations: int) -> dict:
    """Simulate multiple drops and return count statistics."""
    results = [generate_drop(loot_table) for _ in range(simulations)]
    counts = Counter(results)
    return dict(counts)

def balance_suggestion(loot_table, simulation_results: dict) -> dict:
    """Suggest balance adjustments for under/overpowered items."""
    total_simulated = sum(simulation_results.values())
    adjustments = {}
    for item in loot_table.items:
        expected = item.rarity * total_simulated
        acutal = simulation_results.get(item.name, 0)
        diff = expected - acutal
        adjustment = item.rarity + (diff / total_simulated)
        adjustments[item.name] = max(min(adjustment, 1.0), 0.01)
    return adjustments 