import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).parent.parent))
from app.main import Settings, create_app  # noqa: E402

NOW = datetime.now()


def traffic_records(n=48):
    return [{"provider_id": "traffic_sensor_1", "timestamp": (NOW - timedelta(seconds=5 * (n - i))).isoformat(),
             "latitude": 36.8, "longitude": 10.18, "speed": 40 - i * 0.5, "traffic_density": 0.2 + i * 0.01,
             "incident": i > 40} for i in range(n)]


def handler(request: httpx.Request) -> httpx.Response:
    url, path = str(request.url), request.url.path
    if path == "/health":
        if ":8004" in url:  # bikes provider is down
            raise httpx.ConnectError("down")
        return httpx.Response(200, json={"status": "ok"})
    if path == "/data":
        dataset = request.url.params["dataset_id"]
        if dataset == "traffic_sensor_1.congestion_forecast":
            records = [{"timestamp": NOW.isoformat(), "congestion_probability": 0.9, "congested": True,
                        "traffic_level": "severe", "estimated_travel_time_min": 42.0}]
        elif dataset == "traffic_sensor_1.traffic_flow":
            records = traffic_records()
        elif dataset == "parking_lot_5.occupancy":
            records = [{"timestamp": NOW.isoformat(), "occupancy": 0.5, "incident": False}]
        else:
            records = [{"timestamp": NOW.isoformat(), "incident": False}]
        return httpx.Response(200, json={"records": records, "count": len(records)})
    if path == "/model-info":
        return httpx.Response(200, json={"horizon": 6, "metrics": {"random_forest_onnx": {"f1": 0.66}}})
    if path == "/audit":
        return httpx.Response(200, json=[
            {"id": 2, "timestamp": NOW.isoformat(), "requester_id": "mobility_startup_x", "provider_id": "traffic_sensor_1",
             "dataset_id": "traffic_sensor_1.traffic_flow", "purpose": "commercial", "decision": "deny", "reason": "x"},
            {"id": 1, "timestamp": NOW.isoformat(), "requester_id": "dashboard_operator", "provider_id": "parking_lot_5",
             "dataset_id": "parking_lot_5.occupancy", "purpose": "monitoring", "decision": "allow", "reason": "x"}])
    if path == "/audit/stats":
        return httpx.Response(200, json={"total": 2, "allow": 1, "deny": 1})
    if path == "/participants":
        return httpx.Response(200, json=[{"id": "mobility_startup_x", "name": "Mobility Startup X"},
                                         {"id": "traffic_sensor_1", "name": "Urban Traffic Sensors"}])
    if path == "/catalogue":
        return httpx.Response(200, json=[{"id": "traffic_sensor_1.traffic_flow", "title": "Road traffic flow"}])
    return httpx.Response(404)


def client():
    settings = Settings()
    settings.cache_seconds = 0
    return TestClient(create_app(settings, http=httpx.Client(transport=httpx.MockTransport(handler))))


def test_dashboard_matches_frontend_contract():
    data = client().get("/api/dashboard").json()
    assert set(data) >= {"providers", "services", "kpis", "traffic", "predictions", "exchanges", "updatedAt"}
    assert data["mode"] == "live"


def test_offline_provider_is_reported():
    data = client().get("/api/dashboard").json()
    status = {p["id"]: p["status"] for p in data["providers"]}
    assert status == {"traffic_sensor_1": "connected", "bus_line_12": "connected",
                      "parking_lot_5": "connected", "bikes_zone_a": "disconnected"}
    assert {s["id"]: s["status"] for s in data["services"]}["bikes_zone_a"] == "offline"
    assert next(k for k in data["kpis"] if k["id"] == "providers")["value"] == "3 / 4"


def test_traffic_series_marks_congestion():
    traffic = client().get("/api/dashboard").json()["traffic"]
    assert 0 < len(traffic) <= 24
    assert traffic[-1]["incident"] and not traffic[0]["incident"]
    assert all(0 <= p["density"] <= 100 for p in traffic)


def test_predictions_and_exchanges():
    data = client().get("/api/dashboard").json()
    assert data["predictions"][0]["value"] == "90%"
    assert data["predictions"][1]["value"] == "Severe"
    # the dashboard's own polling is hidden from the exchange table
    assert [e["destination"] for e in data["exchanges"]] == ["Mobility Startup X"]
    assert data["exchanges"][0]["authorization"] == "denied"
