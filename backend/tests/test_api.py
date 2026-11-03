import math

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.services.prediction import _metrics, build_evaluation


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Run each API test against a fresh temporary SQLite database."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "cloud_twin_test.db")
    with TestClient(app) as test_client:
        yield test_client


def test_root_and_health_endpoints(client):
    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert root.json()["message"] == "Cloud Digital Twin API is running"
    assert root.json()["docs"] == "/docs"
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_dashboard_has_consistent_server_counts(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200

    data = response.json()
    assert {
        "total_servers", "active_servers", "failed_servers",
        "average_cpu", "average_ram", "high_risk_servers"
    }.issubset(data.keys())
    assert data["total_servers"] == data["active_servers"] + data["failed_servers"]
    assert 0 <= data["average_cpu"] <= 100
    assert 0 <= data["average_ram"] <= 100


def test_list_servers_returns_server_records(client):
    response = client.get("/api/infrastructure/servers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    if response.json():
        server = response.json()[0]
        assert {"id", "name", "cpu", "ram", "storage", "network", "workload", "status"} <= server.keys()


def test_create_server_and_list_it(client):
    payload = {
        "name": "Test-Node-A",
        "cpu": 25,
        "ram": 30,
        "storage": 40,
        "network": 20,
        "workload": 35,
    }

    created = client.post("/api/infrastructure/servers", json=payload)
    assert created.status_code == 200
    server = created.json()
    assert server["name"] == "Test-Node-A"
    assert server["status"] == "Running"
    assert server["cpu"] == 25

    listed = client.get("/api/infrastructure/servers")
    assert listed.status_code == 200
    assert any(item["id"] == server["id"] for item in listed.json())


def test_duplicate_server_name_is_rejected_case_insensitively(client):
    payload = {"name": "Duplicate-Node"}
    first = client.post("/api/infrastructure/servers", json=payload)
    second = client.post("/api/infrastructure/servers", json={"name": "duplicate-node"})

    assert first.status_code == 200
    assert second.status_code == 409


def test_invalid_server_payload_is_rejected(client):
    too_short = client.post("/api/infrastructure/servers", json={"name": " "})
    out_of_range = client.post(
        "/api/infrastructure/servers",
        json={"name": "Bad-Node", "cpu": 150},
    )

    assert too_short.status_code == 422
    assert out_of_range.status_code == 422


def test_workload_simulation_updates_fleet_and_records_history(client):
    before = client.get("/api/dashboard").json()
    response = client.post(
        "/api/simulate",
        json={"scenario": "workload", "workload_change": 25},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["scenario"] == "workload"
    assert result["after_cpu"] >= result["before_cpu"]
    assert result["after_ram"] >= result["before_ram"]
    assert result["failed_server_id"] is None

    after = client.get("/api/dashboard").json()
    assert after["active_servers"] == before["active_servers"]

    history = client.get("/api/simulations")
    assert history.status_code == 200
    assert any("Workload changed" in item["description"] for item in history.json())


def test_workload_simulation_rejects_invalid_change(client):
    response = client.post(
        "/api/simulate",
        json={"scenario": "workload", "workload_change": 500},
    )
    assert response.status_code == 422


def test_failure_simulation_fails_the_selected_server_only(client):
    servers = client.get("/api/infrastructure/servers").json()
    running = [server for server in servers if server["status"] == "Running"]
    assert len(running) >= 2

    selected = running[-1]
    response = client.post(
        "/api/simulate",
        json={"scenario": "failure", "server_id": selected["id"]},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["failed_server_id"] == selected["id"]
    assert selected["name"] in result["description"]

    updated = client.get("/api/infrastructure/servers").json()
    selected_after = next(server for server in updated if server["id"] == selected["id"])
    assert selected_after["status"] == "Failed"

    other_running = [
        server for server in updated
        if server["id"] != selected["id"] and server["status"] == "Running"
    ]
    assert len(other_running) == len(running) - 1


def test_failure_simulation_rejects_unknown_server_id(client):
    response = client.post(
        "/api/simulate",
        json={"scenario": "failure", "server_id": 999999},
    )
    assert response.status_code == 400
    assert "no longer running" in response.json()["detail"].lower()


def test_failed_server_can_be_restored(client):
    servers = client.get("/api/infrastructure/servers").json()
    selected = next(server for server in servers if server["status"] == "Running")

    failed = client.post(
        "/api/simulate",
        json={"scenario": "failure", "server_id": selected["id"]},
    )
    assert failed.status_code == 200

    restored = client.post(f"/api/infrastructure/servers/{selected['id']}/restore")
    assert restored.status_code == 200
    assert "restored" in restored.json()["message"].lower()

    servers_after = client.get("/api/infrastructure/servers").json()
    server_after = next(server for server in servers_after if server["id"] == selected["id"])
    assert server_after["status"] == "Running"


def test_restore_unknown_server_returns_404(client):
    response = client.post("/api/infrastructure/servers/999999/restore")
    assert response.status_code == 404


def test_metrics_endpoint_returns_fleet_snapshots(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    for point in response.json():
        assert {"id", "cpu", "ram", "workload", "network", "server_count"} <= point.keys()
        assert 0 <= point["cpu"] <= 100
        assert 0 <= point["ram"] <= 100


def test_snapshots_endpoint_matches_metrics_endpoint(client):
    metrics = client.get("/api/metrics")
    snapshots = client.get("/api/snapshots")

    assert metrics.status_code == snapshots.status_code == 200
    assert metrics.json() == snapshots.json()


def test_predictions_endpoint_returns_forecast_and_evaluation(client):
    response = client.get("/api/predictions")
    assert response.status_code == 200

    data = response.json()
    assert {
        "current_cpu", "predicted_cpu", "current_ram", "predicted_ram",
        "risk", "recommendation", "method", "evaluation"
    }.issubset(data.keys())

    for key in ("current_cpu", "predicted_cpu", "current_ram", "predicted_ram"):
        assert 0 <= data[key] <= 100

    evaluation = data["evaluation"]
    assert "training_samples" in evaluation
    assert "testing_samples" in evaluation
    assert "cpu" in evaluation and "ram" in evaluation
    assert "cpu_points" in evaluation and "ram_points" in evaluation

    for resource in ("cpu", "ram"):
        for metric in ("mae", "rmse"):
            value = evaluation[resource][metric]
            assert value is None or value >= 0


def test_prediction_history_records_prediction(client):
    prediction = client.get("/api/predictions")
    assert prediction.status_code == 200

    history = client.get("/api/prediction-history")
    assert history.status_code == 200
    assert isinstance(history.json(), list)
    assert len(history.json()) >= 1
    assert {"current_cpu", "predicted_cpu", "current_ram", "predicted_ram", "risk"} <= history.json()[0].keys()


def test_simulation_history_endpoint_returns_list(client):
    response = client.get("/api/simulations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_metrics_calculation_returns_mae_and_rmse():
    result = _metrics([10, 20, 30], [12, 18, 33])

    assert result["mae"] == pytest.approx(2.3333, abs=0.0001)
    assert result["rmse"] == pytest.approx(math.sqrt(17 / 3), abs=0.0001)


def test_metrics_calculation_handles_empty_inputs():
    assert _metrics([], []) == {"mae": None, "rmse": None}


def test_chronological_evaluation_uses_later_samples_as_test_data():
    snapshots = [
        {
            "cpu": float(20 + i * 2),
            "ram": float(30 + i),
            "workload": float(10 + i * 3),
            "network": float(15 + i),
        }
        for i in range(10)
    ]

    result = build_evaluation(snapshots)

    # 10 snapshots create 9 one-step-ahead samples; ceil(20% of 9) = 2 test samples.
    assert result["split"] == "Chronological 80/20 holdout"
    assert result["training_samples"] == 7
    assert result["testing_samples"] == 2
    assert [point["sample"] for point in result["cpu_points"]] == [8, 9]
    assert [point["sample"] for point in result["ram_points"]] == [8, 9]
    assert result["cpu"]["mae"] is not None
    assert result["cpu"]["rmse"] is not None
    assert result["ram"]["mae"] is not None
    assert result["ram"]["rmse"] is not None


def test_chronological_evaluation_reports_insufficient_history():
    snapshots = [
        {"cpu": 40.0, "ram": 50.0, "workload": 30.0, "network": 20.0},
        {"cpu": 42.0, "ram": 51.0, "workload": 32.0, "network": 21.0},
        {"cpu": 44.0, "ram": 52.0, "workload": 34.0, "network": 22.0},
    ]

    result = build_evaluation(snapshots)

    assert result["testing_samples"] == 0
    assert result["cpu"]["mae"] is None
    assert result["ram"]["rmse"] is None
    assert result["cpu_points"] == []
    assert "not enough samples" in result["split"].lower()
