import numpy as np
from datetime import datetime
from .base_provider import BaseProvider

HOURLY_SPEED_KMH = {
    0: 55, 1: 55, 2: 55, 3: 55, 4: 50, 5: 45,
    6: 35, 7: 22, 8: 18, 9: 25, 10: 35, 11: 38,
    12: 35, 13: 33, 14: 35, 15: 32, 16: 28, 17: 18,
    18: 16, 19: 22, 20: 32, 21: 40, 22: 48, 23: 52,
}

# États possibles et leurs caractéristiques
STATES = {
    "normal":     {"speed_factor": 1.0,  "density_range": (0.05, 0.3)},
    "buildup":    {"speed_factor": 0.6,  "density_range": (0.4, 0.6)},
    "incident":   {"speed_factor": 0.2,  "density_range": (0.7, 0.9)},
    "congestion": {"speed_factor": 0.05, "density_range": (0.85, 1.0)},
    "recovery":   {"speed_factor": 0.7,  "density_range": (0.3, 0.5)},
}

# Probabilité de transition d'un état vers un autre, à CHAQUE tick
TRANSITIONS = {
    "normal":     {"normal": 0.96, "buildup": 0.04},
    "buildup":    {"buildup": 0.85, "incident": 0.10, "normal": 0.05},
    "incident":   {"incident": 0.5, "congestion": 0.4, "recovery": 0.1},
    "congestion": {"congestion": 0.7, "recovery": 0.3},
    "recovery":   {"recovery": 0.7, "normal": 0.3},
}


class TrafficSensor(BaseProvider):
    def __init__(self, provider_id: str):
        super().__init__(provider_id)
        self.state = "normal"  # état de départ

    def _next_state(self):
        probs = TRANSITIONS[self.state]
        states = list(probs.keys())
        weights = list(probs.values())
        self.state = self.rng.choice(states, p=weights)

    def generate_record(self, timestamp: datetime) -> dict:
        self._next_state()  # le capteur "décide" tout seul de son évolution

        hour = timestamp.hour
        base_speed = HOURLY_SPEED_KMH[hour]
        state_info = STATES[self.state]

        speed = max(0, self.rng.normal(base_speed * state_info["speed_factor"], 3))
        density = round(self.rng.uniform(*state_info["density_range"]), 2)
        incident = self.state in ("incident", "congestion")

        lat, lon = self.config["location"]
        return {
            "provider_id": self.provider_id,
            "timestamp": timestamp.isoformat(),
            "latitude": lat,
            "longitude": lon,
            "speed": round(speed, 1),
            "traffic_density": density,
            "incident": incident,
        }