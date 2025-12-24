RARITY_KEYS = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

# Fatal erros = table not safe to run core features
FATAL_MISSING_ITEM_FIELDS = ["name", "rarity", "type", "drop"]
FATAL_DROP_FIELDS = ["weight"]

# Soft warnings = safe, but imperfect / not best practice
OPTIONAL_FIELDS = ["tags", "stats", "passive"]