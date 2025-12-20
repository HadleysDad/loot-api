from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum

# -----------------------------
# ENUM DEFINITIONS
# -----------------------------

class RarityEnum(str, Enum):
    common = "common"
    uncommon = "uncommon"
    rare = "rare"
    epic = "epic"
    legendary = "legendary"


# -----------------------------
# BASE DROP REQUEST
# -----------------------------

class DropRequest(BaseModel):
    seed: Optional[int] = Field(
        default=None,
        description="Optional RNG seed for deterministic results. "
                    "Same seed always produces same drop order."
    )


# -----------------------------
# DROP BY CATEGORY
# -----------------------------

class CategoryDropRequest(DropRequest):
    category: str = Field(
        description="Loot category to select from (weapons, armor, etc.)"
    )


# -----------------------------
# DROP BY RARITY
# -----------------------------

class RarityDropRequest(DropRequest):
    rarity: RarityEnum = Field(
        description="Rarity tier to draw items from."
    )


# -----------------------------
# SEARCH BY TAG LIST
# -----------------------------

class TagSearchRequest(BaseModel):
    tags: List[str] = Field(
        description="Return all items that contain ALL these tags."
    )

    @validator("tags")
    def non_empty(cls, v):
        if len(v) == 0:
            raise ValueError("tags list cannot be empty")
        return v


# -----------------------------
# DROP BY TAGS
# -----------------------------

class TagDropRequest(BaseModel):
    tags: List[str] = Field(
        description="Tag list filtering drop pool before selection."
    )
    seed: Optional[int] = Field(
        default=None,
        description="Optional RNG seed"
    )

    @validator("tags")
    def non_empty(cls, v):
        if len(v) == 0:
            raise ValueError("tags list cannot be empty")
        return v


# -----------------------------
# SIMULATION REQUEST
# -----------------------------

class SimulationRequest(BaseModel):
    simulations: int = Field(
        default=1000,
        ge=1,
        le=100_000,
        description="Number of simulated rolls. Max: 100,000"
    )
    seed: Optional[int] = Field(
        default=None,
        description="Optional RNG seed lock"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="If provided, pool is filtered by tag matching"
    )


# -----------------------------
# LUCK DROP REQUEST
# -----------------------------

class LuckDropRequest(BaseModel):
    luck: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Luck boost weighting (0.0 = no effect, 1.0 = max boost)"
    )
    seed: Optional[int] = Field(
        default=None,
        description="Optional RNG seed"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="If supplied, items are filtered to matching tags first"
    )


# -----------------------------
# LUCK SIMULATION REQUEST
# -----------------------------

class LuckSimulateRequest(SimulationRequest):
    luck: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Luck strength applied before simulation run"
    )


# -----------------------------
# COMPARE SIMULATIONS
# -----------------------------

class CompareSimulationRequest(BaseModel):
    simulations: int = Field(
        default=10000,
        ge=1,
        le=100_000,
        description="How many rolls each test should run"
    )
    luck: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Luck bonus applied to the second simulation set"
    )
    seed: Optional[int] = Field(
        default=None,
        description="Same seed will generate comparable results"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter comparison pool by tags before running both tests"
    )
    