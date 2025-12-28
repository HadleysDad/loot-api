RARITY_KEYS = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

# Fatal erros = table not safe to run core features
FATAL_MISSING_ITEM_FIELDS = ["name", "rarity", "type", "drop"]
FATAL_DROP_FIELDS = ["weight"]

# Soft warnings = safe, but imperfect / not best practice
OPTIONAL_FIELDS = ["tags", "stats", "passive"]

AUTO_CORRECT_PROFILES = {
    "safe": {
        "fix_weight": True,
        "normalize_rarity": True,
        "clean_tags": True,
        "clean_stats": True,
        "fill_optional_fields": True,
        "reassign_rarity": False,
    },
    "aggressive": {
        "fix_weight": True,
        "normalize_rarity": True,
        "clean_tags": True,
        "clean_stats": True,
        "fill_optional_fields": True,
        "reassign_rarity": True,
        "merge_duplicates": True,
    },
    "strict": {
        "fix_weight": True,
        "normalize_rarity": True,
        "clean_tags": False,
        "clean_stats": False,
        "fill_optional_fields": False,
        "reassign_rarity": False,
    },
}