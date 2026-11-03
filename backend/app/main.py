from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db, backfill_snapshots
from .seed import seed_if_empty
from .routers import infrastructure, simulations, analytics

app = FastAPI(
    title="Cloud Digital Twin API",
    description="Software-based cloud infrastructure simulation and predictive analysis prototype.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    seed_if_empty()
    backfill_snapshots()

@app.get("/")
def root():
    return {"message": "Cloud Digital Twin API is running", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(infrastructure.router)
app.include_router(simulations.router)
app.include_router(analytics.router)
