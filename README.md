## UNFINNISHED README


## Example Loot Tables

You can test the API using the provided example loot tables:

- [Minimal Loot TAble](./examples/minimal_loot_table.json)
- [Full RPG Loot Table](./examples/full_rpg_loot_table.json)
- [Broken Loot Table (Validation Demo)](./examples/broken_loot_table.json)

Use these with the `/balance/test-import` endpoint.

## Example Request
POST /balance/test-import
Body:
{
    "name": "MyGameLoot",
    "loot_table": {
        "Weapons": {
            "sword_1h": {
                "Common": [
                    {
                        "name": "Rusty Sword",
                        "rarity": "Common",
                        "type": "weapon_sword_1h",
                        "tags": ["melee"],
                        "stats": {"attack": 5},
                        "drop": {"weight": 100}
                    }
                ]
            }
        }
    }
}
