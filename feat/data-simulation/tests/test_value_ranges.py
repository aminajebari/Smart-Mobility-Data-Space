import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from simulators.traffic_sensor import TrafficSensor
from simulators.smart_parking import SmartParking
from simulators.public_transport import PublicTransport
from simulators.shared_mobility import SharedMobility


def test_traffic_sensor_ranges():
    p = TrafficSensor("traffic_sensor_1")
    for _ in range(50):
        r = p.generate_record(datetime.now())
        assert r["speed"] >= 0
        assert 0 <= r["traffic_density"] <= 1
        assert isinstance(r["incident"], bool)


def test_smart_parking_ranges():
    p = SmartParking("parking_lot_5")
    for _ in range(50):
        r = p.generate_record(datetime.now())
        assert 0 <= r["occupancy"] <= 1


def test_public_transport_ranges():
    p = PublicTransport("bus_line_12")
    for _ in range(50):
        r = p.generate_record(datetime.now())
        assert r["delay_min"] >= 0
        assert r["route_id"] == "L12"


def test_shared_mobility_ranges():
    p = SharedMobility("bikes_zone_a")
    for _ in range(50):
        r = p.generate_record(datetime.now())
        assert 0 <= r["battery_level"] <= 100
        assert r["status"] in ("available", "in_use", "low_battery")