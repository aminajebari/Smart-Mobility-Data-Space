import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

sys.path.append(str(Path(__file__).parent.parent))

from simulators.traffic_sensor import TrafficSensor
from simulators.smart_parking import SmartParking
from simulators.public_transport import PublicTransport
from simulators.shared_mobility import SharedMobility

# (provider_class, provider_id, tous les états attendus, état "de repos")
CASES = [
    (TrafficSensor, "traffic_sensor_1", {"normal", "buildup", "incident", "congestion", "recovery"}, "normal"),
    (SmartParking, "parking_lot_5", {"normal", "affluence", "presque_plein", "retour_calme"}, "normal"),
    (PublicTransport, "bus_line_12", {"a_l_heure", "leger_retard", "retard_important", "panne"}, "a_l_heure"),
    (SharedMobility, "bikes_zone_a", {"normal", "forte_demande", "faible_disponibilite"}, "normal"),
]

N_TICKS = 3000


def test_all_states_are_reachable():
    for cls, pid, expected_states, _ in CASES:
        p = cls(pid)
        ts = datetime(2026, 9, 28, 8, 0, 0)
        visited = set()
        for _ in range(N_TICKS):
            p.generate_record(ts)
            visited.add(p.state)
            ts += timedelta(seconds=5)
        assert visited == expected_states, f"{pid}: états jamais atteints = {expected_states - visited}"


def test_system_always_recovers():
    for cls, pid, _, rest_state in CASES:
        p = cls(pid)
        ts = datetime(2026, 9, 28, 8, 0, 0)
        consecutive_away = 0
        max_consecutive_away = 0
        for _ in range(N_TICKS):
            p.generate_record(ts)
            if p.state != rest_state:
                consecutive_away += 1
                max_consecutive_away = max(max_consecutive_away, consecutive_away)
            else:
                consecutive_away = 0
            ts += timedelta(seconds=5)
        assert max_consecutive_away < 300, f"{pid}: reste bloqué trop longtemps hors de l'état '{rest_state}'"


def test_state_distribution_is_realistic():
    for cls, pid, _, rest_state in CASES:
        p = cls(pid)
        ts = datetime(2026, 9, 28, 8, 0, 0)
        counts = Counter()
        for _ in range(N_TICKS):
            p.generate_record(ts)
            counts[p.state] += 1
            ts += timedelta(seconds=5)
        rest_ratio = counts[rest_state] / N_TICKS
        assert rest_ratio > 0.5, f"{pid}: trop peu de temps dans l'état de repos ({rest_ratio:.0%})"


def test_records_stay_valid_in_every_state():
    for cls, pid, _, _ in CASES:
        p = cls(pid)
        ts = datetime(2026, 9, 28, 8, 0, 0)
        for _ in range(500):
            record = p.generate_record(ts)
            p.validate(record)  # lève une exception si le schéma n'est pas respecté
            ts += timedelta(seconds=5)