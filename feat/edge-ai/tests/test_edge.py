import json
import sys
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from edge_ai.features import FEATURES, HORIZON, WINDOW, build_dataset, traffic_level, window_features  # noqa: E402
from edge_ai.service import EdgeLoop, EdgeModel, create_app  # noqa: E402


def records(n, speed, density, incident, start=datetime(2026, 9, 28, 10, 0)):
    return [{"provider_id": "traffic_sensor_1", "timestamp": (start + timedelta(seconds=5 * i)).isoformat(),
             "latitude": 36.8065, "longitude": 10.1815, "speed": speed, "traffic_density": density,
             "incident": incident} for i in range(n)]


NORMAL = records(WINDOW, 50, 0.15, False)
CONGESTED = records(WINDOW, 3, 0.95, True)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(run_loop=False))


def test_feature_vector_shape():
    assert len(window_features(NORMAL)) == len(FEATURES)


def test_labels_look_ahead():
    seq = records(20, 50, 0.1, False) + records(10, 3, 0.95, True)
    X, y = build_dataset(seq)
    assert len(X) == len(seq) - WINDOW - HORIZON + 1
    assert y[0] == 0 and y[-1] == 1


def test_traffic_level():
    assert traffic_level(0.05, 0.1) == "free_flow"
    assert traffic_level(0.9, 0.5) == "severe"


def test_model_info_reports_metrics_and_benchmark(client):
    info = client.get("/model-info").json()
    assert info["features"] == FEATURES
    assert info["metrics"]["random_forest"]["f1"] > info["metrics"]["persistence_baseline"]["f1"]
    assert info["benchmark"]["model_size_bytes"]["onnx"] > 0


def test_predict_separates_normal_from_congested(client):
    low = client.post("/predict", json={"records": NORMAL}).json()
    high = client.post("/predict", json={"records": CONGESTED}).json()
    assert low["congestion_probability"] < 0.5 < high["congestion_probability"]
    assert high["congested"] and high["traffic_level"] == "severe"
    assert set(low) >= {"timestamp", "congestion_probability", "traffic_level", "model_version"}


def test_predict_validation(client):
    assert client.post("/predict", json={"records": []}).status_code == 422
    assert client.post("/predict", json={"records": [{"speed": 3}]}).status_code == 422


def test_loop_fetches_predicts_and_publishes_only_results():
    calls = []

    class FakeResponse:
        def __init__(self, status, body):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

    class FakeHttp:
        contract = False

        def get(self, url, params, headers):
            calls.append(("GET", url))
            if not self.contract:
                return FakeResponse(403, {"detail": {"reason": "no active data-sharing contract"}})
            return FakeResponse(200, {"records": CONGESTED})

        def post(self, url, json, headers=None):
            calls.append(("POST", url, json))
            if url.endswith("/contracts"):
                self.contract = True
                return FakeResponse(201, {"id": "ctr-1"})
            return FakeResponse(200, {})

    history = deque()
    loop = EdgeLoop(EdgeModel(ROOT / "models"), history, http=FakeHttp())
    prediction = loop.tick()
    assert prediction["congested"]
    assert any(c[0] == "POST" and c[1].endswith("/contracts") for c in calls)
    published = [c for c in calls if c[0] == "POST" and c[1].endswith("/publish")]
    assert len(published) == 1
    sent = published[0][2]["records"][0]
    assert "speed" not in sent and "latitude" not in sent  # results only, no raw data
    loop.tick()  # same latest record -> not re-published
    assert len([c for c in calls if c[0] == "POST" and c[1].endswith("/publish")]) == 1
    assert len(history) == 1
