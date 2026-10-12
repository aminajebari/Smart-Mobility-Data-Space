"""Allowed / denied scenarios through the governance API (in-memory database)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).parent.parent))
from dataspace.main import create_app

TOKEN = "test-token"
HEADERS = {"X-Service-Token": TOKEN}


@pytest.fixture
def client():
    return TestClient(create_app(db_path=":memory:", service_token=TOKEN))


def authorize(client, requester, dataset, purpose):
    response = client.post("/authorize", headers=HEADERS, json={
        "requester_id": requester, "dataset_id": dataset, "purpose": purpose, "via": "test"})
    assert response.status_code == 200
    return response.json()


def test_health_and_registry(client):
    assert client.get("/health").json()["status"] == "ok"
    providers = {p["id"] for p in client.get("/participants", params={"type": "provider"}).json()}
    assert providers == {"traffic_sensor_1", "bus_line_12", "parking_lot_5", "bikes_zone_a"}


def test_catalogue_contains_metadata_not_records(client):
    items = client.get("/catalogue").json()
    assert len(items) >= 6
    for item in items:
        assert "policy" in item and "fields" in item
        assert "records" not in item
    assert [d["id"] for d in client.get("/catalogue", params={"q": "parking"}).json()] == ["parking_lot_5.occupancy"]


def test_public_dataset_allowed(client):
    decision = authorize(client, "mobility_startup_x", "parking_lot_5.occupancy", "commercial")
    assert decision["decision"] == "allow"


def test_denied_dataset(client):
    decision = authorize(client, "city_planning_office", "bus_line_12.passenger_counts", "research")
    assert decision["decision"] == "deny"


def test_contract_required_before_protected_access(client):
    ds, purpose = "traffic_sensor_1.traffic_flow", "congestion_prediction"
    first = authorize(client, "edge_node_1", ds, purpose)
    assert first["decision"] == "deny" and "contract" in first["reason"]

    contract = client.post("/contracts", json={"requester_id": "edge_node_1", "dataset_id": ds, "purpose": purpose})
    assert contract.status_code == 201
    assert contract.json()["terms"]["retention_days"] == 7

    second = authorize(client, "edge_node_1", ds, purpose)
    assert second["decision"] == "allow"
    assert second["contract_id"] == contract.json()["id"]


def test_contract_refused_for_disallowed_purpose(client):
    response = client.post("/contracts", json={"requester_id": "mobility_startup_x",
                                               "dataset_id": "traffic_sensor_1.traffic_flow", "purpose": "commercial"})
    assert response.status_code == 403


def test_revoked_contract_denies_access(client):
    ds, purpose = "traffic_sensor_1.traffic_flow", "monitoring"
    contract = client.post("/contracts", json={"requester_id": "dashboard_operator", "dataset_id": ds,
                                               "purpose": purpose}).json()
    assert authorize(client, "dashboard_operator", ds, purpose)["decision"] == "allow"
    client.post(f"/contracts/{contract['id']}/revoke", headers=HEADERS)
    assert authorize(client, "dashboard_operator", ds, purpose)["decision"] == "deny"


def test_role_based_dataset(client):
    ds = "bikes_zone_a.fleet_status"
    assert authorize(client, "city_planning_office", ds, "route_optimization")["decision"] == "allow"
    assert authorize(client, "edge_node_1", ds, "route_optimization")["decision"] == "deny"


def test_every_decision_is_audited(client):
    authorize(client, "mobility_startup_x", "traffic_sensor_1.traffic_flow", "commercial")
    authorize(client, "mobility_startup_x", "parking_lot_5.occupancy", "commercial")
    entries = client.get("/audit").json()
    assert len(entries) == 2
    assert {e["decision"] for e in entries} == {"allow", "deny"}
    assert entries[0]["provider_id"] == "parking_lot_5"  # newest first
    assert client.get("/audit/stats").json() == {"total": 2, "allow": 1, "deny": 1}


def test_write_endpoints_require_service_token(client):
    body = {"requester_id": "x", "dataset_id": "parking_lot_5.occupancy", "purpose": "research"}
    assert client.post("/authorize", json=body).status_code == 401


def test_only_owner_can_publish_or_change_policy(client):
    ok = client.post("/catalogue/parking_lot_5.occupancy/publish", headers=HEADERS,
                     json={"provider_id": "parking_lot_5", "access_url": "http://parking:8003", "record_count": 10})
    assert ok.status_code == 200 and ok.json()["access_url"] == "http://parking:8003"
    stolen = client.post("/catalogue/parking_lot_5.occupancy/publish", headers=HEADERS,
                         json={"provider_id": "bus_line_12"})
    assert stolen.status_code == 403
    policy = client.put("/policies/parking_lot_5.occupancy", json={"type": "denied"},
                        headers={**HEADERS, "X-Participant-Id": "bus_line_12"})
    assert policy.status_code == 403
