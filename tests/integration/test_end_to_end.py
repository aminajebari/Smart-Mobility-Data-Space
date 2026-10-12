"""In-process end-to-end test of the final integration scenario.

All real module apps are wired together through TestClients (no network, no Docker):
Module 1 data -> Module 2 provider API -> Module 3 policy/audit -> Module 4 edge loop
-> Module 2 publish -> partner access -> Module 5 dashboard aggregate.
"""
import importlib
import sys
from collections import deque
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "it-token"
KEYS = {"traffic-key": "traffic_sensor_1", "bus-key": "bus_line_12", "edge-key": "edge_node_1",
        "dash-key": "dashboard_operator", "city-key": "city_planning_office", "startup-key": "mobility_startup_x"}


def load(module_dir: Path, module: str):
    """Import a module's package in isolation (modules are independent projects)."""
    sys.path.insert(0, str(module_dir))
    try:
        return importlib.import_module(module)
    finally:
        sys.path.remove(str(module_dir))


class Router:
    """Minimal httpx-like client that dispatches absolute URLs to in-process apps by host."""

    def __init__(self, apps: dict[str, TestClient]):
        self.apps = apps

    def _client(self, url: str) -> tuple[TestClient, str]:
        parsed = httpx.URL(url)
        if parsed.host not in self.apps:
            raise httpx.ConnectError(f"no route to {parsed.host}")
        return self.apps[parsed.host], parsed.raw_path.decode()

    def request(self, method, url, **kwargs):
        client, path = self._client(url)
        return client.request(method, path, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


@pytest.fixture(scope="module")
def system(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    ds_main = load(ROOT / "feat" / "data-space", "dataspace.main")
    api_main = load(ROOT / "feat" / "distributed-api", "provider_api.main")
    api_settings = sys.modules["provider_api.settings"]
    api_ds_client = sys.modules["provider_api.dataspace_client"]
    api_client_mod = sys.modules["provider_api.client"]
    edge = load(ROOT / "feat" / "edge-ai", "edge_ai.service")
    dash = load(ROOT / "feat" / "dashboard-devops" / "dashboard-api", "app.main")

    apps: dict[str, TestClient] = {}
    router = Router(apps)
    apps["data-space"] = TestClient(ds_main.create_app(db_path=":memory:", service_token=TOKEN))

    ports = {"traffic_sensor_1": 8001, "bus_line_12": 8002, "parking_lot_5": 8003, "bikes_zone_a": 8004}
    for pid in ports:
        settings = api_settings.Settings(
            provider_id=pid, port=ports[pid], public_url=f"http://{pid}", api_keys=KEYS,
            own_api_key={"traffic_sensor_1": "traffic-key", "bus_line_12": "bus-key"}.get(pid, ""),
            data_simulation_path=str(ROOT / "feat" / "data-simulation"), data_space_url="http://data-space",
            data_space_token=TOKEN, log_readers=["dashboard_operator"], runtime_dir=tmp / pid,
            providers_config=ROOT / "feat" / "distributed-api" / "config" / "providers.yaml",
            catalogue_refresh_seconds=30)
        ds_client = api_ds_client.DataSpaceClient("http://data-space", TOKEN, http=router)
        partner = api_client_mod.ProviderClient(settings.own_api_key, ds_client, http=router)
        app = api_main.create_app(settings, data_space=ds_client, partner_client=partner, background=False)
        apps[pid] = TestClient(app)

    # providers self-publish their offerings (what the background loop does at startup)
    for pid in ports:
        primary = {"traffic_sensor_1": "traffic_sensor_1.traffic_flow", "bus_line_12": "bus_line_12.vehicle_status",
                   "parking_lot_5": "parking_lot_5.occupancy", "bikes_zone_a": "bikes_zone_a.fleet_status"}[pid]
        own_key = {"traffic_sensor_1": "traffic-key", "bus_line_12": "bus-key"}.get(pid)
        if own_key:
            assert apps[pid].post("/publish", json={"dataset_id": primary},
                                  headers={"X-API-Key": own_key}).status_code == 200

    loop = edge.EdgeLoop(edge.EdgeModel(ROOT / "feat" / "edge-ai" / "models"), deque(), http=router)
    loop.traffic_url, loop.data_space_url, loop.api_key = "http://traffic_sensor_1", "http://data-space", "edge-key"

    dash_settings = dash.Settings()
    dash_settings.provider_urls = {pid: f"http://{pid}" for pid in ports}
    dash_settings.data_space_url, dash_settings.edge_url = "http://data-space", "http://edge"
    dash_settings.api_key, dash_settings.cache_seconds = "dash-key", 0
    dash_settings.stale_after_seconds = 10 ** 9  # sample data is days old
    apps["edge"] = TestClient(edge.create_app(model_dir=ROOT / "feat" / "edge-ai" / "models", run_loop=False))
    dashboard = TestClient(dash.create_app(dash_settings, http=router))
    return {"apps": apps, "loop": loop, "dashboard": dashboard}


def test_final_integration_scenario(system):
    apps, loop = system["apps"], system["loop"]
    traffic, ds = apps["traffic_sensor_1"], apps["data-space"]

    # 1-2. provider API publishes the current mobility state; catalogue knows where to find it
    assert ds.get("/catalogue/traffic_sensor_1.traffic_flow").json()["access_url"] == "http://traffic_sensor_1"

    # 3. edge node: first request denied (no contract) -> negotiates -> predicts -> publishes results
    prediction = loop.tick()
    assert prediction is not None and 0 <= prediction["congestion_probability"] <= 1
    contracts = ds.get("/contracts", params={"requester_id": "edge_node_1"}).json()
    assert contracts and contracts[0]["purpose"] == "congestion_prediction"

    # 4-5. partners request the prediction through the provider API
    allowed = traffic.get("/data", params={"dataset_id": "traffic_sensor_1.congestion_forecast",
                                           "purpose": "traffic_management"}, headers={"X-API-Key": "city-key"})
    assert allowed.status_code == 200
    assert allowed.json()["records"][-1]["congestion_probability"] == prediction["congestion_probability"]
    denied = traffic.get("/data", params={"dataset_id": "traffic_sensor_1.congestion_forecast",
                                          "purpose": "commercial"}, headers={"X-API-Key": "startup-key"})
    assert denied.status_code == 403

    # provider-to-provider exchange with catalogue discovery
    bus = apps["bus_line_12"]
    params = {"dataset_id": "traffic_sensor_1.traffic_flow", "purpose": "route_optimization", "limit": 2}
    assert bus.get("/partners/data", params=params, headers={"X-API-Key": "bus-key"}).status_code == 403
    assert bus.post("/partners/contracts", json={"dataset_id": "traffic_sensor_1.traffic_flow",
                                                 "purpose": "route_optimization"},
                    headers={"X-API-Key": "bus-key"}).status_code == 403  # purpose not allowed by the policy
    params["purpose"] = "traffic_management"
    assert bus.post("/partners/contracts", json={"dataset_id": "traffic_sensor_1.traffic_flow",
                                                 "purpose": "traffic_management"},
                    headers={"X-API-Key": "bus-key"}).status_code == 200
    exchanged = bus.get("/partners/data", params=params, headers={"X-API-Key": "bus-key"})
    assert exchanged.status_code == 200 and exchanged.json()["count"] == 2

    # 6. every decision is in the audit log
    audit = ds.get("/audit", params={"limit": 1000}).json()
    assert {"edge_node_1", "city_planning_office", "mobility_startup_x", "bus_line_12"} <= {e["requester_id"] for e in audit}
    assert {"allow", "deny"} == {e["decision"] for e in audit}

    # 7. dashboard aggregates providers, traffic, AI prediction and exchange trace through APIs only
    data = system["dashboard"].get("/api/dashboard").json()
    assert [p["status"] for p in data["providers"]] == ["connected"] * 4
    assert data["traffic"] and data["exchanges"]
    assert data["predictions"][0]["value"] == f"{prediction['congestion_probability'] * 100:.0f}%"
