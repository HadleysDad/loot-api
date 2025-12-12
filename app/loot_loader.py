import json
from pathlib import Path

LOOT_TABLE_PATH = Path(__file__).parent / "loot_table.json"

with open(LOOT_TABLE_PATH, "r") as f:
    LOOT_TABLE = json.load(f)