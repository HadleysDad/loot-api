from fastapi import APIRouter
from app.models.loot_models import LootTable, DropResult
from app.services.loot_service import generate_drop

router = APIRouter(prefix="/loot", tags=["Loot"])

router.post("/generate-drop", response_model=DropResult)
def generate_drop_endpoint(loot_table: LootTable):
    drop_item = generate_drop(loot_table)
    item_prob = next((i.rarity for i in loot_table.items if i.name == drop_item), 0)
    return {"item": drop_item, "probability": item_prob}