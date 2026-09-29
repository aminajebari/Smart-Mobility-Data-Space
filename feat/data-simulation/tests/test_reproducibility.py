import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))
from simulators.traffic_sensor import TrafficSensor


def test_same_seed_gives_same_sequence():
    """Deux instances avec le même seed doivent produire exactement les mêmes valeurs."""
    p1 = TrafficSensor("traffic_sensor_1")
    p2 = TrafficSensor("traffic_sensor_1")

    ts = datetime(2026, 9, 26, 10, 0, 0)
    r1 = p1.generate_record(ts)
    r2 = p2.generate_record(ts)

    assert r1["speed"] == r2["speed"]
    assert r1["traffic_density"] == r2["traffic_density"]