from pydantic import BaseModel
from typing import Optional

class DropRequest(BaseModel):
    seed: Optional[int] = None

class CategoryDropRequest(DropRequest):
    category: str

class RarityDropRequest(DropRequest):
    rarity: str
    
class TagSearchRequest(BaseModel):
    tags: list[str]

class TagDropRequest(BaseModel):
    tags: list[str]
    seed: int | None = None
    
class SimulationRequest(BaseModel):
    simulations: int = 1000
    seed: int | None = None
    tags: list[str] | None = None
    
class LuckDropRequest(BaseModel):
    luck: float = 0.0 # 0.0 = no luck, 1.0 = strong luck
    seed: int | None = None
    tags: list[str] | None = None