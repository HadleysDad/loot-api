from fastapi import APIRouter
from app.models.loot_models import SimulationRequest
from app.services.loot_service import simulate_drops

router = APIRouter(prefix="/simulate", tags=["Simulation"])

@router.post("/")
def simulate_endpoint(request: SimulationRequest):
    results = simulate_drops(request.loot_table, request.simulations)
    return {"simulations": request.simulations, "results": results}