from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class ItemEntry(BaseModel):
    name: str = Field(..., description="Name of the item")
    rarity: float = Field(..., gt=0, lt=1, description="Probability wieght (0-1)")

class LootTable(BaseModel):
    items: List[ItemEntry] = Field(..., description="List of items with rarity")

class DropResult(BaseModel):
    item: str
    probability: float

class SimulationRequest(BaseModel):
    loot_table: LootTable
    simulations: int = Field(1000, gt=0, description="Number of drops to simulate")
    
class BalanceSuggestion(BaseModel):
    adjustments: Dict[str, float] = Field(..., description="Suggested rarity adjustments")