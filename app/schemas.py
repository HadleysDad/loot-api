
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
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

class RarityTargets(BaseModel):
    Common: Optional[float] = None
    Uncommon: Optional[float] = None
    Rare: Optional[float] = None
    Epic: Optional[float] = None
    Legendary: Optional[float] = None
    
class BalanceRequest(BaseModel):
    simulations: int = 50000
    seed: int | None = None

class ReweightRequest(BaseModel):
    simulations: int = 20000
    seed: Optional[int] = None
    target_rarity: Dict[str, float] = Field(
        default_factory=dict,
        description="Target drop % by rarity. Total should be close to 100."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "simulations": 20000,
                "seed": 1,
                "target_rarity": {
                    "Common": 50,
                    "Uncommon": 27,
                    "Rare": 15,
                    "Epic": 6,
                    "Legendary": 2
                }
            }
        }
    }


class ExportRequest(BaseModel):
    multipliers: Dict[str, float] = Field(
        default_factory=dict,
        description="Weight multipliers to apply to your loot table items."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "multipliers": {
                    "Common": 0.82,
                    "Uncommon": 1.20,
                    "Rare": 1.30,
                    "Epic": 1.50,
                    "Legendary": 2.10
                }
            }
        }
    }


class ImportTestRequest(BaseModel):
    """
    Request body for validating and previewing auto-corrections
    on a custom loot table JSON.
    """

    name: Optional[str] = Field(
        default="Imported_Table",
        description="Optional display name for the imported loot table."
    )

    auto_correct_profile: Optional[Literal["safe", "aggressive", "strict"]] = Field(
        default="safe",
        description=(
            "Auto-correct profile to use for preview:\n"
            "- safe: non-destructive fixes only (free)\n"
            "- aggressive: balance & progression diagnostics (preview-only)\n"
            "- strict: CI-grade validation, no fixes"
        )
    )

    apply_safe_fixes: Optional[bool] = Field(
        default=False,
        description=(
            "If true, applies SAFE auto-corrections to a copy of the loot table.\n"
            "Only valid when auto_correct_profile='safe'."
        )
    )

    loot_table: Dict[str, Any] = Field(
        ...,
        description="Custom loot table JSON to validate. Must follow the same structure as /schema."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Imported_Table",
                "auto_correct_profile": "aggressive",
                "apply_safe_fixes": False,
                "loot_table": {
                    "Weapons": {
                        "Sword_1H": {
                            "Common": [
                                {
                                    "name": "Rusty Sword",
                                    "rarity": "Common",
                                    "type": "weapon_sword_1h",
                                    "tags": ["melee", "physical"],
                                    "stats": {
                                        "attack": 5
                                    },
                                    "drop": {
                                        "weight": 100
                                    }
                                }
                            ],
                            "Rare": [
                                {
                                    "name": "Knight Blade",
                                    "rarity": "Rare",
                                    "type": "weapon_sword_1h",
                                    "tags": ["melee", "physical"],
                                    "stats": {
                                        "attack": 18,
                                        "crit_chance": 3
                                    },
                                    "drop": {
                                        "weight": 15
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

class AutoCorrectProfile(str, Enum):
    safe = "safe"
    aggressive = "aggressive"
    strict = "strict"

class ExportcorrectRequest(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="Optional name for the exported loot table"
    )
    
    loot_table: Dict[str, Any] = Field(
        ...,
        description="Custom loot table JSON to validate and correct"
    )
    
    auto_correct_profile: AutoCorrectProfile = Field(
        default=AutoCorrectProfile.safe,
        description="Auto-correct behavior profile"
    )
