"""Feature engineering shared by training and edge inference.

Input: a time-ordered window of standardized traffic records (shared JSON schema).
Output: one feature vector describing the current state and its recent trend.
"""
import math
from datetime import datetime

import numpy as np

WINDOW = 6  # records used per prediction (30 s at the sensor's 5 s rate)
HORIZON = 6  # label: congestion within the next HORIZON records

FEATURES = [
    "speed", "traffic_density", "incident",
    "speed_mean", "speed_min", "density_mean", "density_max",
    "density_slope", "speed_slope", "incident_ratio",
    "hour_sin", "hour_cos",
]


def _slope(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=np.float64)
    return float(np.polyfit(x, values, 1)[0])


def window_features(window: list[dict]) -> list[float]:
    if not window:
        raise ValueError("at least one record is required")
    window = window[-WINDOW:]
    speed = np.array([float(r.get("speed", 0.0)) for r in window])
    density = np.array([float(r.get("traffic_density", 0.0)) for r in window])
    incident = np.array([1.0 if r.get("incident") else 0.0 for r in window])
    ts = datetime.fromisoformat(window[-1]["timestamp"])
    hour = ts.hour + ts.minute / 60
    return [
        speed[-1], density[-1], incident[-1],
        speed.mean(), speed.min(), density.mean(), density.max(),
        _slope(density), _slope(speed), incident.mean(),
        math.sin(2 * math.pi * hour / 24), math.cos(2 * math.pi * hour / 24),
    ]


def is_congested(record: dict) -> bool:
    """Congestion event = incident flag raised by the sensor (incident or congestion state)."""
    return bool(record.get("incident"))


def build_dataset(records: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Sliding windows -> (X, y) where y = congestion within the next HORIZON records."""
    X, y = [], []
    for end in range(WINDOW, len(records) - HORIZON + 1):
        X.append(window_features(records[end - WINDOW:end]))
        y.append(int(any(is_congested(r) for r in records[end:end + HORIZON])))
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int64)


def traffic_level(probability: float, density: float) -> str:
    if probability >= 0.8 or density >= 0.85:
        return "severe"
    if probability >= 0.5:
        return "heavy"
    if probability >= 0.25 or density >= 0.4:
        return "moderate"
    return "free_flow"
