import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

MODULE_ROOT = Path(__file__).parent.parent
sys.path.append(str(MODULE_ROOT))

from provider_api.main import create_app  # noqa: E402
from provider_api.settings import Settings  # noqa: E402

KEYS = {"traffic-key": "traffic_sensor_1", "edge-key": "edge_node_1", "startup-key": "mobility_startup_x",
        "dashboard-key": "dashboard_operator", "bus-key": "bus_line_12"}


class StubDataSpace:
    """Stands in for Module 3: allows everything except purpose 'commercial' and dataset passenger_counts."""

    def __init__(self):
        self.calls, self.published = [], []
        self.available = True

    def authorize(self, requester_id, dataset_id, purpose, via):
        from provider_api.dataspace_client import DataSpaceUnavailable
        if not self.available:
            raise DataSpaceUnavailable("down")
        self.calls.append((requester_id, dataset_id, purpose, via))
        denied = purpose == "commercial" or dataset_id.endswith("passenger_counts")
        return {"decision": "deny" if denied else "allow", "reason": "stub", "policy_type": "stub",
                "contract_id": None, "audit_id": len(self.calls)}

    def publish(self, dataset_id, provider_id, access_url, record_count, last_published):
        self.published.append((dataset_id, record_count))
        return True

    def catalogue(self, **params):
        return [{"id": "traffic_sensor_1.traffic_flow", "provider_id": "traffic_sensor_1", "title": "Road traffic",
                 "tags": ["traffic"], "location": [36.8065, 10.1815], "policy": {"type": "purpose_limited"}}]

    def dataset(self, dataset_id):
        return None

    def negotiate_contract(self, requester_id, dataset_id, purpose):
        raise NotImplementedError


def make_settings(provider_id: str, tmp_path: Path) -> Settings:
    return Settings(
        provider_id=provider_id, port=8001, public_url="http://test", api_keys=KEYS, own_api_key="",
        data_simulation_path=str(MODULE_ROOT.parent / "data-simulation"),
        data_space_url="http://unused", data_space_token="", log_readers=["dashboard_operator"],
        runtime_dir=tmp_path, providers_config=MODULE_ROOT / "config" / "providers.yaml",
        catalogue_refresh_seconds=30,
    )


@pytest.fixture
def stub():
    return StubDataSpace()


@pytest.fixture
def traffic(stub, tmp_path):
    return TestClient(create_app(make_settings("traffic_sensor_1", tmp_path), data_space=stub, background=False))


@pytest.fixture
def bus(stub, tmp_path):
    return TestClient(create_app(make_settings("bus_line_12", tmp_path), data_space=stub, background=False))
