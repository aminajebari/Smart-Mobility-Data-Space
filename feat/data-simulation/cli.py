import argparse
import time
from datetime import datetime, timedelta

from simulators.traffic_sensor import TrafficSensor
from simulators.public_transport import PublicTransport
from simulators.smart_parking import SmartParking
from simulators.shared_mobility import SharedMobility

PROVIDER_CLASSES = {
    "traffic_sensor": TrafficSensor,
    "public_transport": PublicTransport,
    "smart_parking": SmartParking,
    "shared_mobility": SharedMobility,
}


def main():
    parser = argparse.ArgumentParser(description="Lance un simulateur de mobilité.")
    parser.add_argument("action", choices=["start"], help="Action à effectuer")
    parser.add_argument("--provider", required=True, help="ID du provider (ex: traffic_sensor_1)")
    parser.add_argument("--count", type=int, help="Générer N lignes rapidement (mode batch) puis s'arrêter")
    args = parser.parse_args()

    import yaml
    from pathlib import Path
    config = yaml.safe_load((Path(__file__).parent / "config" / "config.yaml").read_text(encoding="utf-8"))
    provider_type = config["providers"][args.provider]["type"]
    rate_seconds = config["providers"][args.provider]["rate_seconds"]

    provider_class = PROVIDER_CLASSES[provider_type]
    provider = provider_class(args.provider)

    if args.count:
        current_time = datetime.now()
        for i in range(args.count):
            record = provider.generate_record(current_time)
            provider.write_record(record)
            current_time += timedelta(seconds=rate_seconds)
        print(f"[{args.provider}] {args.count} lignes générées.")
        return

    print(f"[{args.provider}] démarré (type={provider_type}, intervalle={rate_seconds}s). Ctrl+C pour arrêter.")
    try:
        while True:
            record = provider.generate_record(datetime.now())
            provider.write_record(record)
            print(record)
            time.sleep(rate_seconds)
    except KeyboardInterrupt:
        print(f"\n[{args.provider}] arrêté.")


if __name__ == "__main__":
    main()