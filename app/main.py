from fastapi import FastAPI
from app.routes import loot, simulation, balance

app = FastAPI(
    title="Loot Table API",
    description="Random loot generator for game developers (Roblox, Unity, Godot)",
    version="1.0.0"
)

# Include routers
app.include_router(loot.router)
app.include_router(simulation.router)
app.include_router(balance.router)

# Health endpoint
@app.get("/health", tags=["Health"])
def health_check():
    return {"Status": "Ok"}