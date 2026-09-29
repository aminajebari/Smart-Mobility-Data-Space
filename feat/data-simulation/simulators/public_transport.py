import numpy as np
from datetime import datetime
from .base_provider import BaseProvider

# États possibles du bus
STATES = {
    "a_l_heure":       {"delay_base": 1.5, "delay_std": 1.0},
    "leger_retard":    {"delay_base": 5.0, "delay_std": 2.0},
    "retard_important": {"delay_base": 12.0, "delay_std": 4.0},
    "panne":           {"delay_base": 20.0, "delay_std": 5.0},
}

TRANSITIONS = {
    "a_l_heure":         {"a_l_heure": 0.95, "leger_retard": 0.05},
    "leger_retard":       {"leger_retard": 0.70, "retard_important": 0.10, "a_l_heure": 0.20},
    "retard_important":   {"retard_important": 0.5, "panne": 0.05, "leger_retard": 0.45},
    "panne":             {"panne": 0.4, "leger_retard": 0.6},
}


class PublicTransport(BaseProvider):
    def __init__(self, provider_id: str):
        super().__init__(provider_id)
        self.state = "a_l_heure"

    def _next_state(self):
        probs = TRANSITIONS[self.state]
        states = list(probs.keys())
        weights = list(probs.values())
        self.state = self.rng.choice(states, p=weights)

    def generate_record(self, timestamp: datetime) -> dict:
        self._next_state()

        stops = self.config["stops"]
        seconds_in_cycle = (timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second) % (len(stops) * 300)
        stop_index = int(seconds_in_cycle // 300) % len(stops)
        lat, lon = stops[stop_index]

        state_info = STATES[self.state]
        delay = max(0, self.rng.normal(state_info["delay_base"], state_info["delay_std"]))

        return {
            "provider_id": self.provider_id,
            "timestamp": timestamp.isoformat(),
            "latitude": lat,
            "longitude": lon,
            "route_id": self.config["route_id"],
            "delay_min": round(delay, 1),
            "incident": self.state == "panne",
        }