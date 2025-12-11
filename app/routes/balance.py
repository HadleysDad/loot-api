from fastapi import APIRouter
from app.models.loot_models import LootTable
from app.services.loot_service import simulate_drops, balance_suggestion

router = APIRouter(prefix="/balance", tags=["Balance"])

class BalanceRequest(LootTable):
    simulations: int = 1000
    
@router.post("/")
def balance_endpoint(request: BalanceRequest):
    simulation_results = simulate_drops(request, request.simulations)
    adjustments = balance_suggestion(request, simulation_results)
    return {"simulations": request.simulations, "adjustments": adjustments}