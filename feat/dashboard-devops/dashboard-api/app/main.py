"""Dashboard API (backend-for-frontend).

Aggregates the documented REST APIs of every module into the single
`DashboardData` document expected by the React dashboard. It never reads
another module's files: providers through their APIs (policy-checked, as the
`dashboard_operator` participant), governance through the Data Space API and
model performance through the Edge AI API.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def parse_mapping(raw: str) -> dict[str, str]:
    return dict(item.split("=", 1) for item in (p.strip() for p in raw.split(",")) if "=" in item)


PROVIDERS = {
    # provider_id: (display name, type label, icon, primary dataset)
    "traffic_sensor_1": ("Urban Traffic Sensors", "Road telemetry", "signal", "traffic_sensor_1.traffic_flow"),
    "bus_line_12": ("Tunis Bus Network - L12", "Public transit", "bus", "bus_line_12.vehicle_status"),
    "parking_lot_5": ("Smart Parking Lot 5", "Parking network", "parking", "parking_lot_5.occupancy"),
    "bikes_zone_a": ("Shared Bikes - Zone A", "Bikes & scooters", "bike", "bikes_zone_a.fleet_status"),
}
FORECAST_DATASET = "traffic_sensor_1.congestion_forecast"


class Settings:
    def __init__(self):
        self.provider_urls = parse_mapping(os.environ.get(
            "PROVIDER_URLS",
            "traffic_sensor_1=http://localhost:8001,bus_line_12=http://localhost:8002,"
            "parking_lot_5=http://localhost:8003,bikes_zone_a=http://localhost:8004"))
        self.data_space_url = os.environ.get("DATA_SPACE_URL", "http://localhost:8010").rstrip("/")
        self.edge_url = os.environ.get("EDGE_URL", "http://localhost:8020").rstrip("/")
        self.api_key = os.environ.get("DASHBOARD_API_KEY", "")
        self.participant_id = os.environ.get("DASHBOARD_PARTICIPANT_ID", "dashboard_operator")
        self.purpose = os.environ.get("DASHBOARD_PURPOSE", "monitoring")
        self.cache_seconds = float(os.environ.get("DASHBOARD_CACHE_SECONDS", "3"))
        self.traffic_points = int(os.environ.get("DASHBOARD_TRAFFIC_POINTS", "24"))
        self.stale_after_seconds = int(os.environ.get("PROVIDER_STALE_SECONDS", "120"))
        self.cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")


def ago(timestamp: Optional[str]) -> str:
    if not timestamp:
        return "no data"
    seconds = int((datetime.now() - datetime.fromisoformat(timestamp).replace(tzinfo=None)).total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds} sec ago"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def age_seconds(timestamp: Optional[str]) -> float:
    if not timestamp:
        return float("inf")
    return (datetime.now() - datetime.fromisoformat(timestamp).replace(tzinfo=None)).total_seconds()


class Aggregator:
    def __init__(self, settings: Settings, http: Optional[httpx.Client] = None):
        self.s = settings
        self.http = http or httpx.Client(timeout=3)
        self.pool = ThreadPoolExecutor(max_workers=12)
        self._cache: tuple[float, dict] | None = None
        self._lock = threading.Lock()

    # -- raw calls --------------------------------------------------------------
    def health(self, service_id: str, name: str, url: str) -> dict:
        started = time.perf_counter()
        try:
            response = self.http.get(f"{url}/health")
            latency = round((time.perf_counter() - started) * 1000)
            body = response.json() if response.status_code == 200 else {}
            status = "healthy" if response.status_code == 200 and not body.get("last_error") else "warning"
            if latency > 800:
                status = "warning"
        except httpx.HTTPError:
            latency, status, body = None, "offline", {}
        return {"id": service_id, "name": name, "endpoint": url, "status": status, "latency": latency, "_body": body}

    def provider_data(self, provider_id: str, dataset_id: str, limit: int) -> Optional[dict]:
        url = self.s.provider_urls.get(provider_id)
        if not url:
            return None
        params = {"dataset_id": dataset_id, "purpose": self.s.purpose, "limit": limit}
        headers = {"X-API-Key": self.s.api_key} if self.s.api_key else {}
        try:
            response = self.http.get(f"{url}/data", params=params, headers=headers)
            if response.status_code == 403 and "contract" in response.text:
                self.http.post(f"{self.s.data_space_url}/contracts", json={
                    "requester_id": self.s.participant_id, "dataset_id": dataset_id, "purpose": self.s.purpose})
                response = self.http.get(f"{url}/data", params=params, headers=headers)
            return response.json() if response.status_code == 200 else None
        except httpx.HTTPError:
            return None

    def get_json(self, url: str, **params):
        try:
            response = self.http.get(url, params=params)
            return response.json() if response.status_code == 200 else None
        except httpx.HTTPError:
            return None

    # -- aggregation ----------------------------------------------------------------
    def dashboard(self) -> dict:
        with self._lock:
            if self._cache and time.monotonic() - self._cache[0] < self.s.cache_seconds:
                return self._cache[1]
            data = self._build()
            self._cache = (time.monotonic(), data)
            return data

    def _build(self) -> dict:
        submit = self.pool.submit
        health_jobs = [submit(self.health, "data-space", "Data Space governance (Gaia-X)", self.s.data_space_url),
                       submit(self.health, "edge-ai", "Edge AI prediction", self.s.edge_url)]
        health_jobs += [submit(self.health, pid, f"Provider API - {PROVIDERS[pid][0]}", url)
                        for pid, url in self.s.provider_urls.items() if pid in PROVIDERS]
        data_jobs = {pid: submit(self.provider_data, pid, PROVIDERS[pid][3],
                                 self.s.traffic_points * 5 if pid == "traffic_sensor_1" else 10)
                     for pid in PROVIDERS}
        forecast_job = submit(self.provider_data, "traffic_sensor_1", FORECAST_DATASET, 1)
        model_job = submit(self.get_json, f"{self.s.edge_url}/model-info")
        audit_job = submit(self.get_json, f"{self.s.data_space_url}/audit", limit=200)
        stats_job = submit(self.get_json, f"{self.s.data_space_url}/audit/stats")
        participants_job = submit(self.get_json, f"{self.s.data_space_url}/participants")
        catalogue_job = submit(self.get_json, f"{self.s.data_space_url}/catalogue")

        services = [j.result() for j in health_jobs]
        health_by_id = {s["id"]: s for s in services}
        data = {pid: job.result() for pid, job in data_jobs.items()}
        names = {p["id"]: p["name"] for p in (participants_job.result() or [])}
        titles = {d["id"]: d["title"] for d in (catalogue_job.result() or [])}

        providers = []
        for pid, (name, type_label, icon, _) in PROVIDERS.items():
            records = (data[pid] or {}).get("records", [])
            last_ts = records[-1]["timestamp"] if records else None
            online = health_by_id.get(pid, {}).get("status") in ("healthy", "warning") and data[pid] is not None
            providers.append({"id": pid, "name": name, "type": type_label, "icon": icon,
                              "status": "connected" if online and age_seconds(last_ts) < self.s.stale_after_seconds
                              else "disconnected",
                              "lastSync": ago(last_ts)})

        traffic_records = (data["traffic_sensor_1"] or {}).get("records", [])
        return {
            "mode": "live",
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
            "providers": providers,
            "services": [{k: v for k, v in s.items() if not k.startswith("_")} for s in services],
            "kpis": self._kpis(data, providers),
            "traffic": self._traffic(traffic_records),
            "predictions": self._predictions(forecast_job.result(), model_job.result()),
            "exchanges": self._exchanges(audit_job.result() or [], names, titles),
            "exchangeStats": stats_job.result() or {"total": 0, "allow": 0, "deny": 0},
        }

    def _kpis(self, data: dict, providers: list[dict]) -> list[dict]:
        traffic = (data["traffic_sensor_1"] or {}).get("records", [])
        recent, earlier = traffic[-12:], traffic[-24:-12]
        mean = lambda rows, key: sum(r.get(key, 0) for r in rows) / len(rows) if rows else None  # noqa: E731
        speed, speed_before = mean(recent, "speed"), mean(earlier, "speed")
        density, density_before = mean(recent, "traffic_density"), mean(earlier, "traffic_density")
        latest = {pid: (d or {}).get("records", [])[-1:] for pid, d in data.items()}
        incidents = [pid for pid, rows in latest.items() if rows and rows[0].get("incident")]
        parking = latest.get("parking_lot_5") or []
        occupancy = parking[0]["occupancy"] if parking else None
        online = sum(p["status"] == "connected" for p in providers)

        def delta(now, before, pct=True):
            if now is None or before is None or before == 0:
                return "no baseline yet", "neutral"
            change = (now - before) / before * 100
            trend = "up" if change > 2 else "down" if change < -2 else "neutral"
            return f"{change:+.0f}% vs previous minute", trend

        speed_detail, speed_trend = delta(speed, speed_before)
        density_detail, density_trend = delta(density, density_before)
        return [
            {"id": "speed", "label": "Average speed", "icon": "speed", "trend": speed_trend, "detail": speed_detail,
             "value": f"{speed:.1f} km/h" if speed is not None else "n/a"},
            {"id": "density", "label": "Traffic density", "icon": "density", "trend": density_trend,
             "detail": density_detail, "value": f"{density * 100:.0f}%" if density is not None else "n/a"},
            {"id": "incidents", "label": "Active incidents", "icon": "incident",
             "trend": "up" if incidents else "neutral", "value": str(len(incidents)),
             "detail": ", ".join(PROVIDERS[p][0] for p in incidents) if incidents else "All providers nominal"},
            {"id": "parking", "label": "Parking occupancy", "icon": "parking", "trend": "neutral",
             "value": f"{occupancy * 100:.0f}%" if occupancy is not None else "n/a",
             "detail": f"{round(occupancy * 120)} / 120 spaces" if occupancy is not None else "provider offline"},
            {"id": "providers", "label": "Active providers", "icon": "provider", "trend": "neutral",
             "value": f"{online} / {len(providers)}",
             "detail": "All connections online" if online == len(providers) else f"{len(providers) - online} offline"},
        ]

    def _traffic(self, records: list[dict]) -> list[dict]:
        if not records:
            return []
        step = max(1, len(records) // self.s.traffic_points)
        points = []
        for i in range(0, len(records), step):
            chunk = records[i:i + step]
            points.append({
                "time": datetime.fromisoformat(chunk[-1]["timestamp"]).strftime("%H:%M:%S"),
                "density": round(sum(r["traffic_density"] for r in chunk) / len(chunk) * 100, 1),
                "speed": round(sum(r["speed"] for r in chunk) / len(chunk), 1),
                "incident": any(r.get("incident") for r in chunk),
            })
        return points[-self.s.traffic_points:]

    def _predictions(self, forecast: Optional[dict], model: Optional[dict]) -> list[dict]:
        records = (forecast or {}).get("records", [])
        if not records:
            return [{"id": "probability", "label": "Congestion probability", "value": "waiting",
                     "detail": "No forecast published by the edge node yet", "confidence": 0, "severity": "low"}]
        p = records[-1]
        probability = p["congestion_probability"]
        confidence = round(max(probability, 1 - probability) * 100)
        level = p["traffic_level"]
        severity = {"severe": "high", "heavy": "high", "moderate": "medium"}.get(level, "low")
        f1 = (model or {}).get("metrics", {}).get("random_forest_onnx", {}).get("f1")
        horizon = (model or {}).get("horizon", 6)
        return [
            {"id": "probability", "label": "Congestion probability", "value": f"{probability * 100:.0f}%",
             "detail": f"Next {horizon} sensor readings · model F1 {f1:.2f}" if f1 else f"Next {horizon} readings",
             "confidence": confidence, "severity": "high" if probability >= 0.5 else "low"},
            {"id": "level", "label": "Predicted traffic level", "value": level.replace("_", " ").title(),
             "detail": f"Sensor traffic_sensor_1 · {p['timestamp'][11:19]}", "confidence": confidence,
             "severity": severity},
            {"id": "travel", "label": "Estimated travel time", "value": f"{p['estimated_travel_time_min']:.0f} min",
             "detail": "5 km corridor at recent mean speed", "confidence": confidence, "severity": severity},
        ]

    def _exchanges(self, audit: list[dict], names: dict, titles: dict) -> list[dict]:
        # the dashboard's own polling is audited too; hide it here so partner exchanges stay visible
        shown = [e for e in audit if e["requester_id"] != self.s.participant_id][:10]
        return [{
            "id": f"audit-{e['id']}",
            "source": names.get(e["provider_id"], e["provider_id"] or "unknown"),
            "destination": names.get(e["requester_id"], e["requester_id"]),
            "dataset": f"{titles.get(e['dataset_id'], e['dataset_id'])} · {e['purpose']}",
            "authorization": "authorized" if e["decision"] == "allow" else "denied",
            "timestamp": e["timestamp"][11:19],
            "reason": e["reason"],
        } for e in shown]


def create_app(settings: Optional[Settings] = None, http: Optional[httpx.Client] = None) -> FastAPI:
    settings = settings or Settings()
    aggregator = Aggregator(settings, http)
    app = FastAPI(title="Smart Mobility Dashboard API", version="1.0.0",
                  description="Aggregates provider, Data Space and Edge AI APIs for the dashboard.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"], allow_headers=["*"])

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "service": "dashboard-api"}

    @app.get("/api/dashboard", tags=["dashboard"])
    def dashboard():
        return aggregator.dashboard()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("DASHBOARD_API_PORT", "8000")))
