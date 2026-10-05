"""Edge inference service.

Runs the ONNX congestion model locally. A background loop pulls the latest
standardized records through the traffic provider API (Module 2, policy-checked),
predicts locally and publishes only the prediction back as a derived dataset.
"""
import json
import logging
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .features import FEATURES, WINDOW, traffic_level, window_features

log = logging.getLogger("edge_ai")
MODULE_ROOT = Path(__file__).parent.parent


class PredictRequest(BaseModel):
    records: list[dict] = Field(..., min_length=1,
                                description=f"Time-ordered traffic records (shared schema); the last {WINDOW} are used")


class EdgeModel:
    def __init__(self, model_dir: Path):
        self.metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
        self.path = model_dir / f"{self.metadata['model_name']}.onnx"
        self.session = ort.InferenceSession(str(self.path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.threshold = self.metadata.get("threshold", 0.5)

    def predict(self, records: list[dict], corridor_km: float) -> dict:
        window = records[-WINDOW:]
        features = window_features(window)
        started = time.perf_counter()
        probability = float(self.session.run(None, {self.input_name: np.asarray([features], dtype=np.float32)})[1][0, 1])
        latency = (time.perf_counter() - started) * 1000
        last = window[-1]
        mean_speed = float(np.mean([r.get("speed", 0.0) for r in window]))
        return {
            "timestamp": last["timestamp"],
            "predicted_at": datetime.now().isoformat(timespec="seconds"),
            "provider_id": last.get("provider_id"),
            "congestion_probability": round(probability, 4),
            "congested": probability >= self.threshold,
            "traffic_level": traffic_level(probability, float(last.get("traffic_density", 0.0))),
            "horizon_records": self.metadata["horizon"],
            "current_speed": last.get("speed"),
            "current_density": last.get("traffic_density"),
            "current_incident": bool(last.get("incident")),
            # heuristic, not learned: time to cross the monitored corridor at the recent mean speed
            "estimated_travel_time_min": round(corridor_km / max(mean_speed, 5.0) * 60, 1),
            "model_version": self.metadata["model_version"],
            "inference_ms": round(latency, 3),
            "records_used": len(window),
        }


class EdgeLoop:
    """Pull -> predict locally -> publish result. Raw records are never stored or forwarded."""

    def __init__(self, model: EdgeModel, history: deque, http: Optional[httpx.Client] = None):
        self.model = model
        self.history = history
        self.http = http or httpx.Client(timeout=5)
        self.traffic_url = os.environ.get("TRAFFIC_API_URL", "http://localhost:8001").rstrip("/")
        self.data_space_url = os.environ.get("DATA_SPACE_URL", "http://localhost:8010").rstrip("/")
        self.api_key = os.environ.get("EDGE_API_KEY", "")
        self.participant_id = os.environ.get("EDGE_PARTICIPANT_ID", "edge_node_1")
        self.source_dataset = os.environ.get("EDGE_SOURCE_DATASET", "traffic_sensor_1.traffic_flow")
        self.target_dataset = os.environ.get("EDGE_TARGET_DATASET", "traffic_sensor_1.congestion_forecast")
        self.purpose = os.environ.get("EDGE_PURPOSE", "congestion_prediction")
        self.interval = float(os.environ.get("EDGE_POLL_SECONDS", "5"))
        self.corridor_km = float(os.environ.get("CORRIDOR_KM", "5"))
        self.last_error: Optional[str] = None
        self.last_published_ts: Optional[str] = None
        self.stop = threading.Event()

    def negotiate_contract(self):
        response = self.http.post(f"{self.data_space_url}/contracts", json={
            "requester_id": self.participant_id, "dataset_id": self.source_dataset, "purpose": self.purpose})
        response.raise_for_status()
        log.info("data-sharing contract %s obtained for %s", response.json()["id"], self.source_dataset)

    def fetch(self) -> list[dict]:
        params = {"dataset_id": self.source_dataset, "purpose": self.purpose, "limit": WINDOW}
        headers = {"X-API-Key": self.api_key}
        response = self.http.get(f"{self.traffic_url}/data", params=params, headers=headers)
        if response.status_code == 403 and "contract" in json.dumps(response.json()):
            self.negotiate_contract()
            response = self.http.get(f"{self.traffic_url}/data", params=params, headers=headers)
        response.raise_for_status()
        return response.json()["records"]

    def tick(self) -> Optional[dict]:
        records = self.fetch()
        if not records:
            return None
        prediction = self.model.predict(records, self.corridor_km)
        if prediction["timestamp"] != self.last_published_ts:
            self.history.append(prediction)
            published = {k: prediction[k] for k in ("timestamp", "predicted_at", "congestion_probability", "congested",
                                                    "traffic_level", "estimated_travel_time_min", "model_version")}
            self.http.post(f"{self.traffic_url}/publish", headers={"X-API-Key": self.api_key},
                           json={"dataset_id": self.target_dataset, "records": [published]}).raise_for_status()
            self.last_published_ts = prediction["timestamp"]
        return prediction

    def run(self):
        while not self.stop.is_set():
            try:
                self.tick()
                self.last_error = None
            except Exception as exc:  # provider or data space not reachable yet: keep retrying
                self.last_error = str(exc)
                log.warning("edge loop: %s", exc)
            self.stop.wait(self.interval)


def create_app(model_dir: Optional[Path] = None, run_loop: Optional[bool] = None) -> FastAPI:
    model_dir = Path(model_dir or os.environ.get("EDGE_MODEL_DIR", MODULE_ROOT / "models"))
    run_loop = run_loop if run_loop is not None else os.environ.get("EDGE_LOOP_ENABLED", "true").lower() == "true"
    model = EdgeModel(model_dir)
    history: deque = deque(maxlen=int(os.environ.get("EDGE_HISTORY_SIZE", "500")))
    loop = EdgeLoop(model, history)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if run_loop:
            threading.Thread(target=loop.run, daemon=True, name="edge-loop").start()
        yield
        loop.stop.set()

    app = FastAPI(title="Edge AI - Congestion prediction", version=model.metadata["model_version"], lifespan=lifespan,
                  description="Local ONNX inference. Shares predictions, never raw training data.")
    app.state.loop = loop

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "service": "edge-ai", "model": model.path.name, "loop_enabled": run_loop,
                "predictions": len(history), "last_error": loop.last_error}

    @app.get("/model-info", tags=["model"])
    def model_info():
        return {**model.metadata, "model_file": model.path.name, "runtime": f"onnxruntime {ort.__version__}"}

    @app.post("/predict", tags=["model"])
    def predict(body: PredictRequest):
        try:
            return model.predict(body.records, loop.corridor_km)
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=f"invalid records: {exc}")

    @app.get("/predictions/latest", tags=["predictions"])
    def latest_prediction():
        if not history:
            raise HTTPException(status_code=404, detail="no prediction yet")
        return history[-1]

    @app.get("/predictions", tags=["predictions"])
    def predictions(limit: int = Query(50, ge=1, le=500)):
        return list(history)[-limit:]

    return app


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("EDGE_PORT", "8020")))
