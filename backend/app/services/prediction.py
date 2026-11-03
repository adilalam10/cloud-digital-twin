import math
import numpy as np
from ..database import get_db
from .recommendation import recommend

def _features(previous, current):
    return [
        current["cpu"], current["ram"], current["workload"],
        current["cpu"] - previous["cpu"],
        current["ram"] - previous["ram"],
        current["workload"] - previous["workload"],
    ]

def _metrics(actual, predicted):
    errors = [float(a) - float(p) for a, p in zip(actual, predicted)]
    if not errors:
        return {"mae": None, "rmse": None}
    return {
        "mae": round(sum(abs(e) for e in errors) / len(errors), 4),
        "rmse": round(math.sqrt(sum(e * e for e in errors) / len(errors)), 4),
    }

def build_evaluation(snapshots):
    """Chronological 80/20 holdout evaluation; no random shuffling or future leakage."""
    rows = [dict(r) for r in snapshots]
    samples = []
    for i in range(1, len(rows)):
        samples.append((_features(rows[i-1], rows[i]), rows[i]["cpu"], rows[i]["ram"], i))

    if len(samples) < 4:
        return {
            "split": "Chronological 80/20 (not enough samples yet)",
            "training_samples": len(samples),
            "testing_samples": 0,
            "cpu": {"mae": None, "rmse": None},
            "ram": {"mae": None, "rmse": None},
            "cpu_points": [],
            "ram_points": [],
            "note": "At least five fleet snapshots are needed for a small holdout evaluation.",
        }

    test_count = max(1, math.ceil(len(samples) * 0.2))
    split = len(samples) - test_count
    train, test = samples[:split], samples[split:]
    y_cpu_train = [x[1] for x in train]
    y_ram_train = [x[2] for x in train]
    cpu_actual = [x[1] for x in test]
    ram_actual = [x[2] for x in test]

    # Last-value persistence baseline is always available and provides an honest
    # comparator when the training history is too small for machine learning.
    cpu_pred = [rows[x[3]-1]["cpu"] for x in test]
    ram_pred = [rows[x[3]-1]["ram"] for x in test]
    method = "Persistence baseline (limited history)"
    if len(train) >= 6:
        try:
            from sklearn.ensemble import RandomForestRegressor
            X_train = [x[0] for x in train]
            X_test = [x[0] for x in test]
            cpu_model = RandomForestRegressor(
                n_estimators=120, max_depth=5, min_samples_leaf=2,
                random_state=42, n_jobs=1
            )
            ram_model = RandomForestRegressor(
                n_estimators=120, max_depth=5, min_samples_leaf=2,
                random_state=42, n_jobs=1
            )
            cpu_model.fit(X_train, y_cpu_train)
            ram_model.fit(X_train, y_ram_train)
            cpu_pred = [float(v) for v in cpu_model.predict(X_test)]
            ram_pred = [float(v) for v in ram_model.predict(X_test)]
            method = "Random Forest (chronological holdout)"
        except ImportError:
            pass

    cpu_points = [
        {"sample": int(x[3]), "actual": round(float(a), 2), "predicted": round(float(p), 2)}
        for x, a, p in zip(test, cpu_actual, cpu_pred)
    ]
    ram_points = [
        {"sample": int(x[3]), "actual": round(float(a), 2), "predicted": round(float(p), 2)}
        for x, a, p in zip(test, ram_actual, ram_pred)
    ]
    return {
        "split": "Chronological 80/20 holdout",
        "training_samples": len(train),
        "testing_samples": len(test),
        "cpu": _metrics(cpu_actual, cpu_pred),
        "ram": _metrics(ram_actual, ram_pred),
        "cpu_points": cpu_points,
        "ram_points": ram_points,
        "note": "Metrics are calculated only on the later held-out samples. Results are preliminary because the project currently uses a small simulated dataset.",
        "method": method,
    }

def predict_resources():
    with get_db() as db:
        snapshots = db.execute(
            "SELECT * FROM metric_snapshots ORDER BY id"
        ).fetchall()
        servers = db.execute(
            "SELECT cpu,ram FROM servers WHERE status='Running'"
        ).fetchall()
        if not servers:
            raise ValueError("No running servers are available for prediction.")
        if not snapshots:
            raise ValueError("No historical fleet metrics are available yet.")

        current_cpu = sum(float(s["cpu"]) for s in servers) / len(servers)
        current_ram = sum(float(s["ram"]) for s in servers) / len(servers)
        evaluation = build_evaluation(snapshots)
        rows = [dict(r) for r in snapshots]
        predicted_cpu = current_cpu
        predicted_ram = current_ram
        method = evaluation.get("method", "Persistence baseline")

        # Fit on all historical transitions only after holdout evaluation has been
        # computed. Forecast the next fleet snapshot using the most recent trend.
        if len(rows) >= 8:
            try:
                from sklearn.ensemble import RandomForestRegressor
                samples = [
                    (_features(rows[i-1], rows[i]), rows[i]["cpu"], rows[i]["ram"])
                    for i in range(1, len(rows))
                ]
                X = [x[0] for x in samples]
                cpu_model = RandomForestRegressor(
                    n_estimators=120, max_depth=5, min_samples_leaf=2,
                    random_state=42, n_jobs=1
                ).fit(X, [x[1] for x in samples])
                ram_model = RandomForestRegressor(
                    n_estimators=120, max_depth=5, min_samples_leaf=2,
                    random_state=42, n_jobs=1
                ).fit(X, [x[2] for x in samples])
                last_feature = [X[-1]]
                predicted_cpu = float(cpu_model.predict(last_feature)[0])
                predicted_ram = float(ram_model.predict(last_feature)[0])
                method = "Random Forest (chronological 80/20 evaluation)"
            except ImportError:
                method = "Persistence baseline (scikit-learn unavailable)"
        elif len(rows) >= 2:
            predicted_cpu = current_cpu + (rows[-1]["cpu"] - rows[-2]["cpu"])
            predicted_ram = current_ram + (rows[-1]["ram"] - rows[-2]["ram"])
            method = "Trend baseline (collect more history for Random Forest)"

        predicted_cpu = round(float(np.clip(predicted_cpu, 0, 100)), 2)
        predicted_ram = round(float(np.clip(predicted_ram, 0, 100)), 2)
        risk = "HIGH" if predicted_cpu >= 85 or predicted_ram >= 85 else (
            "MEDIUM" if predicted_cpu >= 70 or predicted_ram >= 75 else "LOW"
        )
        advice = recommend(predicted_cpu, predicted_ram)
        cpu_mae = evaluation["cpu"]["mae"]
        cpu_rmse = evaluation["cpu"]["rmse"]
        ram_mae = evaluation["ram"]["mae"]
        ram_rmse = evaluation["ram"]["rmse"]
        db.execute("""
            INSERT INTO predictions(current_cpu,predicted_cpu,current_ram,predicted_ram,risk,recommendation,method,mae_cpu,rmse_cpu,mae_ram,rmse_ram)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (current_cpu, predicted_cpu, current_ram, predicted_ram, risk, advice,
              method, cpu_mae, cpu_rmse, ram_mae, ram_rmse))

        return {
            "current_cpu": round(current_cpu, 2),
            "predicted_cpu": predicted_cpu,
            "current_ram": round(current_ram, 2),
            "predicted_ram": predicted_ram,
            "risk": risk,
            "recommendation": advice,
            "method": method,
            "evaluation": evaluation,
        }
