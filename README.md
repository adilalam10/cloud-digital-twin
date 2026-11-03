# Cloud Digital Twin for Infrastructure Simulation and Predictive Analysis

A software-only academic prototype that represents a small cloud fleet as a Digital Twin. It supports infrastructure management, workload and failure what-if simulation, SQLite persistence, resource forecasting, chronological model evaluation, and recommendations.

## Included in this final package

- React + Vite frontend with Dashboard, Infrastructure, Simulation Lab, Prediction, and Analytics pages.
- FastAPI backend and SQLite database.
- Four initial virtual servers; add and restore server actions.
- Workload increase/decrease simulation.
- Server failure simulation with workload redistribution.
- Fleet-level metric snapshots (one average CPU/RAM point per simulation snapshot) to avoid plotting per-server rows as a misleading continuous fleet trend.
- Random Forest forecast when sufficient history is available.
- Chronological 80/20 train/test evaluation (no random shuffle).
- CPU and RAM MAE and RMSE on held-out samples.
- Actual-vs-predicted CPU and RAM charts.
- A persistence-baseline fallback for short histories or missing scikit-learn.
- Safe database migration that retains an existing `digital_twin.db` and backfills fleet snapshots from old metric rows.
- Improved failure-server selection so stale/failed server IDs are cleared and cannot be selected in the UI.

## Requirements for macOS / Apple Silicon

- macOS on Apple Silicon or Intel
- Python 3.10–3.12 recommended (3.12 is a good choice)
- Node.js 20 or newer and npm
- No physical hardware, AWS account, or Docker is needed for local use

## Start the application

Extract this ZIP. Open Terminal in the extracted `cloud-digital-twin` folder. If you extracted it into Downloads, use the commands below.

### Terminal 1 — Backend

```bash
cd ~/Downloads/cloud-digital-twin/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend: http://127.0.0.1:8000  
API docs: http://127.0.0.1:8000/docs  
Health check: http://127.0.0.1:8000/health

If your Mac has multiple Python versions, use `python3.12` instead of `python3` in the virtual-environment command.

### Terminal 2 — Frontend

```bash
cd ~/Downloads/cloud-digital-twin/frontend
npm install
npm run dev
```

Open the Vite URL printed in Terminal (normally http://127.0.0.1:5173).

Keep both Terminal windows open while using the app. Stop each server with Control+C.

## Existing project data

If you are updating the earlier project version, copy your existing `backend/digital_twin.db` into this new package's `backend/` folder before starting the backend. The startup migration adds the new evaluation columns and creates fleet-level snapshots without deleting the existing servers, metrics, or simulation history.

Do not delete `digital_twin.db` unless you intentionally want to reset your project data.

## ML evaluation: how to interpret it

- The historical fleet snapshots are ordered by time.
- Supervised examples use the current snapshot and its change from the previous snapshot to predict the next snapshot.
- The final 20% of examples are held out chronologically as test data. The model is trained only on the earlier 80%.
- MAE is the average absolute prediction error; RMSE penalizes larger errors more strongly.
- CPU and RAM are evaluated separately.
- Actual-vs-predicted charts show only the held-out test points.
- With limited simulated data, metrics are preliminary. Report the training/test sample counts and do not claim production-grade accuracy. For a stronger research evaluation, collect more snapshots and repeat across multiple time periods.

## Demo sequence

1. Dashboard: explain the virtual fleet and average utilization.
2. Infrastructure: add a server, fail a server in Simulation Lab, then restore it here.
3. Simulation Lab: apply a workload increase and demonstrate before/after metrics.
4. Simulation Lab: fail one currently running server and show the recommendation.
5. Prediction: show the next-step CPU/RAM forecast, chronological split, MAE, RMSE and held-out actual-vs-predicted charts.
6. Analytics: show fleet-level CPU/RAM history and saved simulation records.
7. Restart only the backend and confirm the database records remain.

## Academic honesty / scope

The project simulates cloud infrastructure in software; it does not provision real AWS EC2 instances or read live AWS telemetry. Seed metrics are synthetic demonstration data. The prediction model is a prototype and must be evaluated on the displayed held-out samples. Do not invent accuracy values or describe synthetic metrics as measurements from a real cloud deployment.
