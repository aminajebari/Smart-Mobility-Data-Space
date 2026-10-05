import numpy as np
from datetime import datetime
from .base_provider import BaseProvider

# États possibles de la flotte
STATES = {
    "normal":              {"battery_drain": 0.5, "low_battery_bias": 0.0},
    "forte_demande":        {"battery_drain": 1.2, "low_battery_bias": 0.15},
    "faible_disponibilite": {"battery_drain": 1.8, "low_battery_bias": 0.30},
}

TRANSITIONS = {
    "normal":               {"normal": 0.95, "forte_demande": 0.05},
    "forte_demande":         {"forte_demande": 0.6, "faible_disponibilite": 0.15, "normal": 0.25},
    "faible_disponibilite":  {"faible_disponibilite": 0.5, "forte_demande": 0.5},
}


class SharedMobility(BaseProvider):
    def __init__(self, provider_id: str):
        super().__init__(provider_id)
        self.state = "normal"

        fleet_size = self.config["fleet_size"]
        center_lat, center_lon = self.config["zone_center"]
        radius_deg = self.config["zone_radius_km"] / 111
        self.vehicle_positions = [
            (
                center_lat + self.rng.uniform(-radius_deg, radius_deg),
                center_lon + self.rng.uniform(-radius_deg, radius_deg),
            )
            for _ in range(fleet_size)
        ]
        self.vehicle_battery = [self.rng.uniform(40, 100) for _ in range(fleet_size)]

    def _next_state(self):
        probs = TRANSITIONS[self.state]
        states = list(probs.keys())
        weights = list(probs.values())
        self.state = self.rng.choice(states, p=weights)

    def generate_record(self, timestamp: datetime) -> dict:
        self._next_state()
        state_info = STATES[self.state]

        vehicle_idx = int(self.rng.integers(0, len(self.vehicle_positions)))
        lat, lon = self.vehicle_positions[vehicle_idx]

        center_lat, center_lon = self.config["zone_center"]
        radius_deg = self.config["zone_radius_km"] / 111
        new_lat = np.clip(lat + self.rng.normal(0, 0.0005), center_lat - radius_deg, center_lat + radius_deg)
        new_lon = np.clip(lon + self.rng.normal(0, 0.0005), center_lon - radius_deg, center_lon + radius_deg)
        self.vehicle_positions[vehicle_idx] = (new_lat, new_lon)

        drain = state_info["battery_drain"]
        self.vehicle_battery[vehicle_idx] = max(0, self.vehicle_battery[vehicle_idx] - self.rng.uniform(0, drain))
        battery = self.vehicle_battery[vehicle_idx]

        low_bias = state_info["low_battery_bias"]
        effective_battery = max(0, battery - low_bias * 100)
        status = "low_battery" if effective_battery < 15 else "in_use" if self.rng.random() < 0.3 else "available"

        return {
            "provider_id": self.provider_id,
            "timestamp": timestamp.isoformat(),
            "latitude": round(new_lat, 6),
            "longitude": round(new_lon, 6),
            "battery_level": round(battery, 1),
            "status": status,
            "incident": False,
        }