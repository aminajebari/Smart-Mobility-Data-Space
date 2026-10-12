"""System-level smoke test: proves every service communicates (final integration scenario).

Run against a running stack (scripts/run_local.py, docker compose or Kubernetes):
    python scripts/smoke_test.py
    python scripts/smoke_test.py --wait-incident    # also wait until the traffic sensor reports an incident

Service URLs come from environment variables (defaults = local ports).
"""
import argparse
import os
import sys
import time

import httpx

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

http = httpx.Client(timeout=10)
failures = []


def check(label: str, condition: bool, detail: str = ""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{' - ' + detail if detail else ''}")
    if not condition:
        failures.append(label)


def wait_until(fn, timeout: float, interval: float = 2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = fn()
            if result:
                return result
        except httpx.HTTPError:
            pass
        time.sleep(interval)
    return None


def get_data(base, key, dataset, purpose, **params):
    headers = {"X-API-Key": KEYS[key]} if key else {}
    return http.get(f"{base}/data", params={"dataset_id": dataset, "purpose": purpose, **params}, headers=headers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-incident", action="store_true")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()

    print("0. Services are up")
    for name, url in URLS.items():
        ok = wait_until(lambda: http.get(f"{url}/health").status_code == 200, args.timeout)
        check(f"{name} /health", bool(ok), url)
    if failures:
        return finish()

    print("1-2. Provider APIs publish the current mobility state")
    for name in ("bus", "parking"):
        r = http.get(f"{URLS[name]}/data", params={"limit": 1})
        check(f"{name}: public dataset readable anonymously", r.status_code == 200 and r.json()["count"] == 1)
    catalogue = http.get(f"{URLS['data_space']}/catalogue").json()
    published = [d["id"] for d in catalogue if d.get("access_url")]
    check("providers self-published their offerings to the catalogue", TRAFFIC in published, f"{len(published)} with access_url")
    if args.wait_incident:
        incident = wait_until(lambda: http.get(f"{URLS['traffic']}/data", params={"limit": 20, "incident": True},
                                               headers={"X-API-Key": os.environ.get("TRAFFIC_API_KEY", "traffic-demo-key")}
                                               ).json().get("count"), args.timeout * 4, 5)
        check("traffic sensor reported an incident / congestion", bool(incident))

    print("3. Edge node predicts congestion locally")
    latest = wait_until(lambda: http.get(f"{URLS['edge']}/predictions/latest").json()
                        if http.get(f"{URLS['edge']}/predictions/latest").status_code == 200 else None, args.timeout)
    check("edge prediction available", bool(latest),
          f"p={latest['congestion_probability']} level={latest['traffic_level']}" if latest else "none")
    info = http.get(f"{URLS['edge']}/model-info").json()
    check("model-info exposes ONNX format and metrics", info.get("edge_format", "").startswith("ONNX") and "metrics" in info)

    print("4-5. Partners request the prediction / dataset; the Data Space decides allow or deny")
    allowed = get_data(URLS["traffic"], "city", FORECAST, "traffic_management", limit=1)
    check("member partner gets the forecast (partner_only)", allowed.status_code == 200 and allowed.json()["count"] == 1,
          f"HTTP {allowed.status_code}")
    check("forecast contains results only, no raw readings",
          allowed.status_code == 200 and all("speed" not in r for r in allowed.json()["records"]))
    guest = get_data(URLS["traffic"], "startup", FORECAST, "commercial")
    check("guest participant is denied the forecast", guest.status_code == 403, f"HTTP {guest.status_code}")
    denied = get_data(URLS["traffic"], "startup", TRAFFIC, "commercial")
    check("raw traffic data denied for a non-allowed purpose", denied.status_code == 403)
    private = http.get(f"{URLS['bus']}/data", params={"dataset_id": "bus_line_12.passenger_counts", "purpose": "research"},
                       headers={"X-API-Key": KEYS["city"]})
    check("'denied' dataset never leaves its provider", private.status_code == 403)

    bus_headers = {"X-API-Key": KEYS["bus"]}
    no_contract = http.get(f"{URLS['bus']}/partners/data", headers=bus_headers,
                           params={"dataset_id": TRAFFIC, "purpose": "traffic_management", "limit": 3})
    contract = http.post(f"{URLS['bus']}/partners/contracts", headers=bus_headers,
                         json={"dataset_id": TRAFFIC, "purpose": "traffic_management"})
    check("provider-to-provider: bus operator negotiates a contract", contract.status_code == 200,
          contract.json().get("id", contract.text) if contract.status_code == 200 else contract.text)
    exchange = http.get(f"{URLS['bus']}/partners/data", headers=bus_headers,
                        params={"dataset_id": TRAFFIC, "purpose": "traffic_management", "limit": 3})
    check("provider-to-provider: bus API fetches traffic data via catalogue discovery",
          exchange.status_code == 200 and exchange.json()["count"] == 3,
          f"before contract HTTP {no_contract.status_code}, after HTTP {exchange.status_code}")

    print("6. Every exchange is written to the audit log")
    audit_ids = [r.json()["detail"]["audit_id"] for r in (guest, denied)] + [allowed.json()["authorization"]["audit_id"]]
    entries = {e["id"]: e for e in http.get(f"{URLS['data_space']}/audit", params={"limit": 1000}).json()}
    check("allowed and denied requests are traceable in /audit", all(i in entries for i in audit_ids))
    check("audit entries record requester, purpose, policy and decision",
          all({"requester_id", "purpose", "policy_type", "decision"} <= entries[i].keys() for i in audit_ids if i in entries))
    logs = http.get(f"{URLS['traffic']}/logs", params={"limit": 50},
                    headers={"X-API-Key": os.environ.get("DASHBOARD_API_KEY", "dashboard-demo-key")})
    check("provider API keeps its own request log", logs.status_code == 200 and len(logs.json()) > 0)

    print("7. Dashboard shows providers, traffic, AI prediction and exchange trace")
    dashboard = wait_until(lambda: http.get(f"{URLS['dashboard_api']}/api/dashboard").json(), args.timeout)
    check("dashboard aggregate available", bool(dashboard))
    if dashboard:
        connected = sum(p["status"] == "connected" for p in dashboard["providers"])
        check("providers listed with status", len(dashboard["providers"]) == 4, f"{connected}/4 connected")
        check("all services healthy or reachable", all(s["status"] != "offline" for s in dashboard["services"]))
        check("traffic time series present", len(dashboard["traffic"]) > 0)
        check("AI prediction shown", dashboard["predictions"][0]["value"] != "waiting")
        check("exchange trace shown", len(dashboard["exchanges"]) > 0)
    return finish()


def finish():
    print(f"\n{'SMOKE TEST PASSED' if not failures else f'SMOKE TEST FAILED ({len(failures)} checks)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
