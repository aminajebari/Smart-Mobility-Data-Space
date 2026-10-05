"""Data access layer.

Raw provider data is read ONLY through Module 1's public access functions
(access/local_data_api.py); this module never opens Module 1's data files.
Results pushed with POST /publish are kept in this API's own local store.
"""
import importlib
import json
import math
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


class SimulationData:
    def __init__(self, data_simulation_path: str):
        if data_simulation_path not in sys.path:
            sys.path.append(data_simulation_path)
        self._api = importlib.import_module("access.local_data_api")

    def providers(self) -> list[str]:
        return sorted(self._api.list_available_providers())

    def latest(self, provider_id: str, limit: int) -> list[dict]:
        return self._api.get_latest_records(provider_id, limit)

    def since(self, provider_id: str, since: datetime) -> list[dict]:
        return self._api.get_records_since(provider_id, since)


class PublishedStore:
    """Append-only JSONL store for datasets published to this provider (e.g. edge predictions)."""
    MAX_RECORDS = 5000

    def __init__(self, directory: Path):
        self.directory = directory / "published"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, dataset_id: str) -> Path:
        return self.directory / f"{dataset_id}.jsonl"

    def append(self, dataset_id: str, records: list[dict]) -> int:
        with self._lock:
            path = self._path(dataset_id)
            existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
            lines = (existing + [json.dumps(r) for r in records])[-self.MAX_RECORDS:]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return len(lines)

    def read(self, dataset_id: str) -> list[dict]:
        path = self._path(dataset_id)
        if not path.exists():
            return []
        with self._lock:
            return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def filter_records(records: list[dict], since: Optional[datetime] = None, until: Optional[datetime] = None,
                   incident: Optional[bool] = None, lat: Optional[float] = None, lon: Optional[float] = None,
                   radius_km: Optional[float] = None) -> list[dict]:
    def keep(r: dict) -> bool:
        ts = datetime.fromisoformat(r["timestamp"]).replace(tzinfo=None) if "timestamp" in r else None
        if since and ts and ts < since:
            return False
        if until and ts and ts > until:
            return False
        if incident is not None and r.get("incident") != incident:
            return False
        if lat is not None and lon is not None and radius_km is not None and "latitude" in r:
            if distance_km(lat, lon, r["latitude"], r["longitude"]) > radius_km:
                return False
        return True

    return [r for r in records if keep(r)]
