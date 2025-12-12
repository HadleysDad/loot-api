from pydantic import BaseModel
from typing import Optional

class DropRequest(BaseModel):
    seed: Optional[int] = None

class CategoryDropRequest(DropRequest):
    category: str

class RarityDropRequest(DropRequest):
    rarity: str