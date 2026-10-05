"""Start the whole Smart Mobility Data Space locally, without Docker.

    python scripts/run_local.py               # services + live simulators
    python scripts/run_local.py --no-sim      # services only (uses existing sample data)

Ctrl+C stops everything. Logs go to runtime/logs/<service>.log.
Requires the Python dependencies of every module (see requirements-dev.txt).
"""
import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "feat" / "data-simulation"
API = ROOT / "feat" / "distributed-api"
DS = ROOT / "feat" / "data-space"
EDGE = ROOT / "feat" / "edge-ai"
DASH = ROOT / "feat" / "dashboard-devops" / "dashboard-api"
RUNTIME = ROOT / "runtime"


def load_env_file(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


SHARED = load_env_file(ROOT / ".env.example")
PROVIDERS = {"traffic_sensor_1": 8001, "bus_line_12": 8002, "parking_lot_5": 8003, "bikes_zone_a": 8004}
PROVIDER_KEYS = {"traffic_sensor_1": "TRAFFIC_API_KEY", "bus_line_12": "BUS_API_KEY",
                 "parking_lot_5": "PARKING_API_KEY", "bikes_zone_a": "BIKES_API_KEY"}


def services(with_sim: bool) -> list[tuple[str, Path, list[str], dict, int | None]]:
    uv = [sys.executable, "-m", "uvicorn"]
    provider_urls = ",".join(f"{p}=http://127.0.0.1:{port}" for p, port in PROVIDERS.items())
    common = {"DATA_SPACE_URL": "http://127.0.0.1:8010", "DATA_SPACE_SERVICE_TOKEN": SHARED["DATA_SPACE_SERVICE_TOKEN"]}
    result = [("data-space", DS, uv + ["dataspace.main:app", "--host", "127.0.0.1", "--port", "8010"],
               {**common, "DATA_SPACE_DB": str(RUNTIME / "dataspace.db")}, 8010)]
    for pid, port in PROVIDERS.items():
        result.append((f"api-{pid}", API, uv + ["provider_api.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port)], {
            **common, "PROVIDER_ID": pid, "PROVIDER_API_PORT": str(port), "PUBLIC_URL": f"http://127.0.0.1:{port}",
            "DATA_SIMULATION_PATH": str(SIM), "API_KEYS": SHARED["API_KEYS"],
            "PROVIDER_API_KEY": SHARED[PROVIDER_KEYS[pid]], "RUNTIME_DIR": str(RUNTIME / "provider-api" / pid),
            "CATALOGUE_REFRESH_SECONDS": "15", "PARTNER_URLS": provider_urls}, port))
    result.append(("edge-ai", EDGE, uv + ["edge_ai.service:create_app", "--factory", "--host", "127.0.0.1", "--port", "8020"], {
        **common, "TRAFFIC_API_URL": "http://127.0.0.1:8001", "EDGE_API_KEY": SHARED["EDGE_API_KEY"],
        "EDGE_POLL_SECONDS": "3"}, 8020))
    result.append(("dashboard-api", DASH, uv + ["app.main:app", "--host", "127.0.0.1", "--port", "8000"], {
        **common, "EDGE_URL": "http://127.0.0.1:8020", "PROVIDER_URLS": provider_urls,
        "DASHBOARD_API_KEY": SHARED["DASHBOARD_API_KEY"]}, 8000))
    if with_sim:
        for pid in PROVIDERS:
            result.append((f"sim-{pid}", SIM, [sys.executable, "cli.py", "start", "--provider", pid], {}, None))
    return result


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-sim", action="store_true", help="do not start the live simulators")
    args = parser.parse_args()

    busy = [port for *_, port in services(False) if port and port_in_use(port)]
    if busy:
        sys.exit(f"ports already in use: {busy} - is another stack still running?")

    logs = RUNTIME / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    procs = []
    for name, cwd, cmd, env, port in services(not args.no_sim):
        log_file = open(logs / f"{name}.log", "w", encoding="utf-8")
        procs.append((name, port, subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **env, "PYTHONUNBUFFERED": "1"},
                                                   stdout=log_file, stderr=subprocess.STDOUT)))
        print(f"started {name:<24} {'http://127.0.0.1:%d' % port if port else ''}")

    deadline = time.time() + 60
    for name, port, _ in procs:
        while port and time.time() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
    print("\nAll services up. Dashboard API: http://127.0.0.1:8000/api/dashboard")
    print("Swagger: http://127.0.0.1:8001/docs (providers 8001-8004), :8010/docs (data space), :8020/docs (edge AI)")
    print("Frontend: cd feat/dashboard-devops/dashboard && npm run dev  (with VITE_USE_MOCK_DATA=false)")
    print("Ctrl+C to stop.")
    try:
        while all(p.poll() is None for _, _, p in procs):
            time.sleep(1)
        for name, _, p in procs:
            if p.poll() is not None:
                print(f"{name} exited with code {p.returncode}, see runtime/logs/{name}.log")
    except KeyboardInterrupt:
        pass
    finally:
        for _, _, p in procs:
            if p.poll() is None:
                p.terminate()
        for _, _, p in procs:
            p.wait(timeout=10)
        print("stopped.")


if __name__ == "__main__":
    main()
