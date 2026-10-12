"""Guided live demo of the final integration scenario (the 7 steps of docs/DEMO.md).

Run it against a running stack, in a terminal shown to the audience:
    python scripts/run_local.py --demo       # terminal 1, without Docker (no traffic simulator competing with the scenario)
    python scripts/demo.py                   # terminal 2

    docker compose up --build -d             # with Docker
    python scripts/demo.py --docker          # stops the traffic simulator during the scenario, restarts it after

Options: --auto (no "press Enter" pauses), --bonus (sovereignty extras: denied dataset, contract negotiation).
Service URLs and demo keys come from the same environment variables as scripts/smoke_test.py.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "feat" / "data-simulation"
URLS = {
    "traffic": os.environ.get("TRAFFIC_API_URL", "http://127.0.0.1:8001"),
    "bus": os.environ.get("BUS_API_URL", "http://127.0.0.1:8002"),
    "parking": os.environ.get("PARKING_API_URL", "http://127.0.0.1:8003"),
    "bikes": os.environ.get("BIKES_API_URL", "http://127.0.0.1:8004"),
    "data_space": os.environ.get("DATA_SPACE_URL", "http://127.0.0.1:8010"),
    "edge": os.environ.get("EDGE_URL", "http://127.0.0.1:8020"),
    "dashboard_api": os.environ.get("DASHBOARD_API_URL", "http://127.0.0.1:8000"),
}
KEYS = {
    "city": os.environ.get("CITY_API_KEY", "city-demo-key"),
    "startup": os.environ.get("STARTUP_API_KEY", "startup-demo-key"),
    "bus": os.environ.get("BUS_API_KEY", "bus-demo-key"),
}
FORECAST = "traffic_sensor_1.congestion_forecast"
TRAFFIC = "traffic_sensor_1.traffic_flow"

os.system("")  # enables ANSI colours in the Windows console
BOLD, DIM, GREEN, RED, YELLOW, CYAN, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[0m"
http = httpx.Client(timeout=10)
args = argparse.Namespace(auto=True)


def step(number, title: str, says: str):
    if not args.auto:
        input(f"\n{DIM}[Enter] next step{RESET}")
    print(f"\n{BOLD}{CYAN}=== {number}. {title} ==={RESET}")
    print(f"{DIM}{says}{RESET}")


def ok(text: str):
    print(f"  {GREEN}ALLOW{RESET} {text}")


def deny(text: str):
    print(f"  {RED}DENY {RESET} {text}")


def dashboard() -> dict:
    return http.get(f"{URLS['dashboard_api']}/api/dashboard").json()


def bar(percent: float, width: int = 30) -> str:
    filled = round(percent / 100 * width)
    colour = RED if percent >= 70 else YELLOW if percent >= 40 else GREEN
    return f"{colour}{'#' * filled}{RESET}{'.' * (width - filled)}"


def check_services():
    down = []
    for name, url in URLS.items():
        try:
            healthy = http.get(f"{url}/health", timeout=3).status_code == 200
        except httpx.HTTPError:
            healthy = False
        print(f"  {GREEN + 'up  ' if healthy else RED + 'DOWN'}{RESET} {name:<14} {url}")
        if not healthy:
            down.append(name)
    if down:
        sys.exit(f"\n{RED}services down: {down}. Start the stack first (see the top of this file).{RESET}")


def start_scenario() -> subprocess.Popen:
    if args.docker:
        subprocess.run(["docker", "compose", "stop", "traffic-simulator"], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = ["docker", "compose", "--profile", "demo", "run", "--rm", "scenario"]
        cwd = ROOT
    else:
        cmd, cwd = [sys.executable, "scenario/scenario_generator.py"], SIM
    return subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env={**os.environ, "PYTHONUTF8": "1"})


def live_scenario():
    """Steps 1-3: drive the congestion scenario and show sensor state next to the edge prediction."""
    scenario = start_scenario()
    early_warning = None
    fresh = False  # skip readings left over from an earlier congestion until the scenario's normal phase shows
    print(f"  {'time':<9} {'density':>7} {'speed':>10}  {'incident':<8}  edge AI congestion probability")
    try:
        while scenario.poll() is None:
            data = dashboard()
            point = data["traffic"][-1] if data["traffic"] else {}
            prediction = {p["id"]: p["value"] for p in data["predictions"]}
            raw = prediction.get("probability", "waiting")
            percent = float(raw.rstrip("%")) if raw.endswith("%") else 0.0
            incident = bool(point.get("incident"))
            fresh = fresh or not incident
            if not fresh:
                time.sleep(2)
                continue
            note = ""
            if percent >= 50 and not incident and early_warning is None:
                early_warning = time.time()
                note = f"  {BOLD}{YELLOW}<- congestion predicted, no incident reported yet{RESET}"
            elif incident and early_warning and early_warning is not True:
                note = f"  {BOLD}<- incident reported {time.time() - early_warning:.0f} s after the prediction{RESET}"
                early_warning = True
            print(f"  {time.strftime('%H:%M:%S'):<9} {point.get('density', 0):>6.0f}% {point.get('speed', 0):>6.1f} km/h"
                  f"  {(RED + 'YES' if incident else GREEN + 'no ') + RESET:<8}       {bar(percent)} {raw:>4}"
                  f" {prediction.get('level', '')}{note}")
            time.sleep(4)
    finally:
        if scenario.poll() is None:
            scenario.terminate()
        if args.docker:
            subprocess.run(["docker", "compose", "start", "traffic-simulator"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    global args
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docker", action="store_true", help="the stack runs with docker compose")
    parser.add_argument("--auto", action="store_true", help="do not pause between steps")
    parser.add_argument("--bonus", action="store_true", help="also show the sovereignty extras")
    args = parser.parse_args()

    print(f"{BOLD}Smart Mobility Data Space - live demo{RESET}")
    print(f"{DIM}dashboard: http://localhost:8080 (Docker) or http://localhost:5173 (npm run dev){RESET}")

    step(0, "System overview", "7 independent services; each provider keeps its raw data locally.")
    check_services()
    data = dashboard()
    print("  providers: " + ", ".join(
        f"{p['id']} ({'waiting for the scenario' if p['id'] == 'traffic_sensor_1' and p['status'] != 'connected' else p['status']})"
        for p in data["providers"]))

    step("1-3", "Congestion scenario + Edge AI prediction",
         "The traffic simulator goes normal -> rising density -> incident -> congestion (about 70 s).\n"
         "The provider API publishes each reading; the edge node predicts congestion locally (ONNX).")
    live_scenario()

    step(4, "A partner asks for the prediction", "City Planning Office (member) -> traffic API -> Data Space decides.")
    city = http.get(f"{URLS['traffic']}/data", params={"dataset_id": FORECAST, "purpose": "traffic_management", "limit": 1},
                    headers={"X-API-Key": KEYS["city"]})
    audit_ids = []
    if city.status_code == 200:
        body = city.json()
        audit_ids.append(body["authorization"]["audit_id"])
        record = body["records"][-1] if body["records"] else {}
        ok(f"HTTP 200 - {body['authorization']['reason']}")
        print(f"        result shared: congestion_probability={record.get('congestion_probability')}, "
              f"level={record.get('traffic_level')}, travel_time={record.get('estimated_travel_time_min')} min")
        print(f"        raw sensor fields shared: {sorted({'speed', 'traffic_density', 'latitude'} & record.keys()) or 'none'}")
    else:
        deny(f"HTTP {city.status_code} - {city.text}")

    step(5, "A startup asks for the same prediction", "Mobility Startup X has 'guest' membership.")
    startup = http.get(f"{URLS['traffic']}/data", params={"dataset_id": FORECAST, "purpose": "commercial", "limit": 1},
                       headers={"X-API-Key": KEYS["startup"]})
    reason = startup.json().get("detail", {})
    if isinstance(reason, dict) and "audit_id" in reason:
        audit_ids.append(reason["audit_id"])
    deny(f"HTTP {startup.status_code} - {reason.get('reason', reason) if isinstance(reason, dict) else reason}")

    step(6, "Audit trail", "Every decision is written to the Data Space audit log.")
    # the edge node's own polling is audited too; show the two decisions made above
    entries = [e for e in http.get(f"{URLS['data_space']}/audit", params={"limit": 200}).json() if e["id"] in audit_ids]
    for entry in sorted(entries, key=lambda e: e["id"]):
        colour = GREEN if entry["decision"] == "allow" else RED
        print(f"  #{entry['id']:<5} {entry['timestamp']}  {entry['requester_id']:<22} {entry['dataset_id']:<38} "
              f"purpose={entry['purpose']:<18} policy={entry['policy_type']:<14} {colour}{entry['decision']}{RESET}")

    if args.bonus:
        step("+", "Sovereignty extras", "A 'denied' dataset never leaves its provider; provider-to-provider contracts.")
        passengers = http.get(f"{URLS['bus']}/data", params={"dataset_id": "bus_line_12.passenger_counts"},
                              headers={"X-API-Key": KEYS["city"]})
        deny(f"bus passenger counts: HTTP {passengers.status_code}")
        bus = {"X-API-Key": KEYS["bus"]}
        refused = http.get(f"{URLS['bus']}/partners/data", headers=bus,
                           params={"dataset_id": TRAFFIC, "purpose": "route_optimization"})
        deny(f"bus -> traffic data for 'route_optimization': HTTP {refused.status_code}")
        contract = http.post(f"{URLS['bus']}/partners/contracts", headers=bus,
                             json={"dataset_id": TRAFFIC, "purpose": "traffic_management"})
        print(f"  contract for 'traffic_management': {contract.json().get('id')} ({contract.json().get('status')})")
        granted = http.get(f"{URLS['bus']}/partners/data", headers=bus,
                           params={"dataset_id": TRAFFIC, "purpose": "traffic_management", "limit": 5})
        (ok if granted.status_code == 200 else deny)(f"bus -> traffic data with the contract: HTTP {granted.status_code}")

    step(7, "Dashboard", "Providers, traffic indicators, AI prediction and exchange trace, updated live.")
    data = dashboard()
    print("  KPIs:        " + " | ".join(f"{k['label']}: {k['value']}" for k in data["kpis"]))
    print("  prediction:  " + " | ".join(f"{p['label']}: {p['value']}" for p in data["predictions"]))
    # hide the edge node's routine polling so the partner exchanges stay visible
    for exchange in [e for e in data["exchanges"] if not e["destination"].startswith("Edge AI")][:3]:
        colour = GREEN if exchange["authorization"] == "authorized" else RED
        print(f"  exchange:    {exchange['timestamp']} {exchange['source']} -> {exchange['destination']} "
              f"({exchange['dataset']}) {colour}{exchange['authorization']}{RESET}")
    print(f"\n{BOLD}{GREEN}Demo complete: simulate -> publish -> predict at the edge -> authorize -> audit -> visualize.{RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
