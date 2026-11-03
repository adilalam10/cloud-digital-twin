from fastapi import APIRouter, HTTPException
from ..schemas import SimulationRequest
from ..services.simulation import run_simulation
from ..database import get_db

router = APIRouter(prefix="/api", tags=["Simulation"])

@router.post("/simulate")
def simulate(payload: SimulationRequest):
    try:
        return run_simulation(payload.scenario, payload.workload_change, payload.server_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/simulations")
def history():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM simulations ORDER BY id DESC LIMIT 50"
        ).fetchall()]
