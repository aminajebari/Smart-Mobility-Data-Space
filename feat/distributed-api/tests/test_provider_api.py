"""Provider API tests against Module 1 sample data and a stubbed policy service."""
COMMON_FIELDS = {"provider_id", "timestamp", "latitude", "longitude", "incident"}


def test_health(traffic):
    body = traffic.get("/health").json()
    assert body["status"] == "ok" and body["provider_id"] == "traffic_sensor_1"
    assert body["local_data"] is True


def test_openapi_documents_all_endpoints(traffic):
    paths = traffic.get("/openapi.json").json()["paths"]
    for endpoint in ("/health", "/data", "/datasets", "/publish", "/search", "/logs", "/partners/data"):
        assert endpoint in paths


def test_data_returns_common_schema_and_calls_policy(traffic, stub):
    body = traffic.get("/data", params={"limit": 5, "purpose": "monitoring"},
                       headers={"X-API-Key": "edge-key"}).json()
    assert body["count"] == 5 and body["dataset_id"] == "traffic_sensor_1.traffic_flow"
    assert all(COMMON_FIELDS <= r.keys() for r in body["records"])
    assert stub.calls[-1] == ("edge_node_1", "traffic_sensor_1.traffic_flow", "monitoring",
                              "provider-api:traffic_sensor_1")


def test_anonymous_requests_are_still_policy_checked(traffic, stub):
    traffic.get("/data")
    assert stub.calls[-1][0] == "anonymous"


def test_invalid_key_is_rejected(traffic):
    assert traffic.get("/data", headers={"X-API-Key": "nope"}).status_code == 401


def test_policy_denial_returns_403(traffic):
    response = traffic.get("/data", params={"purpose": "commercial"}, headers={"X-API-Key": "startup-key"})
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "stub"


def test_policy_service_down_fails_closed(traffic, stub):
    stub.available = False
    assert traffic.get("/data").status_code == 503


def test_unknown_dataset_404(traffic):
    assert traffic.get("/data", params={"dataset_id": "bus_line_12.vehicle_status"}).status_code == 404


def test_filters(traffic):
    params = {"limit": 1000, "incident": True}
    records = traffic.get("/data", params=params).json()["records"]
    assert records and all(r["incident"] for r in records)

    all_records = traffic.get("/data", params={"limit": 1000}).json()["records"]
    middle = all_records[500]["timestamp"]
    since = traffic.get("/data", params={"limit": 1000, "since": middle}).json()["records"]
    assert since[0]["timestamp"] == middle and len(since) == 500
    until = traffic.get("/data", params={"limit": 1000, "since": all_records[0]["timestamp"], "until": middle}).json()
    assert until["records"][-1]["timestamp"] == middle

    far = traffic.get("/data", params={"lat": 0, "lon": 0, "radius_km": 1}).json()
    assert far["count"] == 0


def test_datasets_lists_local_offerings(traffic):
    ids = {d["dataset_id"]: d for d in traffic.get("/datasets").json()}
    assert ids["traffic_sensor_1.traffic_flow"]["record_count"] >= 1000
    assert ids["traffic_sensor_1.congestion_forecast"]["source"] == "published"


def test_publish_predictions_by_authorized_publisher(traffic, stub):
    record = {"timestamp": "2026-09-28T10:00:00", "congestion_probability": 0.91, "congested": True}
    ok = traffic.post("/publish", json={"dataset_id": "traffic_sensor_1.congestion_forecast", "records": [record]},
                      headers={"X-API-Key": "edge-key"})
    assert ok.status_code == 200 and ok.json()["total"] == 1
    assert stub.published[-1] == ("traffic_sensor_1.congestion_forecast", 1)

    data = traffic.get("/data", params={"dataset_id": "traffic_sensor_1.congestion_forecast"},
                       headers={"X-API-Key": "dashboard-key"}).json()
    assert data["records"] == [record]


def test_publish_rejected_for_other_participants_and_raw_data(traffic):
    body = {"dataset_id": "traffic_sensor_1.congestion_forecast", "records": [{"timestamp": "2026-09-28T10:00:00"}]}
    assert traffic.post("/publish", json=body, headers={"X-API-Key": "startup-key"}).status_code == 403
    raw = {"dataset_id": "traffic_sensor_1.traffic_flow", "records": [{"timestamp": "2026-09-28T10:00:00"}]}
    assert traffic.post("/publish", json=raw, headers={"X-API-Key": "traffic-key"}).status_code == 409


def test_search(traffic):
    results = traffic.get("/search", params={"q": "traffic", "lat": 36.8065, "lon": 10.1815, "radius_km": 1}).json()
    assert results[0]["id"] == "traffic_sensor_1.traffic_flow"
    assert traffic.get("/search", params={"q": "traffic", "lat": 0, "lon": 0, "radius_km": 1}).json() == []


def test_request_logs(traffic):
    traffic.get("/data", headers={"X-API-Key": "edge-key"})
    assert traffic.get("/logs", headers={"X-API-Key": "startup-key"}).status_code == 403
    entries = traffic.get("/logs", headers={"X-API-Key": "dashboard-key"}).json()
    data_entry = next(e for e in entries if e["path"] == "/data")
    assert data_entry["requester"] == "edge_node_1" and data_entry["decision"] == "allow"


def test_each_provider_only_sees_its_own_data(bus):
    body = bus.get("/data", params={"limit": 3}).json()
    assert body["dataset_id"] == "bus_line_12.vehicle_status"
    assert {r["provider_id"] for r in body["records"]} == {"bus_line_12"}
    assert bus.get("/data", params={"dataset_id": "bus_line_12.passenger_counts"}).status_code == 403


def test_partner_endpoints_require_own_identity(bus):
    params = {"dataset_id": "traffic_sensor_1.traffic_flow", "purpose": "traffic_management"}
    assert bus.get("/partners/data", params=params, headers={"X-API-Key": "edge-key"}).status_code == 403
