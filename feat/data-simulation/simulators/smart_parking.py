import numpy as np
from datetime import datetime
from .base_provider import BaseProvider

HOURLY_OCCUPANCY = {
    0: 0.10, 1: 0.08, 2: 0.06, 3: 0.05, 4: 0.05, 5: 0.08,
    6: 0.15, 7: 0.35, 8: 0.65, 9: 0.80, 10: 0.85, 11: 0.88,
    12: 0.82, 13: 0.78, 14: 0.80, 15: 0.83, 16: 0.75, 17: 0.60,
    18: 0.45, 19: 0.35, 20: 0.25, 21: 0.20, 22: 0.15, 23: 0.12,
}

# États possibles du parking
STATES = {
    "normal":      {"offset": 0.0},
    "affluence":   {"offset": 0.12},   # événement local, parking qui se remplit plus vite
    "presque_plein": {"offset": 0.20},
    "retour_calme": {"offset": 0.05},
}

TRANSITIONS = {
    "normal":         {"normal": 0.95, "affluence": 0.05},
    "affluence":       {"affluence": 0.7, "presque_plein": 0.2, "retour_calme": 0.1},
    "presque_plein":   {"presque_plein": 0.6, "retour_calme": 0.4},
    "retour_calme":    {"retour_calme": 0.6, "normal": 0.4},
}


class SmartParking(BaseProvider):
    def __init__(self, provider_id: str):
        super().__init__(provider_id)
        self.state = "normal"

    def _next_state(self):
        probs = TRANSITIONS[self.state]
        states = list(probs.keys())
        weights = list(probs.values())
        self.state = self.rng.choice(states, p=weights)

    def generate_record(self, timestamp: datetime) -> dict:
        self._next_state()

        hour = timestamp.hour
        base_occ = HOURLY_OCCUPANCY[hour] + STATES[self.state]["offset"]
        occupancy = float(np.clip(self.rng.normal(base_occ, 0.04), 0, 1))
        lat, lon = self.config["location"]

        return {
            "provider_id": self.provider_id,
            "timestamp": timestamp.isoformat(),
            "latitude": lat,
            "longitude": lon,
            "occupancy": round(occupancy, 2),
            "incident": self.state == "presque_plein",
        }