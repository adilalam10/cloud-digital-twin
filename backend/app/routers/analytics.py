from fastapi import APIRouter, HTTPException
from ..database import get_db
from ..services.prediction import predict_resources

router = APIRouter(prefix="/api", tags=["Analytics"])

@router.get("/dashboard")
def dashboard():
    with get_db() as db:
        all_servers = [dict(r) for r in db.execute("SELECT * FROM servers").fetchall()]
        running = [s for s in all_servers if s["status"] == "Running"]
        return {
            "total_servers": len(all_servers),
            "active_servers": len(running),
            "failed_servers": len(all_servers) - len(running),
            "average_cpu": round(sum(s["cpu"] for s in running) / len(running), 2) if running else 0,
            "average_ram": round(sum(s["ram"] for s in running) / len(running), 2) if running else 0,
            "high_risk_servers": sum(s["cpu"] >= 85 or s["ram"] >= 85 for s in running),
        }

@router.get("/metrics")
def metrics():
    # Return fleet-level snapshots rather than plotting each server's rows as one
    # continuous line. This prevents artificial zig-zag spikes in analytics.
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM metric_snapshots ORDER BY id DESC LIMIT 100"
        ).fetchall()][::-1]

@router.get("/snapshots")
def snapshots():
    return metrics()

@router.get("/predictions")
def predictions():
    try:
        return predict_resources()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/prediction-history")
def prediction_history():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM predictions ORDER BY id DESC LIMIT 30"
        ).fetchall()]
