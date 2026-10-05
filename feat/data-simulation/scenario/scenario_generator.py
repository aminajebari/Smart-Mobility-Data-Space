import time
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from simulators.traffic_sensor import TrafficSensor

# Chaque phase dure N secondes et force un comportement précis
PHASES = [
    {"name": "normal",      "duration": 20, "speed_range": (45, 55), "density_range": (0.1, 0.3), "incident": False},
    {"name": "increasing",  "duration": 20, "speed_range": (25, 40), "density_range": (0.4, 0.6), "incident": False},
    {"name": "incident",    "duration": 10, "speed_range": (5, 15),  "density_range": (0.7, 0.85), "incident": True},
    {"name": "congestion",  "duration": 20, "speed_range": (0, 8),   "density_range": (0.85, 1.0), "incident": True},
]


def run_scenario(provider_id: str = "traffic_sensor_1", tick_seconds: int = 2):
    provider = TrafficSensor(provider_id)
    lat, lon = provider.config["location"]

    print(f"=== Démarrage du scénario de congestion sur {provider_id} ===")
    for phase in PHASES:
        print(f"--- Phase: {phase['name']} ({phase['duration']}s) ---")
        elapsed = 0
        while elapsed < phase["duration"]:
            speed = round(provider.rng.uniform(*phase["speed_range"]), 1)
            density = round(provider.rng.uniform(*phase["density_range"]), 2)
            record = {
                "provider_id": provider_id,
                "timestamp": datetime.now().isoformat(),
                "latitude": lat,
                "longitude": lon,
                "speed": speed,
                "traffic_density": density,
                "incident": phase["incident"],
            }
            provider.write_record(record)
            print(record)
            time.sleep(tick_seconds)
            elapsed += tick_seconds

    print("=== Scénario terminé ===")


if __name__ == "__main__":
    run_scenario()