# Distributed API Engineer: feat/distributed-api

One **shared FastAPI template** ([`provider_api/`](provider_api)) started once per mobility provider.
It is the only public access point to a provider's data:

- raw records are read **only** through Module 1's `access/local_data_api.py`;
- every request is authenticated (API key → participant id), **checked by the Data Space policy
  service** (Module 3) before any data leaves, and written to a request log;
- results such as Edge AI predictions are published back with `POST /publish`;
- providers exchange data with each other through the inter-service client
  ([`provider_api/client.py`](provider_api/client.py)), discovering partner endpoints in the catalogue.

## Run one provider

```powershell
pip install -r requirements.txt
$env:PROVIDER_ID = "traffic_sensor_1"
$env:DATA_SIMULATION_PATH = "..\data-simulation"
$env:API_KEYS = "edge-demo-key:edge_node_1,city-demo-key:city_planning_office"
$env:DATA_SPACE_URL = "http://localhost:8010"
uvicorn provider_api.main:create_app --factory --port 8001     # Swagger: http://localhost:8001/docs
python -m pytest -q                                            # 16 tests
```

To start all four providers with the rest of the system, use `python scripts/run_local.py` from the repo root.

| Variable | Default | Role |
|---|---|---|
| `PROVIDER_ID` | `traffic_sensor_1` | which provider this instance serves ([`config/providers.yaml`](config/providers.yaml)) |
| `PROVIDER_API_PORT` | 8001 | listening port |
| `PUBLIC_URL` | `http://localhost:<port>` | `access_url` advertised in the catalogue |
| `DATA_SIMULATION_PATH` | `../data-simulation` | location of Module 1's `access` package |
| `DATA_SPACE_URL`, `DATA_SPACE_SERVICE_TOKEN` | `http://localhost:8010`, empty | policy service |
| `API_KEYS` | empty | `key:participant_id,...` |
| `PROVIDER_API_KEY` | empty | this provider's own key, used for `/partners/*` calls |
| `LOG_READERS` | `dashboard_operator` | participants allowed to read `/logs` besides the provider |
| `RUNTIME_DIR` | `runtime/<provider>` | request log + published datasets |
| `CATALOGUE_REFRESH_SECONDS` | 30 | how often the catalogue entry is refreshed |
| `PARTNER_URLS` | empty | static fallback `provider=url,...` when the catalogue has no `access_url` |

## Endpoints

See [`shared/API_CONTRACTS.md`](../../shared/API_CONTRACTS.md#module-2-provider-api) for the full contract.

```text
GET  /data?dataset_id=traffic_sensor_1.traffic_flow&purpose=congestion_prediction&limit=10
     -H "X-API-Key: edge-demo-key"
GET  /data?incident=true&since=2026-10-05T10:00:00&until=2026-10-05T10:10:00
GET  /data?lat=36.8065&lon=10.1815&radius_km=0.5
GET  /search?q=parking&scope=data_space
POST /publish {"dataset_id": "traffic_sensor_1.congestion_forecast", "records": [...]}
GET  /partners/data?dataset_id=traffic_sensor_1.traffic_flow&purpose=traffic_management  (as bus_line_12)
```

## Design choices

- **Fail closed:** if the policy service is unreachable, `/data` answers 503 rather than serving data unchecked.
- **Anonymous requests are still policy-checked** (and audited), so public datasets need no key.
- **Raw datasets are read-only through the API:** `/publish` only accepts records for `published` datasets.
- `/partners/*` act with the provider's own identity, so they require the provider's own key.
